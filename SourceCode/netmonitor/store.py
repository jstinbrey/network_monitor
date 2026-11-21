"""SQLite storage: the devices found by scans and the history of every ping test.

Each function opens its own short-lived connection, because services run in
worker threads and a SQLite connection must not be shared between threads.
"""
import ipaddress
import json
import sqlite3
from contextlib import closing
from dataclasses import asdict
from datetime import datetime

from netmonitor import config
from netmonitor.models import Device, Event, PingResult, User


DEVICE_COLUMNS = "network, ip, mac, hostname, alias, replied_icmp, is_self, is_gateway, known, first_seen, last_seen"
PING_FIELDS = "ip, sent, received, loss_pct, rtts_ms, min_ms, avg_ms, max_ms, status, method, timestamp"
PING_COLUMNS = "network, " + PING_FIELDS     # the PingResult fields plus the network they were measured on

SCHEMA = f"""
CREATE TABLE IF NOT EXISTS devices ({DEVICE_COLUMNS}, PRIMARY KEY (network, ip));
CREATE TABLE IF NOT EXISTS known_macs (network, mac, PRIMARY KEY (network, mac));
CREATE TABLE IF NOT EXISTS pings (id INTEGER PRIMARY KEY, {PING_COLUMNS});
CREATE INDEX IF NOT EXISTS pings_by_host ON pings (network, ip);
CREATE TABLE IF NOT EXISTS users (username PRIMARY KEY, salt BLOB, hash BLOB, role);
CREATE TABLE IF NOT EXISTS port_checks (network, ip, checked_at, open_ports, PRIMARY KEY (network, ip));
CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, network, at, kind, severity, ip, mac, detail,
                                   dismissed DEFAULT 0);
CREATE TABLE IF NOT EXISTS presence (network, mac, at, up);
CREATE TABLE IF NOT EXISTS usage (day PRIMARY KEY, bytes_recv DEFAULT 0, bytes_sent DEFAULT 0);
CREATE TABLE IF NOT EXISTS settings (key PRIMARY KEY, value);
"""
NETWORK_TABLES = ("devices", "known_macs", "pings", "port_checks", "events", "presence")   # keyed by network


def _connect(path=None):
    path = path or config.DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.executescript(SCHEMA)
    return db


def _placeholders(columns: str) -> str:
    """"ip, sent" -> ":ip, :sent", so values are passed by name and never pasted into the SQL."""
    return ", ".join(":" + name.strip() for name in columns.split(","))


def save_scan(devices: list[Device], network: str, path=None):
    """Store one scan's devices for a network (its CIDR string).

    The first scan of a network becomes its baseline: every MAC seen is
    recorded as known. On later scans a device whose MAC is not in that
    baseline gets known=False. Devices missing from this scan are kept, so
    a device that left the network can later be reported as unreachable.
    """
    with closing(_connect(path)) as db, db:   # "with db" commits, or rolls back on an error
        known = {row["mac"] for row in db.execute("SELECT mac FROM known_macs WHERE network = ?", (network,))}
        for device in devices:
            if not known and device.mac:
                db.execute("INSERT OR IGNORE INTO known_macs VALUES (?, ?)", (network, device.mac))
            device.known = not known or device.mac is None or device.mac in known
            db.execute(
                f"INSERT INTO devices ({DEVICE_COLUMNS}) VALUES ({_placeholders(DEVICE_COLUMNS)}) "
                "ON CONFLICT (network, ip) DO UPDATE SET mac = excluded.mac, hostname = excluded.hostname, "
                "replied_icmp = excluded.replied_icmp, is_self = excluded.is_self, "
                "is_gateway = excluded.is_gateway, known = excluded.known, last_seen = excluded.last_seen",
                asdict(device) | {"network": network})   # first_seen is not updated: it keeps its first value


def get_devices(network: str, path=None) -> list[Device]:
    """Every device ever seen on a network, sorted by IP address."""
    with closing(_connect(path)) as db:
        rows = db.execute("SELECT * FROM devices WHERE network = ?", (network,)).fetchall()
    devices = [Device(**{key: row[key] for key in row.keys() if key != "network"}) for row in rows]
    return sorted(devices, key=lambda device: ipaddress.ip_address(device.ip))


def mark_known(mac: str, network: str, path=None):
    """Add a MAC to the network's baseline, after the user confirms the device belongs."""
    with closing(_connect(path)) as db, db:
        db.execute("INSERT OR IGNORE INTO known_macs VALUES (?, ?)", (network, mac))
        db.execute("UPDATE devices SET known = 1 WHERE network = ? AND mac = ?", (network, mac))


def set_alias(ip: str, alias: str, network: str, path=None):
    """Name a device. A rescan never overwrites the alias column, so the name stays."""
    # shortcut: the name belongs to the IP, so a device that DHCP moves to a new IP loses it.
    with closing(_connect(path)) as db, db:
        db.execute("UPDATE devices SET alias = ? WHERE network = ? AND ip = ?", (alias, network, ip))


def save_ping(result: PingResult, network: str, path=None):
    """Append one ping result to the history of a network."""
    with closing(_connect(path)) as db, db:
        db.execute(f"INSERT INTO pings ({PING_COLUMNS}) VALUES ({_placeholders(PING_COLUMNS)})",
                   asdict(result) | {"network": network, "rtts_ms": json.dumps(result.rtts_ms)})


def get_pings(ip: str, network: str, path=None) -> list[PingResult]:
    """All stored ping results for a host on a network, oldest first."""
    with closing(_connect(path)) as db:
        rows = db.execute(f"SELECT {PING_FIELDS} FROM pings WHERE network = ? AND ip = ? ORDER BY id",
                          (network, ip)).fetchall()
    return [PingResult(**dict(row) | {"rtts_ms": json.loads(row["rtts_ms"])}) for row in rows]


