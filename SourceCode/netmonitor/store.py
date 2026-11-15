"""SQLite storage: the devices found by scans and the history of every ping test.

Each function opens its own short-lived connection, because services run in
worker threads and a SQLite connection must not be shared between threads.
"""
import ipaddress
import json
import sqlite3
from contextlib import closing
from dataclasses import asdict

from netmonitor import config
from netmonitor.models import Device, PingResult

DEVICE_COLUMNS = "network, ip, mac, hostname, replied_icmp, is_self, is_gateway, known, first_seen, last_seen"
PING_COLUMNS = "ip, sent, received, loss_pct, rtts_ms, min_ms, avg_ms, max_ms, status, method, timestamp"

SCHEMA = f"""
CREATE TABLE IF NOT EXISTS devices ({DEVICE_COLUMNS}, PRIMARY KEY (network, ip));
CREATE TABLE IF NOT EXISTS known_macs (network, mac, PRIMARY KEY (network, mac));
CREATE TABLE IF NOT EXISTS pings (id INTEGER PRIMARY KEY, {PING_COLUMNS});
CREATE INDEX IF NOT EXISTS pings_by_ip ON pings (ip);
"""


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


def save_ping(result: PingResult, path=None):
    """Append one ping result to the history."""
    with closing(_connect(path)) as db, db:
        db.execute(f"INSERT INTO pings ({PING_COLUMNS}) VALUES ({_placeholders(PING_COLUMNS)})",
                   asdict(result) | {"rtts_ms": json.dumps(result.rtts_ms)})


def get_pings(ip: str, path=None) -> list[PingResult]:
    """All stored ping results for a host, oldest first."""
    with closing(_connect(path)) as db:
        rows = db.execute(f"SELECT {PING_COLUMNS} FROM pings WHERE ip = ? ORDER BY id", (ip,)).fetchall()
    return [PingResult(**dict(row) | {"rtts_ms": json.loads(row["rtts_ms"])}) for row in rows]