"""Feature 5 (Security Recommendations): turns scan and ping results into advice.

Pure rules over devices and their statistics; nothing here touches the
network. The thresholds are in config.py.
"""
import ipaddress

from netmonitor import config, models
from netmonitor.core import vendor
from netmonitor.models import Device, HostStats, Recommendation

_ORDER = {"critical": 0, "warning": 1, "info": 2}


def _is_weak(stats: HostStats, loss_limit: float) -> bool:
    """True when a host that replies loses too many packets or answers too slowly."""
    return stats.avg_ms is not None and (stats.loss_pct >= loss_limit or stats.avg_ms > config.LATENCY_WARN_MS)


def _arp_findings(arp, gateway, add):
    """One MAC answering for several IPs. If one of them is the gateway, that is what ARP poisoning looks like.

    ARP has no authentication (RFC 826), so any device can claim any IP address.
    """
    owners = {}
    for ip, mac in arp.items():
        owners.setdefault(mac, []).append(ip)
    for mac, ips in owners.items():
        if len(ips) < 2:
            continue
        ips = sorted(ips, key=ipaddress.ip_address)
        if gateway in ips:
            add("critical", "ARP spoofing", None, f"Possible ARP spoofing: the gateway shares MAC {mac}",
                f"{', '.join(ips)} all answer with the same MAC address. Traffic to the internet may be "
                "passing through another device (a man-in-the-middle).",
                "Disconnect unknown devices, restart the router, and change the Wi-Fi password.")
        else:
            add("warning", "ARP", None, f"{len(ips)} addresses share MAC {mac}",
                f"{', '.join(ips)} answer with one MAC. A Wi-Fi extender or a PC with two addresses does this harmlessly.",
                "Check that you recognise this device.")


def recommend(devices: list[Device], stats: list[HostStats],
              arp: dict[str, str] | None = None, gateway: str | None = None,
              ports: dict[str, list] | None = None) -> list[Recommendation]:
    """Every recommendation for the network, most severe first.

    arp: the live {ip: mac} table, and gateway: the gateway's IP. With them, ARP spoofing is checked too.
    ports: {ip: open ports} from the stored port checks.
    """
    by_ip = {s.ip: s for s in stats}
    found = []

    def add(severity, category, device, title, detail, action):
        found.append(Recommendation(severity, category, device and device.ip, title, detail, action))

    for d in devices:
        s = by_ip.get(d.ip)
        name = f"{d.hostname} ({d.ip})"
        has_replies = s is not None and s.avg_ms is not None
        measured = f"Packet loss {s.loss_pct:g}%, average latency {s.avg_ms:g} ms." if has_replies else ""

        # Unreachable hosts and weak connectivity: one finding per host, the worst that applies.
        if s and s.status == models.OFFLINE and d.is_gateway:
            add("critical", "Connectivity", d, f"The gateway {d.ip} is unreachable",
                "The router did not answer any ping. Every device loses its route out of the network.",
                "Restart the router and check its power and cables.")
        elif s and s.status == models.OFFLINE:
            add("warning", "Connectivity", d, f"{name} is unreachable",
                "The device did not answer any ping and has no ARP entry.",
                "Check its power and cable or Wi-Fi connection; it may have left the network.")
        elif s and d.is_gateway and _is_weak(s, config.GATEWAY_LOSS_WARN_PCT):
            add("warning", "Connectivity", d, f"The gateway {d.ip} is unstable",
                measured + " Every device on the network is affected.",
                "Check the router's load and Wi-Fi channel, and restart it if the problem stays.")
        elif s and not d.is_gateway and _is_weak(s, config.LOSS_WARN_PCT + 0.1):   # rule: loss above 5%
            add("warning", "Connectivity", d, f"Weak connectivity to {name}", measured,
                "Check signal strength, interference, or a congested link.")

        if not d.known:
            randomized = (" This device uses a randomized MAC address, so it can appear new on every network."
                          if d.mac and vendor.is_randomized(d.mac) else "")
            add("warning", "Access control", d, f"New device on the network: {name}",
                f"MAC address {d.mac} was not present in the first scan of this network." + randomized,
                "Confirm it belongs on the network; if not, change the Wi-Fi password. "
                "Phones that use randomized MAC addresses can appear as new.")
        if s and s.jitter_ms is not None and s.jitter_ms > config.JITTER_WARN_MS:
            add("info", "Performance", d, f"High jitter on {name}",
                f"Reply times vary by {s.jitter_ms:g} ms on average.",
                "Expect poor voice and video call quality on this device.")
        open_ports = (ports or {}).get(d.ip, [])
        risky = [p for p in open_ports if p["risk"] == "high"]
        if risky:
            add("critical", "Open ports", d,
                f"Risky port open on {name}: " + ", ".join(f"{p['service']} ({p['port']})" for p in risky),
                "These services send logins unencrypted or are common targets for worms and password guessing.",
                "Turn the service off if it is not needed, or block the port in the device's firewall.")
        if d.is_gateway and any(p["port"] == 80 for p in open_ports):
            add("info", "Open ports", d, "The router's admin page uses unencrypted HTTP",
                "Port 80 is open on the gateway, so its admin password crosses the network in plain text.",
                "Use the router's HTTPS admin page if it has one, and do not open it over public Wi-Fi.")
        if s and s.status == models.NO_ICMP:
            add("info", "Firewall", d, f"{name} does not answer ping",
                "The device is up (it answers ARP) but its firewall drops ICMP echo requests.",
                "No action needed; this is the default for Windows PCs.")

    _arp_findings(arp or {}, gateway, add)

    # General reminders, shown on every network.
    add("info", "Firewall", None, "Keep the firewall turned on",
        "A firewall blocks connections to services you did not mean to share.",
        "Keep the operating system firewall on for every device and block unused inbound ports.")
    add("info", "Passwords", None, "Use strong router and Wi-Fi passwords",
        "Default router passwords are public knowledge, and weak Wi-Fi passphrases can be guessed.",
        "Change the default router admin password; use WPA2 or WPA3 with a passphrase of 12 or more characters.")
    return sorted(found, key=lambda r: _ORDER[r.severity])   # stable sort: device order is kept within a severity
