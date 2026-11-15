"""Feature 1 (Discovery): find active devices with a ping sweep plus ARP table."""

import ipaddress
import re
import socket
import subprocess
from 