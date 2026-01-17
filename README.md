Here is a clean, professional `README.md` for your GitHub. It matches the "cyber security student" vibe—technical but polished.

I’ve included a section for screenshots, badges, and the specific "Run as Admin" warnings.

---

```markdown
# Ned 👓 | Ultimate Network Monitor

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python)
![Platform](https://img.shields.io/badge/Platform-Windows-0078D6?style=for-the-badge&logo=windows)
![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)

**Ned** is a Python-based network utility tool designed for real-time monitoring, traffic analysis, and process management. Built with a cyberpunk-inspired UI, it combines the functionality of Task Manager, Wireshark, and NetLimiter into one lightweight dashboard.

---

## 📸 Screenshots

*(Add screenshots of your Dashboard and App Manager here)*

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

```

### 2. Install Dependencies

```bash
pip install customtkinter psutil matplotlib

```

---

## 🚀 Usage

**⚠️ IMPORTANT: You must run this app as Administrator.**
*Ned interacts with the Windows Firewall and Network Adapter. Without admin privileges, the "Block", "Unblock", and "Panic" features will fail.*

### Run from Source

```bash
# Open Command Prompt as Administrator
python ned.py

```

### Run as Executable

If you downloaded the `.exe` release:

1. Right-click `Ned.exe`
2. Select **Run as Administrator**

---

## 📦 Building from Source (EXE)

To compile Ned into a standalone executable file:

1. Install PyInstaller:
```bash
pip install pyinstaller auto-py-to-exe

```


2. Run the build command (Fixes `customtkinter` path issues):
```bash
pyinstaller --noconfirm --onefile --windowed --collect-all customtkinter --name "Ned Monitor" ned.py

```


3. Find your app in the `dist/` folder.

---

## 📝 Technical Details

* **GUI Framework:** `CustomTkinter` (Modernized Tkinter wrapper).
* **Network Logic:** `psutil` for packet headers and I/O counters.
* **Graphing:** `matplotlib` backend embedded in Tkinter canvas.
* **Blocking Logic:** Uses `subprocess` to execute `netsh advfirewall` commands, creating custom outbound rules named `Block_{App}_PythonTool`.

---

## ⚠️ Disclaimer

This tool is for educational and network management purposes. Blocking network connections or scanning networks you do not own may violate policies. Use responsibly.

---

### Author

**Heshan Jayakody** [🌐 Portfolio](https://hhjdev.xyz)

```

### How to use this:
1.  Create a file named `README.md` in your project folder.
2.  Paste the code above into it.
3.  Take 2 screenshots of your app (The Dashboard and the App Manager) and upload them to your repo, then replace the `*(Add screenshots...)*` line with the actual image links.

```
