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
NETWORK_TABLES = ("devices", "device_names", "known_macs", "pings", "port_checks", "events", "presence")


def device_owner(ip: str, mac: str | None) -> str:
    """Identify a device by MAC when known, otherwise by its address on this network."""
    return f"mac:{mac.lower().replace(':', '-')}" if mac else f"ip:{ip}"


def _upgrade_device_history(db):
    db.execute("BEGIN IMMEDIATE")
    if db.execute("PRAGMA user_version").fetchone()[0] != 0:
        return
    db.execute("CREATE TABLE device_names (network, owner, alias, first_seen, PRIMARY KEY (network, owner))")
    db.execute("INSERT OR IGNORE INTO device_names SELECT network, 'mac:' || LOWER(REPLACE(mac, ':', '-')), "
               "alias, first_seen FROM devices WHERE mac IS NOT NULL AND mac != '' ORDER BY last_seen DESC")
    db.execute("ALTER TABLE pings ADD COLUMN owner TEXT")
    db.execute("UPDATE pings SET owner = COALESCE((SELECT 'mac:' || LOWER(REPLACE(mac, ':', '-')) FROM devices "
               "WHERE devices.network = pings.network AND devices.ip = pings.ip AND mac != ''), 'ip:' || pings.ip)")
    db.execute("CREATE INDEX pings_by_owner ON pings (network, owner)")
    db.execute("ALTER TABLE port_checks RENAME TO legacy_port_checks")
    db.execute("CREATE TABLE port_checks (network, owner, ip, checked_at, open_ports, PRIMARY KEY (network, owner))")
    db.execute("INSERT OR REPLACE INTO port_checks SELECT p.network, "
               "COALESCE('mac:' || LOWER(REPLACE(NULLIF(d.mac, ''), ':', '-')), 'ip:' || p.ip), "
               "p.ip, p.checked_at, p.open_ports FROM legacy_port_checks p LEFT JOIN devices d "
               "ON d.network = p.network AND d.ip = p.ip ORDER BY p.checked_at")
    db.execute("DROP TABLE legacy_port_checks")
    db.execute("PRAGMA user_version = 1")


def _connect(path=None):
    path = path or config.DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    try:
        db.executescript(SCHEMA)
        if db.execute("PRAGMA user_version").fetchone()[0] == 0:
            with db:
                _upgrade_device_history(db)
    except Exception:
        db.close()
        raise
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
        db.execute("BEGIN IMMEDIATE")
        known = {row["mac"] for row in db.execute("SELECT mac FROM known_macs WHERE network = ?", (network,))}
        current = {row["ip"]: row for row in db.execute("SELECT * FROM devices WHERE network = ?", (network,))}
        seen_ips = {device.ip for device in devices}
        previous_addresses = {}
        for row in current.values():
            previous_addresses.setdefault(device_owner(row["ip"], row["mac"]), []).append(row["ip"])
        for device in devices:
            previous = current.get(device.ip)
            if previous and previous["last_seen"] > device.last_seen:
                continue
            if not known and device.mac:
                db.execute("INSERT OR IGNORE INTO known_macs VALUES (?, ?)", (network, device.mac))
            device.known = not known or device.mac is None or device.mac in known
            owner = device_owner(device.ip, device.mac)
            if device.mac:
                db.execute("INSERT OR IGNORE INTO device_names VALUES (?, ?, ?, ?)",
                           (network, owner, device.alias, device.first_seen))
                meta = db.execute("SELECT alias, first_seen FROM device_names WHERE network = ? AND owner = ?",
                                  (network, owner)).fetchone()
                device.alias, device.first_seen = meta["alias"], meta["first_seen"]
                for ip in previous_addresses.get(owner, ()):
                    if ip not in seen_ips:
                        db.execute("DELETE FROM devices WHERE network = ? AND ip = ? AND last_seen <= ?",
                                   (network, ip, device.last_seen))
            elif previous and not previous["mac"]:
                device.alias, device.first_seen = previous["alias"], previous["first_seen"]
            db.execute(
                f"INSERT INTO devices ({DEVICE_COLUMNS}) VALUES ({_placeholders(DEVICE_COLUMNS)}) "
                "ON CONFLICT (network, ip) DO UPDATE SET mac = excluded.mac, hostname = excluded.hostname, "
                "alias = excluded.alias, first_seen = excluded.first_seen, "
                "replied_icmp = excluded.replied_icmp, is_self = excluded.is_self, "
                "is_gateway = excluded.is_gateway, known = excluded.known, last_seen = excluded.last_seen",
                asdict(device) | {"network": network})


def get_devices(network: str, path=None) -> list[Device]:
    """Every device ever seen on a network, sorted by IP address."""
    with closing(_connect(path)) as db:
        rows = db.execute("SELECT * FROM devices WHERE network = ?", (network,)).fetchall()
    devices = [Device(**{key: row[key] for key in row.keys() if key != "network"}) for row in rows]
    return sorted(devices, key=lambda device: ipaddress.ip_address(device.ip))