def save_port_check(ip: str, open_ports: list[dict], network: str, path=None):
    """Remember the latest port check of a host; it replaces the one before."""
    with closing(_connect(path)) as db, db:
        db.execute("INSERT OR REPLACE INTO port_checks VALUES (?, ?, ?, ?)",
                   (network, ip, datetime.now().isoformat(timespec="seconds"), json.dumps(open_ports)))


def get_port_checks(network: str, path=None) -> dict[str, list[dict]]:
    """{ip: open ports} for every host checked on a network."""
    with closing(_connect(path)) as db:
        rows = db.execute("SELECT ip, open_ports FROM port_checks WHERE network = ?", (network,)).fetchall()
    return {row["ip"]: json.loads(row["open_ports"]) for row in rows}


def add_event(network: str, event: Event, path=None) -> int:
    """Store one event; returns its id, which Dismiss needs."""
    with closing(_connect(path)) as db, db:
        return db.execute("INSERT INTO events (network, at, kind, severity, ip, mac, detail) VALUES (?, ?, ?, ?, ?, ?, ?)",
                          (network, event.at, event.kind, event.severity, event.ip, event.mac, event.detail)).lastrowid


def get_events(network: str, limit=20, path=None) -> list[Event]:
    """The most recent events on a network, newest first. Dismissed ones are included and marked."""
    with closing(_connect(path)) as db:
        rows = db.execute("SELECT id, at, kind, severity, ip, mac, detail, dismissed FROM events "
                          "WHERE network = ? ORDER BY id DESC LIMIT ?", (network, limit)).fetchall()
    return [Event(**dict(row) | {"dismissed": bool(row["dismissed"])}) for row in rows]


def dismiss_event(event_id: int, path=None):
    with closing(_connect(path)) as db, db:
        db.execute("UPDATE events SET dismissed = 1 WHERE id = ?", (event_id,))


def add_presence(network: str, at: str, rows: list[tuple[str, bool]], path=None):
    """One watch check: for each known MAC, whether it was found (up) or not."""
    with closing(_connect(path)) as db, db:
        db.executemany("INSERT INTO presence VALUES (?, ?, ?, ?)", [(network, mac, at, up) for mac, up in rows])


def get_presence(network: str, mac: str, since: str, path=None) -> list[tuple[str, bool]]:
    """(at, up) of every watch check of one device since an ISO time, oldest first."""
    with closing(_connect(path)) as db:
        rows = db.execute("SELECT at, up FROM presence WHERE network = ? AND mac = ? AND at >= ? ORDER BY at",
                          (network, mac, since)).fetchall()
    return [(row["at"], bool(row["up"])) for row in rows]


def get_settings(path=None) -> dict:
    """Every saved setting as {key: value}. Settings never saved are missing: config gives their defaults."""
    with closing(_connect(path)) as db:
        return {row["key"]: row["value"] for row in db.execute("SELECT key, value FROM settings")}


def save_settings(values: dict, path=None):
    with closing(_connect(path)) as db, db:
        db.executemany("INSERT OR REPLACE INTO settings VALUES (?, ?)", values.items())


def get_usage(day: str, path=None) -> int:
    """Bytes received plus sent on one day (an ISO date), as saved so far."""
    with closing(_connect(path)) as db:
        row = db.execute("SELECT bytes_recv + bytes_sent FROM usage WHERE day = ?", (day,)).fetchone()
    return row[0] if row else 0


def add_usage(day: str, recv: int, sent: int, path=None):
    """Add bytes to a day's totals; the day's row is made on its first save."""
    with closing(_connect(path)) as db, db:
        db.execute("INSERT INTO usage VALUES (?, ?, ?) ON CONFLICT (day) DO UPDATE SET "
                   "bytes_recv = bytes_recv + excluded.bytes_recv, bytes_sent = bytes_sent + excluded.bytes_sent",
                   (day, recv, sent))


def clear_network(network: str, path=None):
    """Delete everything stored for one network. Accounts, settings and daily usage are kept."""
    with closing(_connect(path)) as db, db:
        for table in NETWORK_TABLES:      # names come from the constant above, never from input
            db.execute(f"DELETE FROM {table} WHERE network = ?", (network,))


def add_user(username: str, salt: bytes, digest: bytes, role: str, path=None):
    """Store a new account. The password itself is never stored, only its salt and hash."""
    with closing(_connect(path)) as db, db:
        db.execute("INSERT INTO users VALUES (?, ?, ?, ?)", (username, salt, digest, role))


def get_user(username: str, path=None):
    """The account's row (username, salt, hash, role), or None if there is no such user."""
    with closing(_connect(path)) as db:
        return db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()


def list_users(path=None) -> list[User]:
    """Every account, sorted by username."""
    with closing(_connect(path)) as db:
        rows = db.execute("SELECT username, role FROM users ORDER BY username").fetchall()
    return [User(row["username"], row["role"]) for row in rows]


def set_password(username: str, salt: bytes, digest: bytes, path=None):
    with closing(_connect(path)) as db, db:
        db.execute("UPDATE users SET salt = ?, hash = ? WHERE username = ?", (salt, digest, username))


def set_role(username: str, role: str, path=None):
    with closing(_connect(path)) as db, db:
        db.execute("UPDATE users SET role = ? WHERE username = ?", (role, username))


def delete_user(username: str, path=None):
    with closing(_connect(path)) as db, db:
        db.execute("DELETE FROM users WHERE username = ?", (username,))