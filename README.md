# Ned 👓 | Ultimate Network Monitor

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python)
![Platform](https://img.shields.io/badge/Platform-Windows-0078D6?style=for-the-badge&logo=windows)
![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)

**Ned** is a Python-based network utility tool designed for real-time monitoring, traffic analysis, and process management. Built with a cyberpunk-inspired UI, it combines the functionality of Task Manager, Wireshark, and NetLimiter into one lightweight dashboard.

---

## 📸 Screenshots

![Dashboard Screenshot](https://via.placeholder.com/800x400?text=Dashboard+Screenshot+Here)
![App Manager Screenshot](https://via.placeholder.com/800x400?text=App+Manager+Screenshot+Here)

---

## ⚡ Features

### 1. 📊 Real-Time Dashboard
- **Live Traffic Graph:** Visualizes download/upload speeds in real-time using `matplotlib`.
- **Session Tracking:** Tracks total data consumed (MB/GB) per session.
- **Panic Button:** Instant "Kill Switch" to sever all internet connections via the OS network adapter.

### 2. 🛡️ App Manager (Firewall Control)
- **Active Process Scan:** Identifies specific applications currently consuming bandwidth.
- **Force Quit:** Terminate processes directly from the UI.
- **Firewall Integration:** Block/Unblock internet access for specific apps using Windows Firewall rules (`netsh`).

### 3. 🔗 Connection Sniffer
- **Live Netstat:** Displays all active `ESTABLISHED` connections.
- **Process ID Mapping:** Maps connections to specific PIDs.
- **Copy-Paste UI:** Selectable IP addresses and ports for easy WHOIS lookups.

### 4. 📡 LAN Scanner
- **ARP Table Dump:** Scans the local network for connected devices.
- **Device Identification:** Lists IP, MAC Address, and connection type (Dynamic/Static).

---

## 🛠️ Installation

### Prerequisites
- Python 3.x
- Windows OS (Required for Firewall/Netsh commands)

### 1. Clone the repo
```bash
git clone [https://github.com/yourusername/Ned-Monitor.git](https://github.com/yourusername/Ned-Monitor.git)
cd Ned-Monitor
