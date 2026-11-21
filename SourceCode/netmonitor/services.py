"""The only module the GUI imports.

Every function here can block for seconds, so views call them through
gui.worker.run_async and never directly.
"""
import ipaddress
import math
import socket
import time

from netmonitor import config, models, store
from netmonitor.core import advisor, auth, discovery, netinfo, pinger, ports, report_builder, statistics, tracer, vendor

validate_ip = pinger.validate_ip          # raises ValueError on bad input
network_info = netinfo.get_network_info   # Feature 1: local IP, range, gateway
hop_segment = tracer.segment              # traceroute: "your router", "ISP access network" or "internet"


def _network_id(info, macs=None) -> str:
    """Which network this is: its range plus the gateway's MAC address.

    Two networks that both use 192.168.1.0/24 (home and a cafe, say) have
    different routers, so they get separate device lists and ping history.
    macs: the {ip: mac} ARP entries, when the caller has already read them.
    """
    network = ipaddress.ip_network(info.cidr)
    if macs is None:
        macs = discovery.read_arp(info.local_ip, network)
    if info.gateway and info.gateway not in macs:   # the ARP cache can be empty right after connecting
        pinger.is_alive(info.gateway)               # one ping makes Windows learn the gateway's MAC
        macs = discovery.read_arp(info.local_ip, network)
    return f"{info.cidr} via {macs.get(info.gateway, 'no gateway')}"


def _with_vendor(devices):
    """Fill in each device's maker. Done here, in a worker thread, because the first lookup reads the registry."""
    for device in devices:
        device.vendor = vendor.vendor(device.mac)
    return devices


def _current():
    """(network id, stored devices) for the network this PC is on now."""
    network = _network_id(netinfo.get_network_info())
    return network, _with_vendor(store.get_devices(network))


def scan(on_progress=None):
    """Feature 1: find every active device on the local network and remember them."""
    require_admin()
    info = netinfo.get_network_info()
    devices = discovery.discover(info, on_progress)
    # The scan has just read the ARP table, so the gateway's MAC is already in the results.
    store.save_scan(devices, _network_id(info, {d.ip: d.mac for d in devices if d.mac}))
    return _with_vendor(devices)


def _record(results):
    """Save ping results. A host with no reply that still answers ARP is up but blocks ICMP."""
    info = netinfo.get_network_info()
    neighbours = discovery.read_arp(info.local_ip, ipaddress.ip_network(info.cidr))
    network = _network_id(info, neighbours)
    for result in results:
        if result.status == models.OFFLINE and result.ip in neighbours:
            result.status = models.NO_ICMP
        store.save_ping(result, network)
    return results


def run_ping(ip, count=config.PING_COUNT):
    """Feature 2: ping one host and store the result."""
    return _record([pinger.ping(ip, count)])[0]


def run_ping_many(ips, count=config.PING_COUNT):
    """Feature 2: ping several hosts in parallel and store the results."""
    return _record(pinger.ping_many(ips, count))


def start_traceroute(target, on_hop, on_done):
    """Feature 2 extension: trace the route to an IP address or a name; returns the running trace, for Stop.

    on_hop(hop) is called as each hop arrives, and on_done((hops, status, sentence)) at the end,
    both from the trace's own thread.
    """
    target = target.strip()
    try:
        ip = pinger.validate_ip(socket.gethostbyname(target)) if target else None
    except (OSError, UnicodeError, ValueError):     # a name that does not resolve
        ip = None
    if ip is None:
        raise ValueError("Enter an IP address or a host name that exists, for example 1.1.1.1.")

    def done(hops):
        _running.discard(trace)
        on_done((hops, *(("info", "Stopped.") if trace.stopped else tracer.analyse(hops, ip))))

    trace = tracer.Traceroute(ip, on_hop, done)
    _running.add(trace)
    trace.start()
    return trace


def devices():
    """Feature 1: the devices stored for this network, shown when the Devices view opens."""
    return _current()[1]


def _stats(devices, network):
    return [statistics.host_stats(device, store.get_pings(device.ip, network)) for device in devices]


def stats():
    """Feature 3: one row of statistics per device known on this network."""
    network, devices = _current()
    return _stats(devices, network)


def refresh_all():
    """Feature 3: ping every known device, then return fresh statistics."""
    network, devices = _current()
    run_ping_many([device.ip for device in devices])
    return _stats(devices, network)


def history(ip, limit=10):
    """Feature 3: the most recent ping tests of one host, oldest first, for the history chart."""
    network = _network_id(netinfo.get_network_info())
    return store.get_pings(ip, network)[-limit:]


def device_detail(ip):
    """Device panel: one device, its statistics, its last 10 ping tests and its latest port check."""
    network, devices = _current()
    device = next((d for d in devices if d.ip == ip), None) or models.Device(ip=ip)   # pinged but never scanned
    pings = store.get_pings(ip, network)
    return models.DeviceDetail(device, statistics.host_stats(device, pings), pings[-10:],
                               store.get_port_checks(network).get(ip))


def set_alias(ip, name):
    """Admin: give a device a name that is shown instead of its hostname. An empty name removes it."""
    require_admin()
    store.set_alias(ip, name.strip()[:config.ALIAS_MAX_LEN], _network_id(netinfo.get_network_info()))
    return device_detail(ip)


def check_ports(ip):
    """Admin, Feature 5 bonus: which common TCP ports a device has open. The result is kept for the advisor."""
    require_admin()
    store.save_port_check(ip, ports.check_ports(ip), _network_id(netinfo.get_network_info()))
    return device_detail(ip)


