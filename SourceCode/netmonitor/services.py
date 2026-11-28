"""The only module the GUI imports.

Every function here can block for seconds, so views call them through
gui.worker.run_async and never directly.
"""
import ipaddress
import math
import socket
import threading
import time
from datetime import date, datetime, timedelta

from netmonitor import config, models, store
from netmonitor.core import (advisor, auth, bandwidth, diagnosis, discovery, netinfo, pinger, ports, report_builder,
                             statistics, tracer, vendor, watch, wifi)

validate_ip = pinger.validate_ip          # raises ValueError on bad input
network_info = netinfo.get_network_info   # Feature 1: local IP, range, gateway
hop_segment = tracer.segment              # traceroute: "your router", "ISP access network" or "internet"
describe_bandwidth = bandwidth.describe   # the Connection view's verdict line
describe_wifi = wifi.describe             # "Excellent signal (92%, -43 dBm) on 5 GHz channel 40, WPA2-Personal"
rate_text = bandwidth.rate_text           # "12.4 Mbps", or "350 kbps" below 1 Mbps


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


def start_continuous_ping(ip, on_reply):
    """Feature 2: ping -t until Stop; returns the running ping, for Stop. Raises ValueError for a bad IP.

    on_reply(session, rtt_ms or None, line) is called from the reader thread for each reply.
    Starting a child process takes milliseconds, so a view may call this one directly.
    """
    session = pinger.PingSession(pinger.validate_ip(ip))

    def reply(rtt, line):                         # reader thread
        session.add(rtt)
        on_reply(session, rtt, line)

    def load_history():                           # the network id takes about 0.2 s, so not on the UI thread
        try:
            pings = store.get_pings(session.ip, _network_id(netinfo.get_network_info()))
        except RuntimeError:                      # not connected: the session learns from its own replies
            return
        session.history = [rtt for p in pings for rtt in p.rtts_ms][-config.BASELINE_WINDOW:]

    threading.Thread(target=load_history, daemon=True).start()
    handle = pinger.ContinuousPing(ip, reply)
    handle.session = session
    _running.add(handle)
    return handle


def stop_continuous_ping(handle):
    """Stop a continuous ping, store it like any other ping test, and return its verdict (status, sentence)."""
    handle.stop()
    _running.discard(handle)
    if handle.session.rtts:
        _record([handle.session.result()])        # stored like any ping; the ARP check is included
    return handle.session.verdict()


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


_last_verdict = None                  # (time, Verdict) of the latest diagnosis, for the report


def diagnose(on_step=None):
    """Find where a network problem is, one layer at a time: this PC, the router, the internet, DNS.

    on_step(DiagnosisStep) is called after each layer, from this worker thread, so the card fills in live.
    The router and both internet targets are pinged in parallel, so it takes about DIAG_PINGS seconds.
    """
    global _last_verdict
    def step(name, ok, detail):
        if on_step:
            on_step(models.DiagnosisStep(name, ok, detail))

    def short(stats):
        return "no reply" if stats.avg_ms is None else f"{stats.avg_ms:g} ms"

    m = models.Measurements()
    try:
        info = netinfo.get_network_info()
    except RuntimeError:                          # not connected to any network
        info = None
    m.local_ip = info.local_ip if info else None
    adapter = netinfo.get_adapter(m.local_ip) if info else None
    usable = info is not None and not m.local_ip.startswith("169.254.")
    step("Adapter", usable, f"{adapter}, {m.local_ip}" if info else "no address")
    m.wifi, note = wifi_link()
    if m.wifi:
        step("Wi-Fi", m.wifi.signal_pct >= config.WIFI_WEAK_PCT, f"{m.wifi.signal_pct}%, {m.wifi.band}")
    else:
        step("Wi-Fi", None, "not used" if note.startswith("Not on Wi-Fi") else "no details")
    if usable and info.gateway:
        results = pinger.ping_many([info.gateway, *config.INTERNET_TARGETS], config.DIAG_PINGS)
        m.gateway, *internet = [statistics.host_stats(models.Device(ip=r.ip), [r]) for r in results]
        m.internet = min(internet, key=lambda s: (s.loss_pct, s.avg_ms or math.inf))   # the better target
        step("Router", m.gateway.avg_ms is not None, short(m.gateway))
        step("Internet", m.internet.avg_ms is not None, short(m.internet))
        servers = diagnosis.dns_servers(adapter) if adapter else []
        m.dns_server = servers[0] if servers else None
        m.dns_ms = diagnosis.dns_query(m.dns_server) if m.dns_server else None
        m.dns_public_ms = diagnosis.dns_query(diagnosis.PUBLIC_DNS)
        step("DNS", m.dns_ms is not None, "no answer" if m.dns_ms is None else f"{m.dns_ms:g} ms")
    verdict = diagnosis.verdict(m)
    _last_verdict = (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), verdict)
    return verdict


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
    since = (datetime.now() - timedelta(hours=24)).isoformat(timespec="seconds")
    presence = store.get_presence(network, device.mac, since) if device.mac else []
    return models.DeviceDetail(device, statistics.host_stats(device, pings), pings[-10:],
                               store.get_port_checks(network).get(ip), presence, watch.uptime_pct(presence))


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


