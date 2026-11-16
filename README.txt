NETMONITOR
Network Monitoring and Performance Analysis System


Course : CCS 234 - Communications and Networking
School : West Visayas State University, CICT
Date   : December 2026


1. DESCRIPTION
--------------
NetMonitor is a Windows desktop application written in Python. It finds
the devices on the local network, tests their connectivity with ping,
measures latency and packet loss, keeps a history of the results, writes
a summary report, and gives basic security recommendations.


2. REQUIREMENTS
---------------
- Windows 10 or Windows 11
- Python 3.11 or newer (developed and tested on Python 3.13)
- A wired or Wi-Fi connection to a local network

Administrator rights are not needed.


3. INSTALLATION
---------------
Open PowerShell in the SourceCode folder and run:

    python -m venv .venv
    .\.venv\Scripts\Activate.ps1
    pip install -r requirements.txt

If PowerShell refuses to run Activate.ps1, run this once and try again:

    Set-ExecutionPolicy -Scope CurrentUser RemoteSigned

Packages installed from requirements.txt: customtkinter, matplotlib,
psutil, jinja2, reportlab, pytest, and their dependencies.


4. RUNNING THE APPLICATION
--------------------------
Option A: double-click SourceCode\run.bat
          On the first run it creates the virtual environment and
          installs the packages by itself, then opens the application.

Option B: from PowerShell in the SourceCode folder, with the virtual
          environment active:

    python main.py

Suggested first use:
  1. Open Devices and click "Scan network" (about 10 to 15 seconds).
  2. Select one or more devices and click "Ping selected", or
     double-click a device to ping it.
  3. Open Statistics and click "Refresh all".
  4. Open Reports and click "Generate report".
  5. Open Security to read the recommendations.


5. FEATURES
-----------
Feature 1 - Network Discovery (Devices view)
  Detects the local IP address, subnet mask, network range and default
  gateway, then lists the active devices with IP address, hostname and
  MAC address. Uses a parallel ICMP ping sweep and the ARP table.

Feature 2 - Connectivity Testing (Ping view)
  Pings one device or several selected devices. Shows each reply time,
  the minimum, average and maximum, and the packet loss percentage.

Feature 3 - Network Statistics (Statistics view)
  For every device: hostname, IP address, average latency, maximum
  latency, packet loss, jitter and status, computed from all stored
  ping results. Selecting a device charts its history.

Feature 4 - Network Report Generator (Reports view)
  Writes a report with the date and time, the devices detected, the
  latest ping results, the network performance summary and the security
  recommendations. Formats: HTML and CSV. Reports are saved in
  SourceCode\output.

Feature 5 - Security Recommendations (Security view)
  Weak connectivity alerts, unreachable hosts, an unstable or unreachable
  gateway, new devices that were not in the first scan, and firewall and
  password reminders, ordered by severity.

Additional features
  - Graphical interface built with CustomTkinter (Tkinter).
  - Dashboard with device count, reachable devices, average latency, a
    0 to 100 health score, a latency chart and the top recommendations.
  - A device that does not answer ping but answers ARP is reported as
    "No ICMP reply (host up)" instead of offline.
  - Results are stored in an SQLite database, so they remain after the
    application is closed.


6. RUNNING THE TESTS
--------------------
From PowerShell in the SourceCode folder, with the virtual environment
active:

    pytest -v

The tests cover address and gateway detection, ping output parsing, ARP
parsing, statistics, storage, report generation and the recommendation
rules. They do not need a network connection.


7. FOLDER CONTENTS
------------------
README.txt            this file
SourceCode\
  main.py             entry point
  run.bat             installs on first run, then starts the application
  requirements.txt    pinned package versions
  pytest.ini          test settings
  netmonitor\
    config.py         timeouts, thresholds and file locations
    models.py         records shared by all layers
    store.py          SQLite storage
    services.py       the only module the interface calls
    core\             networking logic: netinfo, discovery, pinger,
                      statistics, report_builder, advisor
    gui\              main window, views and widgets
    templates\        HTML report template
  tests\              pytest test files and saved command output
  data\               netmonitor.db is created here on first use
  output\             generated reports
Presentation\         presentation slides
VideoDemo\            demonstration video

The Documentation folder is submitted separately through Teams.


8. KNOWN LIMITATIONS
--------------------
- Windows only. The application reads the output of the Windows ping,
  arp and route commands.
- IPv4 only.
- A scan covers at most 254 addresses (a /24). On a larger network only
  the /24 that contains this PC is scanned.
- Hostnames are not always available. Many phones do not answer reverse
  DNS and are listed as "Unknown".
- Some networks, such as school or public Wi-Fi, block devices from
  seeing each other. A scan there may find only the gateway.
- Phones that use a randomized MAC address can be flagged as new devices.
- History is kept per network range. Two different networks that use the
  same range (for example two routers that both use 192.168.1.0/24)
  share one device list. To start clean, close the application and
  delete SourceCode\data\netmonitor.db.
- Scan only networks that you own or are allowed to test.