def mark_known(mac: str, network: str, path=None):
    """Add a MAC to the baseline and report whether it was newly added."""
    with closing(_connect(path)) as db, db:
        inserted = db.execute("INSERT OR IGNORE INTO known_macs VALUES (?, ?)", (network, mac)).rowcount
        db.execute("UPDATE devices SET known = 1 WHERE network = ? AND mac = ?", (network, mac))
        return bool(inserted)


def unmark_known(mac: str, network: str, path=None):
    """Undo a device confirmation on the network where it was made."""
    with closing(_connect(path)) as db, db:
        db.execute("DELETE FROM known_macs WHERE network = ? AND mac = ?", (network, mac))
        db.execute("UPDATE devices SET known = 0 WHERE network = ? AND mac = ?", (network, mac))


def set_alias(ip: str, alias: str, network: str, path=None, *, owner=None):
    """Name a device and keep the name when its MAC moves to another IP."""
    with closing(_connect(path)) as db, db:
        db.execute("BEGIN IMMEDIATE")
        current = _current_owner(db, ip, network)
        if owner and owner != current:
            raise RuntimeError("The device at this address changed. Scan the network before renaming it.")
        owner = current
        if owner.startswith("mac:"):
            db.execute("UPDATE device_names SET alias = ? WHERE network = ? AND owner = ?", (alias, network, owner))
            db.execute("UPDATE devices SET alias = ? WHERE network = ? AND LOWER(REPLACE(mac, ':', '-')) = ?",
                       (alias, network, owner[4:]))
        else:
            db.execute("UPDATE devices SET alias = ? WHERE network = ? AND ip = ?", (alias, network, ip))


def _current_owner(db, ip, network):
    row = db.execute("SELECT mac FROM devices WHERE network = ? AND ip = ?", (network, ip)).fetchone()
    return device_owner(ip, row["mac"] if row else None)


def save_ping(result: PingResult, network: str, path=None, *, owner=None):
    """Append one ping result to the history of a network."""
    with closing(_connect(path)) as db, db:
        db.execute("BEGIN IMMEDIATE")
        owner = owner or _current_owner(db, result.ip, network)
        db.execute(f"INSERT INTO pings ({PING_COLUMNS}, owner) VALUES ({_placeholders(PING_COLUMNS)}, :owner)",
                   asdict(result) | {"network": network, "rtts_ms": json.dumps(result.rtts_ms), "owner": owner})


def get_pings(ip: str, network: str, path=None, *, owner=None) -> list[PingResult]:
    """Ping history for the device and the address family being tested."""
    with closing(_connect(path)) as db:
        owner = owner or _current_owner(db, ip, network)
        rows = db.execute(f"SELECT {PING_FIELDS} FROM pings WHERE network = ? AND owner = ? "
                          "AND (instr(ip, ':') > 0) = ? ORDER BY id", (network, owner, ":" in ip)).fetchall()
    return [PingResult(**dict(row) | {"rtts_ms": json.loads(row["rtts_ms"])}) for row in rows]


def save_port_check(ip: str, open_ports: list[dict], network: str, path=None, *, owner=None):
    """Remember the latest port check of a host; it replaces the one before."""
    with closing(_connect(path)) as db, db:
        db.execute("BEGIN IMMEDIATE")
        owner = owner or _current_owner(db, ip, network)
        db.execute("INSERT OR REPLACE INTO port_checks VALUES (?, ?, ?, ?, ?)",
                   (network, owner, ip, datetime.now().isoformat(timespec="seconds"), json.dumps(open_ports)))


def get_port_check(network: str, owner: str, path=None) -> list[dict] | None:
    with closing(_connect(path)) as db:
        row = db.execute("SELECT open_ports FROM port_checks WHERE network = ? AND owner = ?",
                         (network, owner)).fetchone()
    return json.loads(row["open_ports"]) if row else None


def get_port_checks(network: str, path=None) -> dict[str, list[dict]]:
    """{ip: open ports} for every host checked on a network."""
    with closing(_connect(path)) as db:
        db.execute("BEGIN")
        rows = db.execute("SELECT owner, ip, open_ports FROM port_checks WHERE network = ?", (network,)).fetchall()
        devices = db.execute("SELECT ip, mac FROM devices WHERE network = ?", (network,)).fetchall()
    owners = {row["ip"]: device_owner(row["ip"], row["mac"]) for row in devices}
    checks = {row["owner"]: json.loads(row["open_ports"]) for row in rows}
    results = {row["ip"]: checks[row["owner"]] for row in rows
               if row["owner"] == device_owner(row["ip"], None) and row["ip"] not in owners}
    results.update({ip: checks[owner] for ip, owner in owners.items() if owner in checks})
    return results


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