def _baselines(devices, network):
    """{ip: (latest test's average, baseline of every earlier reply)} for the "slower than usual" rule."""
    found = {}
    for device in devices:
        pings = store.get_pings(device.ip, network)
        if pings and pings[-1].avg_ms is not None:
            found[device.ip] = (pings[-1].avg_ms, statistics.baseline([r for p in pings[:-1] for r in p.rtts_ms]))
    return found


def _advice(info, arp, network, devices, host_stats, link):
    return advisor.recommend(devices, host_stats, arp, info.gateway, store.get_port_checks(network),
                             _baselines(devices, network), link)


def map_data(update=None):
    """Map view: (devices, {ip: HostStats}, IPs with a finding) for the network this PC is on now.

    update: "ping" pings every known device first; "scan" (Admin) scans for devices first, then pings them.
    A finding is a security one: a risky open port, or the device's MAC answering for several IPs in the live
    ARP table. Offline and slow devices already show in their node and link colours; new ones have a red ring.
    """
    if update == "scan":
        scan()
    if update:
        refresh_all()
    info, arp, network, devices = _live()
    host_stats = _stats(devices, network)
    recs = _advice(info, arp, network, devices, host_stats, None)
    macs = list(arp.values())
    issues = {r.host for r in recs if r.category == "Open ports" and r.severity != "info"}   # not the router's HTTP note
    issues |= {ip for ip, mac in arp.items() if macs.count(mac) > 1}
    return devices, {s.ip: s for s in host_stats}, issues


def wifi_link():
    """(this PC's WifiInfo or None, a note saying why there is none)."""
    try:
        link = wifi.read()
    except wifi.WifiUnavailable as error:
        return None, str(error)
    return link, "" if link else "Not on Wi-Fi: this PC is wired or not connected."


def wifi_details():
    """Connection view: (WifiInfo or None, note, nearby access points as (band, channel), advice line)."""
    link, note = wifi_link()
    nearby = wifi.nearby() if link else []
    advice = ""
    if link and link.band == "2.4 GHz" and wifi.best_24ghz_channel(nearby) != link.channel:
        advice = (f"Channel {wifi.best_24ghz_channel(nearby)} is the least crowded of 1, 6 and 11, the 2.4 GHz "
                  "channels that do not overlap: set it in the router.")
    return link, note, nearby, advice


def generate_report(fmt):
    """Feature 4: write a report of the current network state; returns the file's path."""
    info, arp, network, devices = _live()
    host_stats = _stats(devices, network)
    link, note = wifi_link()
    diagnosed_at, verdict = _last_verdict or ("", None)
    return report_builder.build({
        "info": info, "devices": devices, "stats": host_stats, "summary": statistics.summary(host_stats),
        "recommendations": _advice(info, arp, network, devices, host_stats, link),
        "pings": [ping for device in devices for ping in store.get_pings(device.ip, network)[-1:]],   # latest per device
        "verdict": verdict, "diagnosed_at": diagnosed_at, "ports": store.get_port_checks(network),
        "events": store.get_events(network, 10), "wifi": wifi.describe(link) if link else note,
        "usage_bytes": usage_today(),
    }, fmt)


def reports():
    """Feature 4: the generated report files, newest first."""
    return sorted(config.OUTPUT_DIR.glob("report_*.*"), reverse=True)


def dashboard():
    """Dashboard: the network summary, per-host statistics, recommendations and the Wi-Fi link in one call."""
    info, arp, network, devices = _live()
    host_stats = _stats(devices, network)
    link = wifi_link()
    return statistics.summary(host_stats), host_stats, _advice(info, arp, network, devices, host_stats, link[0]), link


def recommendations():
    """Feature 5: security and connectivity advice for the current network, most severe first."""
    return dashboard()[2]


def mark_known(ip):
    """Feature 5: the user confirms a new device belongs; returns the fresh recommendations."""
    mark_known_change(ip)
    return recommendations()


