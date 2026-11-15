"""The only module the GUI imports

Every function here can block for seconds, so views call them through gui.worker.run_async and never directly.
"""

from netmonitor.core import discovery, pinger, netinfo

validate_ip = pinger.validate_ip            #raises ValueError on bad input
network_info = netinfo.get_network_info     #Feature 1: local IP, range, gateway
run_ping = pinger.ping                      #Feature 2: one host
run_ping_many = pinger.ping_many            #Feature 2: several hosts

def scan(on_progress = None):
    """Feature 1: find every active device on the local network."""
    return discovery.discover(netinfo.get_network_info(), on_progress)