# Ned 👓 | Ultimate Network Monitor

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python)
![Platform](https://img.shields.io/badge/Platform-Windows-0078D6?style=for-the-badge&logo=windows)
![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)

**Ned** is a Python-based network utility tool designed for real-time monitoring, traffic analysis, and process management. It combines the functionality of Task Manager, Wireshark, and NetLimiter into one lightweight dashboard.

---


## ⚡ Features

### 1. 📊 Real-Time Dashboard
- **Live Traffic Graph:** Visualizes download/upload speeds in real-time.
- **Session Tracking:** Tracks total data consumed (MB/GB) per session.
- **Panic Button:** Instant "Kill Switch" (`ipconfig /release`) and "Restore" (`ipconfig /renew`) triggers.

### 2. 🛡️ App Manager
- **Active Process Scan:** Identifies specific applications currently consuming bandwidth.
- **Deep Inspection:** View detailed process stats (CPU, RAM, PID) with a click.
- **Firewall Integration:** Block/Unblock internet access for specific apps using Windows Firewall rules.

### 3. 🔗 Connection Sniffer
- **Live Netstat:** Displays all active `ESTABLISHED` connections.
- **GeoIP Lookup:** Automatically identifies the Country and ISP of remote connections.
- **Data Export:** Export connection logs to CSV for analysis.

### 4. 📡 LAN Scanner
- **ARP Table Dump:** Scans the local network for connected devices.
- **Device Identification:** Lists IP, MAC Address, and connection type.
- **Export:** Save scan results to CSV.

### 5. 🚀 Speed Test (New)
- **Integrated Benchmarking:** Measure Ping, Download, and Upload speeds directly within the app.

### 6. ⚙️ Settings
- **Theme Toggle:** Switch between Dark and Light modes.
- **Performance:** Adjust data refresh intervals.

---


## 🛠️ Installation

### Prerequisites
- Python 3.x
- Windows OS (Required for Firewall/Netsh commands)

### 1. Clone the repo

```bash
git clone https://github.com/hheshanj/ned-monitor.git
```
### 2. Install Dependencies

```bash
pip install customtkinter psutil matplotlib speedtest-cli requests
```
### 3. Usage
⭕ IMPORTANT: You must run this app as Administrator. Ned interacts with the Windows Firewall and Network Adapter.

```bash
# Open Command Prompt as Administrator
python main.py
```


---

## ❓ Troubleshooting

**Q: "Access Denied" or Firewall errors?**
A: You MUST run the terminal/script as **Administrator**. The app needs high-level privileges to modify firewall rules and release IP addresses.

**Q: Speed Test stuck on "Testing..."?**
A: This depends on your internet connection and the `speedtest-cli` server response time. Give it up to 30 seconds.

**Q: Graph not showing?**
A: Ensure you have `matplotlib` installed: `pip install matplotlib`.

---
⚠️ Disclaimer
This tool is for educational and network management purposes. Blocking network connections or scanning networks you do not own may violate policies. Use responsibly.