def mark_known_change(ip):
    """Confirm a device and return the network and MAC if the baseline changed."""
    require_admin()
    network, devices = _current()
    for device in devices:
        if device.ip == ip and device.mac:
            if store.mark_known(device.mac, network):
                return network, device.mac
            return None


def undo_mark_known(change):
    """Undo a confirmation using its original network and MAC."""
    require_admin()
    network, mac = change
    store.unmark_known(mac, network)


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


# --- Events (alerts) ---------------------------------------------------------
def record_event(kind, severity, ip, mac, detail, network=None):
    """Store something that happened, e.g. a bandwidth limit passed; returns it with its id, for the alert bar.
    network: the network id when the caller already knows it (working it out takes about 0.2 s)."""
    event = models.Event(None, datetime.now().isoformat(timespec="seconds"), kind, severity, ip, mac, detail)
    event.id = store.add_event(network or _network_id(netinfo.get_network_info()), event)
    return event


def events(limit=20):
    """The latest events on this network, newest first; dismissed ones included."""
    return store.get_events(_network_id(netinfo.get_network_info()), limit)


def dismiss(event_id):
    store.dismiss_event(event_id)


# --- Settings and the bandwidth monitor ---------------------------------------
_limits = {}                                    # the bandwidth settings, loaded on first use; save_settings updates it
_adapter = {"ip": None, "name": None, "meter": None}   # looked up again only when the local IP changes
_alarms = {"bw_down_mbps": bandwidth.LimitAlarm(), "bw_up_mbps": bandwidth.LimitAlarm()}
_today = {"day": None, "bytes": 0, "cap_level": 0}      # today's use, saved and not yet saved
_unsaved = [0, 0]                               # bytes received and sent since the last flush_usage
_unsaved_lock = threading.Lock()                # bandwidth_sample (UI thread) and flush_usage (a worker) share it


def settings():
    """The saved settings, with the default for any never saved."""
    return config.SETTING_DEFAULTS | store.get_settings()


def save_settings(values):
    """Admin: save settings from {key: text}. Each must be a number of 0 or more (0 = no limit);
    the watch interval at least 1 minute."""
    require_admin()
    try:
        clean = {key: float(text) for key, text in values.items() if key in config.SETTING_DEFAULTS}
    except ValueError:
        clean = {}
    # `value >= minimum` is also False for NaN; isfinite refuses "inf", which would break Watch's timer.
    if not values or len(clean) != len(values) or not all(
            math.isfinite(value) and value >= config.SETTING_MINIMUMS.get(key, 0) for key, value in clean.items()):
        raise ValueError("Each limit must be a number of 0 or more (0 means no limit), "
                         "and the watch interval at least 1 minute.")
    store.save_settings(clean)
    _limits.update(settings())                  # the monitor uses the new limits from its next sample
    return dict(_limits)


def bandwidth_sample():
    """Bandwidth monitor, called once a second on the UI thread. It reads the adapter's byte counters only
    (about 5 ms, no network traffic). Returns a BandwidthSample, or None when there is no rate yet.

    A limit just passed comes back in sample.alerts; storing it takes longer, so the window does that in a worker.
    """
    ip = netinfo.get_local_ip()
    if ip != _adapter["ip"]:                    # first call, or another network: find the adapter again
        _adapter.update(ip=ip, name=netinfo.get_adapter(ip) if ip else None, meter=bandwidth.Meter())
    counters = bandwidth.read_counters(_adapter["name"]) if _adapter["name"] else None
    rates = _adapter["meter"].update(*counters, time.monotonic()) if counters else None
    if not rates:
        return None
    down, up, recv, sent = rates
    day = date.today().isoformat()
    if _today["day"] != day:                    # the first sample, or past midnight: start from today's saved total
        _today.update(day=day, bytes=store.get_usage(day), cap_level=0)
    _today["bytes"] += recv + sent
    with _unsaved_lock:
        _unsaved[0] += recv
        _unsaved[1] += sent
    if not _limits:
        _limits.update(settings())

    alerts = []
    for name, rate, key in (("Download", down, "bw_down_mbps"), ("Upload", up, "bw_up_mbps")):
        if _alarms[key].update(rate, _limits[key]):
            alerts.append(f"{name} above the {_limits[key]:g} Mbps limit for {config.BW_SUSTAIN_S} s: "
                          f"{bandwidth.rate_text(rate)}.")
    level = bandwidth.cap_level(_today["bytes"], _limits["bw_daily_gb"])
    if level > _today["cap_level"]:
        alerts.append(f"{level}% of today's {_limits['bw_daily_gb']:g} GB cap used: {_today['bytes'] / 1e9:.2f} GB.")
    _today["cap_level"] = level                 # a raised cap lowers the level, so the warning can come again
    return models.BandwidthSample(down, up, _today["bytes"], alerts)