def _live():
    """(details, live ARP table, network id, stored devices) for the network this PC is on now.

    The spoofing check needs the live table: stored devices keep old IPs after DHCP hands out new ones.
    """
    info = netinfo.get_network_info()
    arp = discovery.read_arp(info.local_ip, ipaddress.ip_network(info.cidr))
    network = _network_id(info, arp)
    return info, arp, network, _with_vendor(store.get_devices(network))


def generate_report(fmt):
    """Feature 4: write a report of the current network state; returns the file's path."""
    info, arp, network, devices = _live()
    host_stats = _stats(devices, network)
    return report_builder.build({
        "info": info, "devices": devices, "stats": host_stats, "summary": statistics.summary(host_stats),
        "recommendations": advisor.recommend(devices, host_stats, arp, info.gateway, store.get_port_checks(network)),
        "pings": [ping for device in devices for ping in store.get_pings(device.ip, network)[-1:]],   # latest per device
    }, fmt)


def reports():
    """Feature 4: the generated report files, newest first."""
    return sorted(config.OUTPUT_DIR.glob("report_*.*"), reverse=True)


def dashboard():
    """Dashboard: the network summary, per-host statistics, and recommendations in one call."""
    info, arp, network, devices = _live()
    host_stats = _stats(devices, network)
    recs = advisor.recommend(devices, host_stats, arp, info.gateway, store.get_port_checks(network))
    return statistics.summary(host_stats), host_stats, recs


def recommendations():
    """Feature 5: security and connectivity advice for the current network, most severe first."""
    return dashboard()[2]


def mark_known(ip):
    """Feature 5: the user confirms a new device belongs; returns the fresh recommendations."""
    require_admin()
    network, devices = _current()
    for device in devices:
        if device.ip == ip and device.mac:
            store.mark_known(device.mac, network)
    return recommendations()


def scan_and_refresh(on_progress=None):
    """Dashboard button for an Admin: scan for devices, ping every one, then return fresh dashboard data."""
    require_admin()
    scan(on_progress)
    refresh_all()
    return dashboard()


def refresh_dashboard():
    """Dashboard button for a User, who may not scan: ping the known devices, then return fresh dashboard data."""
    refresh_all()
    return dashboard()


def clear_history():
    """Admin: forget every device, ping and alert stored for the network this PC is on now."""
    require_admin()
    network = _network_id(netinfo.get_network_info())
    store.clear_network(network)
    return network


# --- Accounts and roles ----------------------------------------------------
_user = None                          # the signed-in models.User, or None
_failures, _locked_until = 0, 0.0     # wrong passwords in a row; time.monotonic() when sign-in reopens


def _clean(username):
    """Usernames are compared without case or surrounding spaces."""
    username = username.strip().lower()
    if not username:
        raise ValueError("Enter a username.")
    return username


def _add(username, password, confirm, role):
    username = _clean(username)
    if role not in (models.ADMIN, models.USER):
        raise ValueError(f"Unknown role: {role}")
    auth.check_new_password(username, password, confirm)
    if store.get_user(username):
        raise ValueError(f'The username "{username}" is already taken.')
    store.add_user(username, *auth.hash_password(password), role)
    return models.User(username, role)


def needs_setup():
    """True on the first run, before any account exists."""
    return not store.list_users()


def create_first_admin(username, password, confirm):
    """First run only: create the administrator account and sign in with it."""
    global _user
    if not needs_setup():
        raise PermissionError("An administrator account already exists.")
    _user = _add(username, password, confirm, models.ADMIN)
    return _user


def login(username, password):
    """Sign in. The same message for an unknown name and a wrong password, so neither is revealed."""
    global _user, _failures, _locked_until
    wait = _locked_until - time.monotonic()
    if wait > 0:
        raise ValueError(f"Too many attempts. Wait {math.ceil(wait)} s.")
    row = store.get_user(username.strip().lower())
    # An unknown name is still hashed, so it takes as long as a wrong password and timing reveals nothing.
    salt, digest = (row["salt"], row["hash"]) if row else (bytes(16), b"")
    if not auth.verify_password(password, salt, digest) or row is None:
        _failures += 1
        if _failures >= config.LOGIN_MAX_FAILURES:
            _failures, _locked_until = 0, time.monotonic() + config.LOGIN_LOCK_S
        raise ValueError("Wrong username or password.")
    _failures = 0
    _user = models.User(row["username"], row["role"])
    return _user


_running = set()                      # traceroutes still running (Step 7.2 adds continuous pings)


def stop_all():
    """Stop every running tracert (and, from Step 7.2, ping -t). Called by sign-out and window close."""
    for task in list(_running):       # a copy: a stopped task removes itself from the set
        task.stop()


def logout():
    global _user
    stop_all()
    _user = None


def current_user():
    return _user


def require_admin():
    """The real role check. Views also disable admin buttons, but only for convenience."""
    if not (_user and _user.is_admin):
        raise PermissionError("Only an administrator can do this.")


def users():
    require_admin()
    return store.list_users()


def add_user(username, password, confirm, role):
    require_admin()
    return _add(username, password, confirm, role)


def reset_password(username, password, confirm):
    require_admin()
    auth.check_new_password(username, password, confirm)
    store.set_password(username, *auth.hash_password(password))


def set_role(username, role):
    """Admins cannot change their own role, so there is always at least one admin."""
    require_admin()
    if role not in (models.ADMIN, models.USER):
        raise ValueError(f"Unknown role: {role}")
    if username == _user.username:
        raise ValueError("You cannot change the role of the account you are signed in with.")
    store.set_role(username, role)


def delete_user(username):
    """Admins cannot delete themselves, so there is always at least one admin."""
    require_admin()
    if username == _user.username:
        raise ValueError("You cannot delete the account you are signed in with.")
    store.delete_user(username)