def flush_usage():
    """Add the bytes counted since the last call to today's row of the usage table."""
    with _unsaved_lock:
        recv, sent = _unsaved
        _unsaved[:] = [0, 0]
    if recv or sent:
        # shortcut: bytes counted just before midnight and saved just after go to the new day (at most 10 s of traffic).
        store.add_usage(date.today().isoformat(), recv, sent)


def usage_today():
    """Bytes this PC received and sent today: the saved total plus what the monitor counted since."""
    day = date.today().isoformat()
    return _today["bytes"] if _today["day"] == day else store.get_usage(day)


# --- Watch mode -------------------------------------------------------------
_watch = watch.WatchState()


def start_watch():
    """Admin: start watch mode afresh. Its first check only records who is present."""
    global _watch
    require_admin()
    _watch = watch.WatchState()


def watch_tick():
    """Admin, one watch-mode check: scan, ping the router, store the changes as events, and return them.

    Also stores a presence row (up or down) for every known device, for its uptime.
    """
    found = scan()                                # checks the admin role and stores the scan
    network = _network_id(netinfo.get_network_info(), {d.ip: d.mac for d in found if d.mac})
    stored = {d.mac: d for d in _with_vendor(store.get_devices(network)) if d.mac}   # includes devices that left
    gateway = next((d for d in found if d.is_gateway), None)
    events = []

    def add(kind, severity, device, ip, detail):
        events.append(record_event(kind, severity, ip, device and device.mac, detail, network))

    seen = {d.mac: d.ip for d in found if d.mac}
    for kind, mac, ip in _watch.update(seen, {d.mac for d in found if d.mac and d.known}, gateway and gateway.mac):
        device = stored.get(mac)
        name = ", ".join(filter(None, [device.alias or device.hostname, ip or device.ip, device.vendor])) \
            if device else mac
        add(kind, watch.SEVERITY[kind], device, gateway.ip if kind == "gateway-mac-changed" else ip, {
            "new-device": f"New device joined: {name}.",
            "back-online": f"Back online: {name}.",
            "offline": f"Went offline: {name}.",
            "gateway-mac-changed": f"The router's MAC address changed to {mac}: a new router, or ARP spoofing.",
        }[kind])

    if gateway:                                   # the router judged against its own history (Step 7.4)
        base = statistics.baseline([rtt for p in store.get_pings(gateway.ip, network) for rtt in p.rtts_ms])
        result = run_ping(gateway.ip, config.DIAG_PINGS)
        if result.avg_ms is not None and base and statistics.is_spike(result.avg_ms, base):
            add("spike", "warning", gateway, gateway.ip,
                f"The router answered in {result.avg_ms:g} ms against a usual {base[0]:.1f} ms.")

    store.add_presence(network, datetime.now().isoformat(timespec="seconds"),
                       [(mac, mac in seen) for mac, device in stored.items() if device.known])
    return events


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


def login_lock_seconds():
    """Whole seconds until another sign-in attempt is allowed."""
    return max(0, math.ceil(_locked_until - time.monotonic()))


def login(username, password, admin_only=False):
    """Sign in. The same message for an unknown name and a wrong password, so neither is revealed."""
    global _user, _failures, _locked_until
    if wait := login_lock_seconds():
        raise ValueError(f"Too many attempts. Wait {wait} s.")
    row = store.get_user(username.strip().lower())
    # An unknown name is still hashed, so it takes as long as a wrong password and timing reveals nothing.
    salt, digest = (row["salt"], row["hash"]) if row else (bytes(16), b"")
    if not auth.verify_password(password, salt, digest) or row is None:
        _failures += 1
        if _failures >= config.LOGIN_MAX_FAILURES:
            _failures, _locked_until = 0, time.monotonic() + config.LOGIN_LOCK_S
        raise ValueError("Wrong username or password.")
    _failures = 0
    user = models.User(row["username"], row["role"])
    if admin_only and not user.is_admin:
        raise PermissionError("Sign in with an administrator account to continue.")
    _user = user
    return _user


_running = set()                      # every tracert and ping -t still running


def stop_all():
    """Stop every running tracert, ping -t and ping -n (a scan, a watch check). Called by sign-out and window
    close. A continuous ping stopped here is not stored: only its Stop button stores it."""
    for task in list(_running):       # a copy: a stopped trace removes itself from the set
        task.stop()
    _running.clear()
    pinger.stop_children()


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
