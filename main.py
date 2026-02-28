import customtkinter as ctk
import psutil
import threading
import time
import os
import re
import subprocess
import collections
import csv
import json
import sqlite3
import requests
import speedtest
from datetime import datetime
from tkinter import messagebox, filedialog
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import pystray
from PIL import Image

# Safe Import for Matplotlib
try:
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
except ImportError:
    messagebox.showerror("Missing Library", "Run: pip install matplotlib")
    exit()

# --- THEME CONFIG ---
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("green")

APP_VERSION = "1.3.0"

class ned(ctk.CTk):
    def __init__(self):
        super().__init__()

        # --- FONT CONFIG ---
        self.FONT_HEADER = ("Segoe UI", 26, "bold")
        self.FONT_SUBHEAD = ("Segoe UI", 16, "bold")
        self.FONT_BODY = ("Segoe UI", 12)
        self.FONT_MONO = ("Segoe UI", 12)
        self.FONT_BUTTON = ("Segoe UI", 13, "bold")

        # Window Setup
        self.title("Ned | Ultimate Network Monitor")
        self.geometry("1200x800")
        
        # Set icon
        try:
            ned_icon = Path(__file__).parent / "gls.ico"
            if ned_icon.exists():
                self.iconbitmap(str(ned_icon))
        except Exception:
            pass

        # System tray state
        self._tray_icon = None
        self._minimize_to_tray = True
        self._tray_speed_text = "DL: 0 B/s | UL: 0 B/s"
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # Bandwidth alerts
        self._alert_enabled = False
        self._alert_session_mb = 500  # Alert if session total exceeds this (MB)
        self._alert_speed_mbps = 10   # Alert if speed exceeds this (MB/s)
        self._alert_session_fired = False
        self._alert_speed_fired = False

        # Data usage history (SQLite)
        self._db_path = Path(__file__).parent / "ned_history.db"
        self._init_db()
        self._last_history_save = time.time()

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)  # Status bar row

        # --- CACHING & STATE ---
        self.geoip_cache = {}
        self.pending_geo_labels = collections.defaultdict(list)
        self.geo_executor = ThreadPoolExecutor(max_workers=5)
        self.monitor_active = True
        self.update_interval = 1000 # ms

        # Sortable data stores
        self.current_conns_data = []
        self.current_scan_data = []
        self.conns_sort_col = None
        self.conns_sort_reverse = False
        self.scan_sort_col = None
        self.scan_sort_reverse = False

        # App manager filter
        self.app_filter_var = ctk.StringVar()
        self.app_filter_var.trace_add("write", lambda *_: self._apply_app_filter())
        self._cached_active_apps = {}

        # Per-app bandwidth tracking
        self._app_bw_data = {}  # {pid: {name, sent, recv, last_sent, last_recv, send_rate, recv_rate}}
        self._app_bw_tracking = False
        self._app_bw_sort_col = 2  # Default sort by recv_rate (download)
        self._app_bw_sort_reverse = True

        # Ping monitor state
        self._ping_active = False
        self._ping_target = "8.8.8.8"
        self._ping_data = collections.deque([0]*60, maxlen=60)
        self._ping_x = list(range(60))

        # Network interface selection
        self._selected_interface = None  # None = all interfaces

        # --- TABS ---
        self.tabview = ctk.CTkTabview(self, command=self.on_tab_change)
        self.tabview.grid(row=0, column=0, padx=20, pady=(20, 5), sticky="nsew")
        self.tabview._segmented_button.configure(font=self.FONT_BUTTON) 
        
        self.tab_dash = self.tabview.add("Dashboard")
        self.tab_bw = self.tabview.add("Bandwidth")
        self.tab_apps = self.tabview.add("App Manager")
        self.tab_conn = self.tabview.add("Connections")
        self.tab_scan = self.tabview.add("LAN Scanner")
        self.tab_dns = self.tabview.add("DNS")
        self.tab_ping = self.tabview.add("Ping")
        self.tab_speed = self.tabview.add("Speed Test")
        self.tab_history = self.tabview.add("History")
        self.tab_settings = self.tabview.add("Settings")

        # --- STATUS BAR ---
        self.status_bar = ctk.CTkLabel(self, text="Ready.", font=("Segoe UI", 11), 
                                        text_color="#888888", anchor="w")
        self.status_bar.grid(row=1, column=0, padx=25, pady=(0, 10), sticky="ew")
        
        # Setup Views
        self.setup_dashboard()
        self.setup_bandwidth()
        self.setup_app_manager()
        self.setup_connections()
        self.setup_scanner()
        self.setup_dns()
        self.setup_ping()
        self.setup_speedtest()
        self.setup_history()
        self.setup_settings()

        # --- KEYBOARD SHORTCUTS ---
        self.bind("<F5>", lambda e: self._shortcut_refresh())
        self.bind("<Control-e>", lambda e: self._shortcut_export())
        self.bind("<Escape>", lambda e: self._shortcut_escape())

        # Data for Graphs
        self.x_data = list(range(60))
        self.y_dl = collections.deque([0]*60, maxlen=60)
        self.y_ul = collections.deque([0]*60, maxlen=60)
        
        # --- INIT TRACKING ---
        net_io = psutil.net_io_counters()
        self.start_upload = net_io.bytes_sent
        self.start_download = net_io.bytes_recv
        
        self.last_upload = self.start_upload
        self.last_download = self.start_download
        self.last_time = time.time()
        
        # Start Loop
        self.monitor_loop()

    def set_status(self, text):
        """Update the status bar text."""
        self.status_bar.configure(text=text)

    def on_tab_change(self):
        """Auto-refresh data when switching tabs."""
        current = self.tabview.get()
        # Bandwidth tracking on/off
        if current == "Bandwidth":
            self._start_bw_tracking()
        else:
            self._stop_bw_tracking()
        # Ping tracking on/off
        if current == "Ping":
            self._start_ping()
        else:
            self._stop_ping()
        
        if current == "App Manager":
            self.set_status("🔄 Refreshing App Manager...")
            self.refresh_all_apps()
        elif current == "Connections":
            self.set_status("🔄 Fetching connections...")
            self.get_conns()
        elif current == "LAN Scanner":
            self.set_status("📡 Scanning local network...")
            self.run_scan()
        elif current == "DNS":
            self._refresh_dns()
        elif current == "History":
            self._render_history()

    # ==========================
    # KEYBOARD SHORTCUTS
    # ==========================
    def _shortcut_refresh(self):
        """F5 refreshes the current tab."""
        current = self.tabview.get()
        refresh_map = {
            "App Manager": self.refresh_all_apps,
            "Connections": self.get_conns,
            "LAN Scanner": self.run_scan,
            "DNS": self._refresh_dns,
            "Bandwidth": self._bw_refresh_now,
            "History": self._render_history,
        }
        if current in refresh_map:
            refresh_map[current]()
            self.set_status(f"🔄 Refreshed {current}.")

    def _shortcut_export(self):
        """Ctrl+E exports data for the current tab."""
        current = self.tabview.get()
        export_map = {
            "Connections": "connections",
            "LAN Scanner": "scanner",
            "Bandwidth": "bandwidth",
        }
        if current in export_map:
            self.export_data(export_map[current])

    def _shortcut_escape(self):
        """Escape closes topmost dialog."""
        for widget in self.winfo_children():
            if isinstance(widget, ctk.CTkToplevel):
                widget.destroy()
                return

    # ==========================
    # TOOLTIP HELPER
    # ==========================
    def _add_tooltip(self, widget, text):
        """Add a hover tooltip to a widget."""
        tip = None
        def show(event):
            nonlocal tip
            tip = ctk.CTkToplevel(self)
            tip.wm_overrideredirect(True)
            tip.geometry(f"+{event.x_root + 10}+{event.y_root + 10}")
            lbl = ctk.CTkLabel(tip, text=text, font=("Segoe UI", 11), 
                              fg_color="#333333", corner_radius=4, 
                              padx=8, pady=4, text_color="white")
            lbl.pack()
        def hide(event):
            nonlocal tip
            if tip:
                tip.destroy()
                tip = None
        widget.bind("<Enter>", show)
        widget.bind("<Leave>", hide)

    # ==========================
    # DATA USAGE HISTORY (SQLite)
    # ==========================
    def _init_db(self):
        """Initialize the SQLite database for data usage history."""
        conn = sqlite3.connect(str(self._db_path))
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS daily_usage (
            date TEXT PRIMARY KEY,
            download_bytes INTEGER DEFAULT 0,
            upload_bytes INTEGER DEFAULT 0
        )''')
        conn.commit()
        conn.close()

    def setup_history(self):
        self.tab_history.grid_columnconfigure(0, weight=1)
        self.tab_history.grid_rowconfigure(0, weight=0)
        self.tab_history.grid_rowconfigure(1, weight=1)

        top = ctk.CTkFrame(self.tab_history, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=10, pady=10)

        ctk.CTkButton(top, text="💾 Save Current Session", font=self.FONT_BUTTON,
                       command=self._save_session_to_db).pack(side="left", padx=5)
        ctk.CTkButton(top, text="🔄 Refresh Chart", font=self.FONT_BUTTON, fg_color="#444444",
                       command=self._render_history).pack(side="left", padx=5)

        # Matplotlib chart
        self.hist_fig = Figure(figsize=(5, 3), dpi=100, facecolor='#2b2b2b')
        self.hist_ax = self.hist_fig.add_subplot(111)
        self.hist_canvas = FigureCanvasTkAgg(self.hist_fig, master=self.tab_history)
        self.hist_canvas.get_tk_widget().grid(row=1, column=0, sticky="nsew", padx=10, pady=10)

    def _save_session_to_db(self):
        """Save current session data to the database."""
        net_io = psutil.net_io_counters()
        session_dl = net_io.bytes_recv - self.start_download
        session_ul = net_io.bytes_sent - self.start_upload
        today = datetime.now().strftime("%Y-%m-%d")

        try:
            conn = sqlite3.connect(str(self._db_path))
            c = conn.cursor()
            c.execute('''INSERT INTO daily_usage (date, download_bytes, upload_bytes)
                         VALUES (?, ?, ?)
                         ON CONFLICT(date) DO UPDATE SET
                         download_bytes = download_bytes + excluded.download_bytes,
                         upload_bytes = upload_bytes + excluded.upload_bytes''',
                      (today, session_dl, session_ul))
            conn.commit()
            conn.close()
            
            # Reset session start to avoid double-counting
            self.start_download = net_io.bytes_recv
            self.start_upload = net_io.bytes_sent
            
            self.set_status(f"💾 Session data saved for {today}.")
            self._render_history()
        except Exception as e:
            self.set_status(f"\u274c DB error: {e}")

    def _auto_save_history(self):
        """Periodically save session data (called from monitor_loop)."""
        now = time.time()
        if now - self._last_history_save >= 300:  # Every 5 minutes
            self._last_history_save = now
            net_io = psutil.net_io_counters()
            session_dl = net_io.bytes_recv - self.start_download
            session_ul = net_io.bytes_sent - self.start_upload
            if session_dl > 0 or session_ul > 0:
                today = datetime.now().strftime("%Y-%m-%d")
                try:
                    conn = sqlite3.connect(str(self._db_path))
                    c = conn.cursor()
                    c.execute('''INSERT INTO daily_usage (date, download_bytes, upload_bytes)
                                 VALUES (?, ?, ?)
                                 ON CONFLICT(date) DO UPDATE SET
                                 download_bytes = download_bytes + excluded.download_bytes,
                                 upload_bytes = upload_bytes + excluded.upload_bytes''',
                              (today, session_dl, session_ul))
                    conn.commit()
                    conn.close()
                    self.start_download = net_io.bytes_recv
                    self.start_upload = net_io.bytes_sent
                except Exception:
                    pass

    def _render_history(self):
        """Render the 7-day usage bar chart."""
        self.hist_ax.clear()
        self.hist_ax.set_facecolor('#2b2b2b')
        self.hist_ax.tick_params(colors='white', labelcolor='white', labelsize=8)
        self.hist_ax.spines['bottom'].set_color('white')
        self.hist_ax.spines['left'].set_color('white')
        self.hist_ax.spines['top'].set_visible(False)
        self.hist_ax.spines['right'].set_visible(False)
        self.hist_ax.set_ylabel("MB", color='white', fontsize=10)
        self.hist_ax.set_title("Daily Data Usage (Last 7 Days)", color='white', fontsize=12)

        try:
            conn = sqlite3.connect(str(self._db_path))
            c = conn.cursor()
            c.execute('''SELECT date, download_bytes, upload_bytes FROM daily_usage 
                         ORDER BY date DESC LIMIT 7''')
            rows = c.fetchall()
            conn.close()
        except Exception:
            rows = []

        if not rows:
            self.hist_ax.text(0.5, 0.5, "No history data yet.\nClick 'Save Current Session' to start logging.",
                             ha='center', va='center', color='gray', fontsize=11,
                             transform=self.hist_ax.transAxes)
            self.hist_canvas.draw()
            return

        rows.reverse()  # Chronological order
        dates = [r[0][-5:] for r in rows]  # MM-DD format
        dl_mb = [r[1] / (1024 * 1024) for r in rows]
        ul_mb = [r[2] / (1024 * 1024) for r in rows]

        import numpy as np
        x = np.arange(len(dates))
        width = 0.35

        self.hist_ax.bar(x - width/2, dl_mb, width, label='Download', color='#00ff00', alpha=0.8)
        self.hist_ax.bar(x + width/2, ul_mb, width, label='Upload', color='#ff9900', alpha=0.8)
        self.hist_ax.set_xticks(x)
        self.hist_ax.set_xticklabels(dates, color='white')
        self.hist_ax.legend(facecolor='#2b2b2b', labelcolor='white', prop={'size': 9})

        self.hist_fig.tight_layout()
        self.hist_canvas.draw()
        self.set_status("📊 History chart updated.")

    # ==========================
    # TAB: DNS MONITOR
    # ==========================
    def setup_dns(self):
        self.tab_dns.grid_columnconfigure(0, weight=1)
        self.tab_dns.grid_rowconfigure(0, weight=0)
        self.tab_dns.grid_rowconfigure(1, weight=1)

        top = ctk.CTkFrame(self.tab_dns, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=10, pady=10)

        ctk.CTkButton(top, text="🔄 Refresh DNS Cache", font=self.FONT_BUTTON,
                       command=self._refresh_dns).pack(side="left", padx=5)
        ctk.CTkButton(top, text="🧹 Flush DNS", font=self.FONT_BUTTON, fg_color="#cf0000",
                       hover_color="#8a0000", command=self._flush_dns).pack(side="left", padx=5)
        ctk.CTkButton(top, text="💾 Export CSV", font=self.FONT_BUTTON, fg_color="#444444",
                       command=lambda: self.export_data("dns")).pack(side="left", padx=5)
        
        self.dns_count_label = ctk.CTkLabel(top, text="0 entries", font=self.FONT_BODY, text_color="gray")
        self.dns_count_label.pack(side="right", padx=10)

        self.dns_scroll = ctk.CTkScrollableFrame(self.tab_dns, fg_color="transparent")
        self.dns_scroll.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        self.current_dns_data = []

    def _refresh_dns(self):
        """Parse Windows DNS cache."""
        for w in self.dns_scroll.winfo_children(): w.destroy()
        self.current_dns_data = []
        self.set_status("🔍 Reading DNS cache...")

        def _fetch():
            entries = []
            try:
                result = subprocess.run('ipconfig /displaydns', capture_output=True, text=True,
                                        creationflags=subprocess.CREATE_NO_WINDOW)
                current_name = ""
                current_type = ""
                current_data = ""
                for line in result.stdout.splitlines():
                    line = line.strip()
                    if "Record Name" in line:
                        current_name = line.split(":")[-1].strip()
                    elif "Record Type" in line:
                        val = line.split(":")[-1].strip()
                        type_map = {"1": "A", "5": "CNAME", "28": "AAAA"}
                        current_type = type_map.get(val, val)
                    elif "A (Host) Record" in line or "AAAA" in line or "CNAME" in line:
                        current_data = line.split(":")[-1].strip()
                    elif line == "" and current_name:
                        if current_data:
                            entries.append([current_name, current_type, current_data])
                        current_name = current_type = current_data = ""
            except Exception:
                pass
            self.after(0, lambda: self._render_dns(entries))

        threading.Thread(target=_fetch, daemon=True).start()

    def _render_dns(self, entries):
        for w in self.dns_scroll.winfo_children(): w.destroy()
        self.current_dns_data = entries
        self.dns_count_label.configure(text=f"{len(entries)} entries")

        if not entries:
            ctk.CTkLabel(self.dns_scroll, text="DNS cache is empty.", font=self.FONT_BODY,
                         text_color="gray").pack(pady=20)
            return

        for name, rtype, data in entries:
            card = ctk.CTkFrame(self.dns_scroll, fg_color="#2b2b2b", corner_radius=4)
            card.pack(fill="x", pady=1, padx=2)
            ctk.CTkLabel(card, text=name, width=300, font=self.FONT_MONO, 
                         text_color="white", anchor="w").pack(side="left", padx=8, pady=4)
            ctk.CTkLabel(card, text=rtype, width=60, font=self.FONT_MONO,
                         text_color="#00ccff", anchor="w").pack(side="left", padx=4)
            ctk.CTkLabel(card, text=data, width=200, font=self.FONT_MONO,
                         text_color="#88ff88", anchor="w").pack(side="left", padx=4)
        self.set_status(f"🔍 Found {len(entries)} DNS cache entries.")

    def _flush_dns(self):
        confirm = messagebox.askyesno("Flush DNS", "Clear the Windows DNS resolver cache?")
        if not confirm:
            return
        try:
            subprocess.run('ipconfig /flushdns', shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
            self.set_status("🧹 DNS cache flushed.")
            self._refresh_dns()
        except Exception:
            self.set_status("\u274c Failed to flush DNS.")

    # ==========================
    # TAB: PING MONITOR
    # ==========================
    def setup_ping(self):
        self.tab_ping.grid_columnconfigure(0, weight=1)
        self.tab_ping.grid_rowconfigure(0, weight=0)
        self.tab_ping.grid_rowconfigure(1, weight=1)

        top = ctk.CTkFrame(self.tab_ping, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=10, pady=10)

        ctk.CTkLabel(top, text="Target:", font=self.FONT_BODY).pack(side="left", padx=(10, 5))
        self.ping_entry = ctk.CTkEntry(top, width=150, placeholder_text="8.8.8.8")
        self.ping_entry.insert(0, "8.8.8.8")
        self.ping_entry.pack(side="left", padx=5)

        self.ping_btn = ctk.CTkButton(top, text="▶ Start Ping", font=self.FONT_BUTTON,
                                       command=self._toggle_ping_btn)
        self.ping_btn.pack(side="left", padx=10)

        self.ping_stat_label = ctk.CTkLabel(top, text="--", font=("Segoe UI", 14, "bold"), text_color="#00ccff")
        self.ping_stat_label.pack(side="right", padx=15)

        # Matplotlib ping chart
        self.ping_fig = Figure(figsize=(5, 3), dpi=100, facecolor='#2b2b2b')
        self.ping_ax = self.ping_fig.add_subplot(111)
        self.ping_ax.set_facecolor('#2b2b2b')
        self.ping_ax.tick_params(colors='white', labelcolor='white', labelsize=8)
        self.ping_ax.spines['bottom'].set_color('white')
        self.ping_ax.spines['left'].set_color('white')
        self.ping_ax.spines['top'].set_visible(False)
        self.ping_ax.spines['right'].set_visible(False)
        self.ping_ax.set_xlabel("Samples", color='white', fontsize=9)
        self.ping_ax.set_ylabel("ms", color='white', fontsize=9)
        self.ping_ax.set_title("Latency (ms)", color='white', fontsize=11)

        self.ping_line, = self.ping_ax.plot([], [], color='#00ccff', linewidth=2)
        self.ping_ax.grid(True, color='#444444', linestyle='--', linewidth=0.5)

        self.ping_canvas = FigureCanvasTkAgg(self.ping_fig, master=self.tab_ping)
        self.ping_canvas.get_tk_widget().grid(row=1, column=0, sticky="nsew", padx=10, pady=10)

    def _toggle_ping_btn(self):
        if self._ping_active:
            self._stop_ping()
        else:
            self._start_ping()

    def _start_ping(self):
        if self._ping_active:
            return
        self._ping_target = self.ping_entry.get().strip() or "8.8.8.8"
        self._ping_active = True
        self.ping_btn.configure(text="\u23f9 Stop Ping", fg_color="#cf0000")
        self.set_status(f"🏓 Pinging {self._ping_target}...")
        self._ping_loop()

    def _stop_ping(self):
        self._ping_active = False
        if hasattr(self, 'ping_btn'):
            self.ping_btn.configure(text="\u25b6 Start Ping", fg_color=["#2CC985", "#2FA572"])

    def _ping_loop(self):
        if not self._ping_active:
            return
        threading.Thread(target=self._do_ping, daemon=True).start()
        self.after(1000, self._ping_loop)

    def _do_ping(self):
        try:
            result = subprocess.run(
                f'ping -n 1 -w 1000 {self._ping_target}',
                capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW
            )
            output = result.stdout
            latency = -1.0
            for line in output.splitlines():
                if 'time=' in line.lower():
                    import re
                    m = re.search(r'time[=<](\d+)', line, re.IGNORECASE)
                    if m:
                        latency = float(m.group(1))
                    break
            
            if latency >= 0:
                self._ping_data.append(latency)
            else:
                self._ping_data.append(0)
            
            self.after(0, lambda lat=latency: self._update_ping_ui(lat))
        except Exception:
            self._ping_data.append(0)

    def _update_ping_ui(self, latency):
        if latency >= 0:
            color = "#00ff00" if latency < 50 else "#ff9900" if latency < 100 else "#ff0000"
            self.ping_stat_label.configure(text=f"{latency:.0f} ms", text_color=color)
        else:
            self.ping_stat_label.configure(text="Timeout", text_color="red")

        self.ping_line.set_data(self._ping_x, list(self._ping_data))
        peak = max(max(self._ping_data), 10)
        self.ping_ax.set_ylim(0, peak * 1.2)
        self.ping_ax.set_xlim(0, 59)
        self.ping_canvas.draw()

    # ==========================
    # TAB: BANDWIDTH TRACKER
    # ==========================
    def setup_bandwidth(self):
        self.tab_bw.grid_columnconfigure(0, weight=1)
        self.tab_bw.grid_rowconfigure(0, weight=0)
        self.tab_bw.grid_rowconfigure(1, weight=0)
        self.tab_bw.grid_rowconfigure(2, weight=1)

        # Top bar
        top = ctk.CTkFrame(self.tab_bw, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=10, pady=5)
        
        ctk.CTkButton(top, text="🔄 Refresh", font=self.FONT_BUTTON, 
                       command=self._bw_refresh_now).pack(side="left", padx=5)
        ctk.CTkButton(top, text="💾 Export CSV", font=self.FONT_BUTTON, fg_color="#444444",
                       command=lambda: self.export_data("bandwidth")).pack(side="left", padx=5)
        
        self.bw_status_label = ctk.CTkLabel(top, text="⏸ Not tracking", font=self.FONT_BODY, text_color="gray")
        self.bw_status_label.pack(side="right", padx=10)

        # Headers (sortable)
        h_frame = ctk.CTkFrame(self.tab_bw, height=30, fg_color="#1a1a1a")
        h_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(5, 0))

        bw_headers = [
            ("PROCESS", 180, 0), ("PID", 60, 1), 
            ("⬇ DL SPEED", 110, 2), ("⬆ UL SPEED", 110, 3),
            ("TOTAL RECV", 110, 4), ("TOTAL SENT", 110, 5),
        ]
        for text, width, col_idx in bw_headers:
            btn = ctk.CTkButton(h_frame, text=f"{text} ↕", width=width, height=25,
                                font=("Segoe UI", 11, "bold"), fg_color="#1a1a1a", hover_color="#333333",
                                anchor="w", command=lambda c=col_idx: self._sort_bw(c))
            btn.pack(side="left", padx=4)

        # Scrollable results
        self.bw_scroll = ctk.CTkScrollableFrame(self.tab_bw, fg_color="transparent")
        self.bw_scroll.grid(row=2, column=0, sticky="nsew", padx=10, pady=5)

    def _start_bw_tracking(self):
        """Start the per-app bandwidth tracking loop."""
        if self._app_bw_tracking:
            return
        self._app_bw_tracking = True
        self.bw_status_label.configure(text="▶ Live tracking", text_color="#00ff00")
        self.set_status("📊 Per-app bandwidth tracking started.")
        self._bw_track_loop()

    def _stop_bw_tracking(self):
        """Stop the per-app bandwidth tracking loop."""
        self._app_bw_tracking = False
        if hasattr(self, 'bw_status_label'):
            self.bw_status_label.configure(text="⏸ Paused (switch to tab to resume)", text_color="gray")

    def _bw_refresh_now(self):
        """Manual refresh of bandwidth data."""
        self._bw_sample()
        self._render_bw()

    def _bw_track_loop(self):
        """Background loop that samples bandwidth every 2 seconds."""
        if not self._app_bw_tracking:
            return
        threading.Thread(target=self._bw_sample_thread, daemon=True).start()
        self.after(2000, self._bw_track_loop)

    def _bw_sample_thread(self):
        """Sample per-app bandwidth in a background thread and render on main thread."""
        self._bw_sample()
        self.after(0, self._render_bw)

    def _bw_sample(self):
        """Take a snapshot of per-process network IO."""
        current_snapshot = {}  # pid -> {name, sent, recv}
        
        try:
            connections = psutil.net_connections(kind='inet')
        except (psutil.AccessDenied, PermissionError):
            return
        
        # Get unique PIDs with connections
        active_pids = set()
        for c in connections:
            if c.pid and c.status == 'ESTABLISHED':
                active_pids.add(c.pid)

        for pid in active_pids:
            try:
                p = psutil.Process(pid)
                io = p.io_counters()
                current_snapshot[pid] = {
                    'name': p.name(),
                    'sent': io.write_bytes,
                    'recv': io.read_bytes,
                }
            except (psutil.NoSuchProcess, psutil.AccessDenied, AttributeError):
                pass

        # Calculate rates
        new_data = {}
        for pid, snap in current_snapshot.items():
            if pid in self._app_bw_data:
                old = self._app_bw_data[pid]
                dt = 2.0  # seconds between samples
                send_rate = max(0, (snap['sent'] - old.get('last_sent', snap['sent'])) / dt)
                recv_rate = max(0, (snap['recv'] - old.get('last_recv', snap['recv'])) / dt)
                new_data[pid] = {
                    'name': snap['name'],
                    'sent': snap['sent'],
                    'recv': snap['recv'],
                    'last_sent': snap['sent'],
                    'last_recv': snap['recv'],
                    'send_rate': send_rate,
                    'recv_rate': recv_rate,
                }
            else:
                new_data[pid] = {
                    'name': snap['name'],
                    'sent': snap['sent'],
                    'recv': snap['recv'],
                    'last_sent': snap['sent'],
                    'last_recv': snap['recv'],
                    'send_rate': 0,
                    'recv_rate': 0,
                }
        self._app_bw_data = new_data

    def _render_bw(self):
        """Render the per-app bandwidth list."""
        for w in self.bw_scroll.winfo_children():
            w.destroy()

        if not self._app_bw_data:
            ctk.CTkLabel(self.bw_scroll, text="No apps with active connections detected.",
                         font=self.FONT_BODY, text_color="gray").pack(pady=20)
            return

        # Build sortable rows: [name, pid, recv_rate, send_rate, total_recv, total_sent]
        rows = []
        for pid, d in self._app_bw_data.items():
            rows.append([
                d['name'], pid,
                d['recv_rate'], d['send_rate'],
                d['recv'], d['sent'],
            ])

        # Sort
        try:
            rows.sort(key=lambda r: r[self._app_bw_sort_col], reverse=self._app_bw_sort_reverse)
        except (IndexError, TypeError):
            pass

        for row in rows:
            name, pid, recv_rate, send_rate, total_recv, total_sent = row
            
            card = ctk.CTkFrame(self.bw_scroll, fg_color="#2b2b2b", corner_radius=6)
            card.pack(fill="x", pady=2, padx=2)

            # Process name
            ctk.CTkLabel(card, text=f"📦 {name}", width=180, font=self.FONT_BODY, 
                         anchor="w").pack(side="left", padx=8, pady=6)
            # PID
            ctk.CTkLabel(card, text=str(pid), width=60, font=self.FONT_MONO,
                         text_color="gray", anchor="w").pack(side="left", padx=4)
            # DL speed
            dl_color = "#00ff00" if recv_rate > 0 else "#555555"
            ctk.CTkLabel(card, text=self.format_speed(recv_rate), width=110, font=self.FONT_MONO,
                         text_color=dl_color, anchor="w").pack(side="left", padx=4)
            # UL speed  
            ul_color = "#ff9900" if send_rate > 0 else "#555555"
            ctk.CTkLabel(card, text=self.format_speed(send_rate), width=110, font=self.FONT_MONO,
                         text_color=ul_color, anchor="w").pack(side="left", padx=4)
            # Total recv
            ctk.CTkLabel(card, text=self.format_bytes(total_recv), width=110, font=self.FONT_MONO,
                         text_color="#88ff88", anchor="w").pack(side="left", padx=4)
            # Total sent
            ctk.CTkLabel(card, text=self.format_bytes(total_sent), width=110, font=self.FONT_MONO,
                         text_color="#ffcc88", anchor="w").pack(side="left", padx=4)

    def _sort_bw(self, col_idx):
        """Sort bandwidth data by column."""
        if self._app_bw_sort_col == col_idx:
            self._app_bw_sort_reverse = not self._app_bw_sort_reverse
        else:
            self._app_bw_sort_col = col_idx
            self._app_bw_sort_reverse = True  # Default descending for bandwidth
        self._render_bw()

    # ==========================
    # TAB 1: DASHBOARD
    # ==========================
    def setup_dashboard(self):
        self.tab_dash.grid_columnconfigure((0, 1), weight=1)
        self.tab_dash.grid_rowconfigure(2, weight=1)
        
        # --- Speed Labels ---
        self.dl_label = ctk.CTkLabel(self.tab_dash, text="⬇ 0 B/s", font=self.FONT_HEADER, text_color="#00ff00")
        self.dl_label.grid(row=0, column=0, pady=(20, 5))
        
        self.ul_label = ctk.CTkLabel(self.tab_dash, text="⬆ 0 B/s", font=self.FONT_HEADER, text_color="#ff9900")
        self.ul_label.grid(row=0, column=1, pady=(20, 5))

        # --- Session Totals ---
        self.total_dl_label = ctk.CTkLabel(self.tab_dash, text="Total: 0 B", font=self.FONT_BODY, text_color="#88ff88")
        self.total_dl_label.grid(row=1, column=0, pady=(0, 20))
        
        self.total_ul_label = ctk.CTkLabel(self.tab_dash, text="Total: 0 B", font=self.FONT_BODY, text_color="#ffcc88")
        self.total_ul_label.grid(row=1, column=1, pady=(0, 20))

        # --- Graph ---
        self.fig = Figure(figsize=(5, 3), dpi=100, facecolor='#2b2b2b')
        self.ax = self.fig.add_subplot(111)
        self.ax.set_facecolor('#2b2b2b')
        self.ax.tick_params(colors='white', labelcolor='white', labelsize=8)
        self.ax.spines['bottom'].set_color('white')
        self.ax.spines['left'].set_color('white')
        self.ax.spines['top'].set_visible(False)
        self.ax.spines['right'].set_visible(False)
        self.ax.set_xlabel("Time (s)", color='white', fontsize=9)
        self.ax.set_ylabel("KB/s", color='white', fontsize=9)
        
        self.line_dl, = self.ax.plot([], [], color='#00ff00', linewidth=2, label='Download')
        self.line_ul, = self.ax.plot([], [], color='#ff9900', linewidth=2, label='Upload')
        self.ax.legend(facecolor='#2b2b2b', labelcolor='white', prop={'family': 'Segoe UI', 'size': 10})
        self.ax.grid(True, color='#444444', linestyle='--', linewidth=0.5)
        
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.tab_dash)
        self.canvas.get_tk_widget().grid(row=2, column=0, columnspan=2, sticky="nsew", padx=10, pady=10)

        # --- Buttons Frame ---
        btn_frame = ctk.CTkFrame(self.tab_dash, fg_color="transparent")
        btn_frame.grid(row=3, column=0, columnspan=2, pady=20)

        # Kill Switch
        self.kill_btn = ctk.CTkButton(btn_frame, text="💀 PANIC (KILL INTERNET)", font=self.FONT_BUTTON, 
                                      fg_color="#cf0000", hover_color="#8a0000", height=40, width=200, command=self.kill_switch)
        self.kill_btn.pack(side="left", padx=10)

        # Restore Button
        self.restore_btn = ctk.CTkButton(btn_frame, text="🩹 RESTORE INTERNET", font=self.FONT_BUTTON, 
                                      fg_color="#009900", hover_color="#006600", height=40, width=200, command=self.restore_internet)
        self.restore_btn.pack(side="left", padx=10)

    # ==========================
    # TAB 2: APP MANAGER
    # ==========================
    def setup_app_manager(self):
        self.tab_apps.grid_columnconfigure((0, 1), weight=1)
        self.tab_apps.grid_rowconfigure(2, weight=1)
        
        # Controls
        self.control_frame = ctk.CTkFrame(self.tab_apps, fg_color="transparent")
        self.control_frame.grid(row=0, column=0, columnspan=2, padx=10, pady=5, sticky="ew")
        
        self.refresh_btn = ctk.CTkButton(self.control_frame, text="🔄 Refresh Lists", font=self.FONT_BUTTON, command=self.refresh_all_apps)
        self.refresh_btn.pack(side="left", padx=0, pady=10)
        
        ctk.CTkLabel(self.control_frame, text="⚠️ Admin Required", font=self.FONT_BODY, text_color="orange").pack(side="right", padx=10)

        # Search / Filter
        search_frame = ctk.CTkFrame(self.tab_apps, fg_color="transparent")
        search_frame.grid(row=1, column=0, columnspan=2, padx=10, pady=(0, 5), sticky="ew")
        
        ctk.CTkLabel(search_frame, text="🔍", font=self.FONT_BODY).pack(side="left", padx=(10, 5))
        self.app_search_entry = ctk.CTkEntry(search_frame, placeholder_text="Filter by process name...",
                                              textvariable=self.app_filter_var, width=300)
        self.app_search_entry.pack(side="left", padx=5)

        # Lists
        self.active_frame = ctk.CTkScrollableFrame(self.tab_apps, label_text="🟢 Active Data Hogs")
        self.active_frame.grid(row=2, column=0, padx=(10, 5), pady=10, sticky="nsew")

        self.blocked_frame = ctk.CTkScrollableFrame(self.tab_apps, label_text="🔴 Blocked / Jailed")
        self.blocked_frame.grid(row=2, column=1, padx=(5, 10), pady=10, sticky="nsew")

    def refresh_all_apps(self):
        """Refresh both active and blocked app lists in a background thread."""
        self.set_status("🔄 Scanning active connections...")
        self.refresh_btn.configure(state="disabled", text="Refreshing...")

        def _fetch():
            active_apps = {}
            try:
                for conn in psutil.net_connections(kind='inet'):
                    if conn.status == 'ESTABLISHED':
                        try:
                            p = psutil.Process(conn.pid)
                            active_apps[p.name()] = p
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            pass
            except (psutil.AccessDenied, PermissionError):
                pass
            
            blocked_rules = []
            try:
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                result = subprocess.run(
                    'netsh advfirewall firewall show rule name=all',
                    capture_output=True, text=True, startupinfo=startupinfo
                )
                output = result.stdout
                for line in output.split('\n'):
                    if "Rule Name:" in line and "_PythonTool" in line:
                        rule_name = line.split("Rule Name:")[1].strip()
                        app_name = rule_name.replace("Block_", "").replace("_PythonTool", "")
                        blocked_rules.append((rule_name, app_name))
            except (subprocess.CalledProcessError, OSError):
                pass
            
            self.after(0, lambda: self._render_app_lists(active_apps, blocked_rules))

        threading.Thread(target=_fetch, daemon=True).start()

    def _render_app_lists(self, active_apps, blocked_rules):
        """Render app manager lists on the main thread."""
        self._cached_active_apps = active_apps
        self.refresh_btn.configure(state="normal", text="🔄 Refresh Lists")
        
        # Render active apps (respecting filter)
        self._render_active_apps(active_apps)

        # Render blocked apps
        for w in self.blocked_frame.winfo_children():
            w.destroy()
        
        if not blocked_rules:
            ctk.CTkLabel(self.blocked_frame, text="No apps blocked.", font=self.FONT_BODY, text_color="gray").pack(pady=20)
        else:
            for rule_name, app_name in blocked_rules:
                f = ctk.CTkFrame(self.blocked_frame, fg_color="#3d0000", corner_radius=6)
                f.pack(fill="x", pady=4, padx=5)
                ctk.CTkLabel(f, text=f"🔒 {app_name}", font=self.FONT_BODY, text_color="#ffcccc").pack(side="left", padx=10, pady=10)
                ctk.CTkButton(f, text="UNBLOCK", width=70, font=("Segoe UI", 11, "bold"), fg_color="#2eb82e", hover_color="#238f23",
                              command=lambda r=rule_name: self.unblock_app(r)).pack(side="right", padx=10)

        count = len(active_apps)
        self.set_status(f"✅ Found {count} active app{'s' if count != 1 else ''} and {len(blocked_rules)} blocked rule{'s' if len(blocked_rules) != 1 else ''}.")

    def _render_active_apps(self, active_apps):
        """Render the active apps list, applying search filter."""
        for w in self.active_frame.winfo_children():
            w.destroy()

        filter_text = self.app_filter_var.get().lower().strip()
        
        filtered = {name: p for name, p in active_apps.items()
                     if not filter_text or filter_text in name.lower()}

        if not filtered:
            msg = "No matches found." if filter_text else "No active connections found."
            ctk.CTkLabel(self.active_frame, text=msg, font=self.FONT_BODY, text_color="gray").pack(pady=20)
            return

        for name, p_obj in filtered.items():
            f = ctk.CTkFrame(self.active_frame, fg_color="#2b2b2b", corner_radius=6)
            f.pack(fill="x", pady=4, padx=5)
            
            ctk.CTkLabel(f, text=f"📦 {name}", font=self.FONT_BODY).pack(side="left", padx=10, pady=10)
            
            btn_frame = ctk.CTkFrame(f, fg_color="transparent")
            btn_frame.pack(side="right", padx=5)

            ctk.CTkButton(btn_frame, text="DETAILS", width=60, font=("Segoe UI", 10), fg_color="#444444", hover_color="#666666",
                          command=lambda p=p_obj: self.show_process_details(p)).pack(side="left", padx=2)
            
            path = ""
            try:
                path = p_obj.exe() 
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
            
            ctk.CTkButton(btn_frame, text="BLOCK", width=60, font=("Segoe UI", 10, "bold"), fg_color="#ff9900", hover_color="#b36b00",
                          command=lambda n=name, p=path: self.block_app(n, p)).pack(side="left", padx=2)

    def _apply_app_filter(self):
        """Re-render active apps list when the search filter changes."""
        if self._cached_active_apps:
            self._render_active_apps(self._cached_active_apps)

    def show_process_details(self, process):
        """Show process details in a themed CTkToplevel dialog."""
        try:
            info_lines = [
                ("Name", process.name()),
                ("PID", str(process.pid)),
                ("Status", process.status()),
                ("CPU Usage", f"{process.cpu_percent(interval=None)}%"),
                ("Memory", f"{process.memory_info().rss / 1024 / 1024:.2f} MB"),
                ("Path", process.exe()),
            ]
        except Exception as e:
            info_lines = [("Error", f"Could not fetch details: {e}")]
        
        dialog = ctk.CTkToplevel(self)
        dialog.title("Process Details")
        dialog.geometry("450x320")
        dialog.resizable(False, False)
        dialog.grab_set()
        dialog.after(100, dialog.focus_force)

        ctk.CTkLabel(dialog, text="📋 Process Details", font=self.FONT_SUBHEAD).pack(pady=(20, 10))

        details_frame = ctk.CTkFrame(dialog, fg_color="#2b2b2b", corner_radius=8)
        details_frame.pack(padx=20, pady=5, fill="x")

        for label, value in info_lines:
            row = ctk.CTkFrame(details_frame, fg_color="transparent")
            row.pack(fill="x", padx=15, pady=4)
            ctk.CTkLabel(row, text=f"{label}:", font=("Segoe UI", 12, "bold"), width=90, anchor="w").pack(side="left")
            ctk.CTkLabel(row, text=value, font=self.FONT_MONO, text_color="#cccccc", anchor="w", wraplength=280).pack(side="left", fill="x", expand=True)

        ctk.CTkButton(dialog, text="Close", width=100, command=dialog.destroy).pack(pady=15)

    def block_app(self, name, path):
        if not path:
            messagebox.showerror("Error", "Could not find executable path.")
            return
        rule = f"Block_{name}_PythonTool"
        cmd = f'netsh advfirewall firewall add rule name="{rule}" dir=out action=block program="{path}" enable=yes'
        self.run_netsh(cmd)
        self.set_status(f"🔒 Blocked {name}")
        self.refresh_all_apps()

    def unblock_app(self, rule):
        cmd = f'netsh advfirewall firewall delete rule name="{rule}"'
        self.run_netsh(cmd)
        app_name = rule.replace("Block_", "").replace("_PythonTool", "")
        self.set_status(f"🔓 Unblocked {app_name}")
        self.refresh_all_apps()

    def run_netsh(self, cmd):
        try:
            subprocess.run(cmd, shell=True, check=True, creationflags=subprocess.CREATE_NO_WINDOW)
        except subprocess.CalledProcessError:
            messagebox.showerror("Error", "Action Failed. Run as Admin!")
        except OSError as e:
            messagebox.showerror("Error", f"System error: {e}")

    # ==========================
    # TAB 3: CONNECTIONS
    # ==========================
    def setup_connections(self):
        self.tab_conn.grid_columnconfigure(0, weight=1)
        self.tab_conn.grid_rowconfigure(0, weight=0)
        self.tab_conn.grid_rowconfigure(1, weight=0)
        self.tab_conn.grid_rowconfigure(2, weight=1)
        
        # Top Bar
        top_bar = ctk.CTkFrame(self.tab_conn, fg_color="transparent")
        top_bar.grid(row=0, column=0, sticky="ew", padx=10, pady=5)
        
        ctk.CTkButton(top_bar, text="🔄 Refresh Table", font=self.FONT_BUTTON, command=self.get_conns).pack(side="left")
        ctk.CTkButton(top_bar, text="💾 Export CSV", font=self.FONT_BUTTON, fg_color="#444444", command=lambda: self.export_data("connections")).pack(side="left", padx=10)
        
        # Headers (clickable for sorting)
        self.conn_header_frame = ctk.CTkFrame(self.tab_conn, height=30, fg_color="#1a1a1a")
        self.conn_header_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(5,0))
        
        conn_headers = [("LOCAL PORT", 80, 0), ("REMOTE IP", 140, 1), ("GEO / ISP", 200, 2), ("STATUS", 100, 3), ("PID", 60, 4)]
        for text, width, col_idx in conn_headers:
            btn = ctk.CTkButton(self.conn_header_frame, text=f"{text} ↕", width=width, height=25,
                                font=("Segoe UI", 11, "bold"), fg_color="#1a1a1a", hover_color="#333333",
                                anchor="w", command=lambda c=col_idx: self.sort_connections(c))
            btn.pack(side="left", padx=5)

        # Scrollable Area
        self.conn_scroll = ctk.CTkScrollableFrame(self.tab_conn, fg_color="transparent")
        self.conn_scroll.grid(row=2, column=0, sticky="nsew", padx=10, pady=5)

    def get_conns(self):
        for w in self.conn_scroll.winfo_children(): w.destroy()
        self.current_conns_data = []
        
        # Loading Indicator
        loading = ctk.CTkLabel(self.conn_scroll, text="Fetching Connections & GeoIP...", text_color="yellow")
        loading.pack(pady=10)
        self.update_idletasks()

        def fetch_thread():
            active_conns = []
            try:
                for c in psutil.net_connections(kind='inet'):
                    if c.status == 'ESTABLISHED':
                        active_conns.append(c)
            except (psutil.AccessDenied, PermissionError):
                pass
            
            # Update UI on Main Thread
            self.after(0, lambda: self.render_connections(active_conns))
            
        threading.Thread(target=fetch_thread, daemon=True).start()

    def render_connections(self, connections):
        for w in self.conn_scroll.winfo_children(): w.destroy()
        self.current_conns_data = []
        
        if not connections:
             ctk.CTkLabel(self.conn_scroll, text="No established connections.", font=self.FONT_BODY).pack(pady=20)
             self.set_status("No established connections found.")
             return

        for c in connections:
            r_ip = c.raddr.ip if c.raddr else "N/A"
            r_port = str(c.raddr.port) if c.raddr else ""
            remote = f"{r_ip}:{r_port}"
            
            # GeoIP Lookup (Cached)
            geo_info = "Local/Unknown"
            if r_ip != "127.0.0.1" and r_ip != "N/A" and not r_ip.startswith("192.168") and not r_ip.startswith("10."):
                 if r_ip in self.geoip_cache:
                     geo_info = self.geoip_cache[r_ip]
                 else:
                     geo_info = "..." 
                     self.geo_executor.submit(self.resolve_geoip, r_ip)

            # Record for export
            self.current_conns_data.append([str(c.laddr.port), remote, geo_info, c.status, str(c.pid)])

            # UI Card
            card = ctk.CTkFrame(self.conn_scroll, fg_color="#2b2b2b")
            card.pack(fill="x", pady=2)
            
            self.create_selectable_label(card, str(c.laddr.port), 80, "#00ccff")
            self.create_selectable_label(card, str(remote), 140, "white")
            
            # Dynamic Label for Geo that can update
            geo_lbl = ctk.CTkLabel(card, text=geo_info, width=200, anchor="w", font=self.FONT_MONO, text_color="#aaaaaa")
            geo_lbl.pack(side="left", padx=5)
            # Store ref to update later
            if geo_info == "...":
                 self.pending_geo_labels[r_ip].append(geo_lbl)

            ctk.CTkLabel(card, text=c.status, width=100, font=self.FONT_MONO, anchor="w", text_color="#00ff00").pack(side="left", padx=5)
            self.create_selectable_label(card, str(c.pid), 60, "gray")

        self.set_status(f"✅ Found {len(connections)} established connections.")

    def sort_connections(self, col_idx):
        """Sort connection data by the clicked column."""
        if not self.current_conns_data:
            return
        if self.conns_sort_col == col_idx:
            self.conns_sort_reverse = not self.conns_sort_reverse
        else:
            self.conns_sort_col = col_idx
            self.conns_sort_reverse = False

        try:
            self.current_conns_data.sort(key=lambda row: row[col_idx], reverse=self.conns_sort_reverse)
        except (IndexError, TypeError):
            return

        # Re-render
        for w in self.conn_scroll.winfo_children(): w.destroy()
        for row in self.current_conns_data:
            card = ctk.CTkFrame(self.conn_scroll, fg_color="#2b2b2b")
            card.pack(fill="x", pady=2)
            colors = ["#00ccff", "white", "#aaaaaa", "#00ff00", "gray"]
            widths = [80, 140, 200, 100, 60]
            for i, val in enumerate(row):
                if i == 2 or i == 3:
                    ctk.CTkLabel(card, text=val, width=widths[i], font=self.FONT_MONO, anchor="w",
                                 text_color=colors[i]).pack(side="left", padx=5)
                else:
                    self.create_selectable_label(card, val, widths[i], colors[i])
        
        direction = "▼" if self.conns_sort_reverse else "▲"
        self.set_status(f"Sorted connections by column {col_idx + 1} {direction}")

    def resolve_geoip(self, ip):
        try:
            r = requests.get(f"http://ip-api.com/json/{ip}", timeout=3).json()
            if r.get('status') == 'success':
                info = f"{r.get('countryCode', '')} | {r.get('isp', 'Unknown')[:15]}"
                self.geoip_cache[ip] = info
                
                # Update UI on main thread
                if ip in self.pending_geo_labels:
                    labels = self.pending_geo_labels.pop(ip)
                    self.after(0, lambda lbls=labels, txt=info: [lbl.configure(text=txt) for lbl in lbls])
        except (requests.RequestException, ValueError, KeyError):
            pass

    def create_selectable_label(self, parent, text, width, color):
        entry = ctk.CTkEntry(parent, width=width, font=self.FONT_MONO, text_color=color,
                             fg_color="transparent", border_width=0)
        entry.insert(0, text)
        entry.configure(state="readonly")
        entry.pack(side="left", padx=5, pady=5)

    # ==========================
    # TAB 4: SCANNER
    # ==========================
    def setup_scanner(self):
        self.tab_scan.grid_columnconfigure(0, weight=1)
        self.tab_scan.grid_rowconfigure(0, weight=0)
        self.tab_scan.grid_rowconfigure(1, weight=0)
        self.tab_scan.grid_rowconfigure(2, weight=1)

        top = ctk.CTkFrame(self.tab_scan, fg_color="transparent")
        top.grid(row=0, column=0, pady=20)
        ctk.CTkButton(top, text="📡 Scan Local Network (ARP)", font=self.FONT_BUTTON, command=self.run_scan).pack(side="left", padx=10)
        ctk.CTkButton(top, text="💾 Export CSV", font=self.FONT_BUTTON, fg_color="#444444", command=lambda: self.export_data("scanner")).pack(side="left", padx=10)
        
        # Headers (clickable for sorting)
        self.scan_header_frame = ctk.CTkFrame(self.tab_scan, height=30, fg_color="#1a1a1a")
        self.scan_header_frame.grid(row=1, column=0, sticky="ew", padx=20)
        
        scan_headers = [("IP ADDRESS", 200, 0), ("MAC ADDRESS", 200, 1), ("TYPE", 100, 2)]
        for text, width, col_idx in scan_headers:
            btn = ctk.CTkButton(self.scan_header_frame, text=f"{text} ↕", width=width, height=25,
                                font=("Segoe UI", 11, "bold"), fg_color="#1a1a1a", hover_color="#333333",
                                anchor="w", command=lambda c=col_idx: self.sort_scanner(c))
            btn.pack(side="left", padx=20)

        # Results Area
        self.scan_scroll = ctk.CTkScrollableFrame(self.tab_scan, fg_color="transparent")
        self.scan_scroll.grid(row=2, column=0, sticky="nsew", padx=20, pady=5)

    def run_scan(self):
        for w in self.scan_scroll.winfo_children(): w.destroy()
        self.current_scan_data = []
        
        try:
            result = subprocess.run('arp -a', capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
            output = result.stdout
            lines = output.splitlines()
            
            found_any = False
            for line in lines:
                parts = line.split()
                if len(parts) == 3 and parts[2] in ['dynamic', 'static']:
                    found_any = True
                    ip, mac, type_ = parts[0], parts[1], parts[2]
                    self.current_scan_data.append([ip, mac, type_])
                    
                    self._render_scan_card(ip, mac, type_)

            if not found_any:
                ctk.CTkLabel(self.scan_scroll, text="No devices found.", font=self.FONT_BODY).pack(pady=20)
            else:
                self.set_status(f"📡 Found {len(self.current_scan_data)} devices on the network.")

        except Exception as e: 
            ctk.CTkLabel(self.scan_scroll, text=f"Scan failed: {e}", text_color="red").pack(pady=20)
            self.set_status("❌ LAN scan failed.")

    def _render_scan_card(self, ip, mac, type_):
        """Render a single scan result card."""
        card = ctk.CTkFrame(self.scan_scroll, fg_color="#2b2b2b")
        card.pack(fill="x", pady=3)
        
        icon = "🖥️" if type_ == 'dynamic' else "⚙️"
        
        self.create_selectable_label(card, f"{icon} {ip}", 200, "#00ccff")
        self.create_selectable_label(card, mac, 200, "white")
        ctk.CTkLabel(card, text=type_.upper(), width=100, font=self.FONT_MONO, anchor="w", text_color="gray").pack(side="left", padx=20)

    def sort_scanner(self, col_idx):
        """Sort scanner data by the clicked column."""
        if not self.current_scan_data:
            return
        if self.scan_sort_col == col_idx:
            self.scan_sort_reverse = not self.scan_sort_reverse
        else:
            self.scan_sort_col = col_idx
            self.scan_sort_reverse = False

        self.current_scan_data.sort(key=lambda row: row[col_idx], reverse=self.scan_sort_reverse)

        for w in self.scan_scroll.winfo_children(): w.destroy()
        for row in self.current_scan_data:
            self._render_scan_card(row[0], row[1], row[2])

        direction = "▼" if self.scan_sort_reverse else "▲"
        self.set_status(f"Sorted scanner by column {col_idx + 1} {direction}")

    # ==========================
    # TAB 5: SPEED TEST
    # ==========================
    def setup_speedtest(self):
        self.tab_speed.grid_columnconfigure(0, weight=1)
        self.tab_speed.grid_rowconfigure(1, weight=0)
        self.tab_speed.grid_rowconfigure(2, weight=1)

        btn_frame = ctk.CTkFrame(self.tab_speed, fg_color="transparent")
        btn_frame.grid(row=0, column=0, pady=30)

        self.st_btn = ctk.CTkButton(btn_frame, text="🚀 START SPEED TEST", font=("Segoe UI", 16, "bold"), 
                                    height=50, width=250, command=self.run_speedtest_thread)
        self.st_btn.pack()

        # Progress Bar
        self.st_progress = ctk.CTkProgressBar(btn_frame, width=250, mode="indeterminate")
        self.st_progress.pack(pady=(10, 0))
        self.st_progress.set(0)

        # Results Grid
        res_frame = ctk.CTkFrame(self.tab_speed, fg_color="#2b2b2b")
        res_frame.grid(row=2, column=0, padx=50, pady=(0, 50), sticky="nsew")
        res_frame.grid_columnconfigure((0,1,2), weight=1)
        res_frame.grid_rowconfigure(0, weight=1)

        self.st_ping = self.create_stat_box(res_frame, "PING", "---", 0)
        self.st_down = self.create_stat_box(res_frame, "DOWNLOAD", "---", 1)
        self.st_up = self.create_stat_box(res_frame, "UPLOAD", "---", 2)

    def create_stat_box(self, parent, title, value, col):
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.grid(row=0, column=col)
        ctk.CTkLabel(f, text=title, font=("Segoe UI", 14), text_color="gray").pack()
        lbl = ctk.CTkLabel(f, text=value, font=("Segoe UI", 28, "bold"), text_color="#00ccff")
        lbl.pack()
        return lbl

    def run_speedtest_thread(self):
        self.st_btn.configure(state="disabled", text="TESTING...")
        self.st_progress.start()
        self.st_ping.configure(text="...")
        self.st_down.configure(text="...")
        self.st_up.configure(text="...")
        self.set_status("🚀 Running speed test... this may take up to 30 seconds.")
        
        threading.Thread(target=self.run_speedtest, daemon=True).start()

    def run_speedtest(self):
        try:
            st = speedtest.Speedtest()
            st.get_best_server()
            
            p = st.results.ping
            self.after(0, lambda: self.st_ping.configure(text=f"{p:.1f} ms"))
            
            d = st.download() / 1024 / 1024
            self.after(0, lambda: self.st_down.configure(text=f"{d:.2f} Mbps"))
            
            u = st.upload() / 1024 / 1024
            self.after(0, lambda: self.st_up.configure(text=f"{u:.2f} Mbps"))

            self.after(0, lambda: self._speedtest_done(True))
        except Exception as e:
            self.after(0, lambda: self._speedtest_done(False, str(e)))

    def _speedtest_done(self, success, error_msg=""):
        """Handle speedtest completion on the main thread."""
        self.st_progress.stop()
        self.st_progress.set(0)
        if success:
            self.st_btn.configure(state="normal", text="🚀 START SPEED TEST")
            self.set_status("✅ Speed test completed.")
        else:
            self.st_btn.configure(state="normal", text="🚀 RETRY")
            self.set_status(f"❌ Speed test failed: {error_msg}")
            messagebox.showerror("Speedtest Failed", f"The speed test could not complete.\n\nError: {error_msg}\n\nTip: Check your internet connection and try again.")

    # ==========================
    # TAB 6: SETTINGS
    # ==========================
    def setup_settings(self):
        self.tab_settings.grid_columnconfigure(0, weight=1)
        
        scroll = ctk.CTkScrollableFrame(self.tab_settings, fg_color="transparent")
        scroll.pack(pady=20, padx=40, fill="both", expand=True)

        # --- Appearance ---
        ctk.CTkLabel(scroll, text="Appearance", font=self.FONT_SUBHEAD).pack(anchor="w", pady=(0, 10))
        
        self.theme_switch = ctk.CTkSwitch(scroll, text="Dark Mode", command=self.toggle_theme)
        self.theme_switch.select()
        self.theme_switch.pack(anchor="w")

        # --- Network Interface ---
        ctk.CTkLabel(scroll, text="Network Interface", font=self.FONT_SUBHEAD).pack(anchor="w", pady=(20, 10))
        
        interfaces = list(psutil.net_if_addrs().keys())
        interface_options = ["All Interfaces"] + interfaces
        self.iface_var = ctk.StringVar(value="All Interfaces")
        self.iface_menu = ctk.CTkOptionMenu(scroll, values=interface_options, variable=self.iface_var,
                                             command=self._change_interface, width=250)
        self.iface_menu.pack(anchor="w")

        # --- System Tray ---
        ctk.CTkLabel(scroll, text="System Tray", font=self.FONT_SUBHEAD).pack(anchor="w", pady=(20, 10))
        
        self.tray_switch = ctk.CTkSwitch(scroll, text="Minimize to tray on close", 
                                          command=self._toggle_tray_setting)
        self.tray_switch.select()  # Default ON
        self.tray_switch.pack(anchor="w")

        # --- Performance ---
        ctk.CTkLabel(scroll, text="Update Interval (ms)", font=self.FONT_SUBHEAD).pack(anchor="w", pady=(20, 10))
        
        self.slider = ctk.CTkSlider(scroll, from_=500, to=5000, number_of_steps=9, command=self.change_interval)
        self.slider.set(1000)
        self.slider.pack(anchor="w", fill="x")
        self.lbl_interval = ctk.CTkLabel(scroll, text="1000 ms")
        self.lbl_interval.pack(anchor="w")

        # --- Bandwidth Alerts ---
        ctk.CTkLabel(scroll, text="Bandwidth Alerts", font=self.FONT_SUBHEAD).pack(anchor="w", pady=(20, 10))
        
        self.alert_switch = ctk.CTkSwitch(scroll, text="Enable bandwidth alerts",
                                           command=self._toggle_alerts)
        self.alert_switch.pack(anchor="w")

        alert_grid = ctk.CTkFrame(scroll, fg_color="transparent")
        alert_grid.pack(anchor="w", fill="x", pady=(10, 0))
        
        ctk.CTkLabel(alert_grid, text="Session total limit (MB):", font=self.FONT_BODY).grid(row=0, column=0, sticky="w", pady=3)
        self.alert_session_entry = ctk.CTkEntry(alert_grid, width=80, placeholder_text="500")
        self.alert_session_entry.insert(0, "500")
        self.alert_session_entry.grid(row=0, column=1, padx=10, pady=3)
        
        ctk.CTkLabel(alert_grid, text="Speed limit (MB/s):", font=self.FONT_BODY).grid(row=1, column=0, sticky="w", pady=3)
        self.alert_speed_entry = ctk.CTkEntry(alert_grid, width=80, placeholder_text="10")
        self.alert_speed_entry.insert(0, "10")
        self.alert_speed_entry.grid(row=1, column=1, padx=10, pady=3)
        
        ctk.CTkButton(alert_grid, text="Apply", width=60, font=("Segoe UI", 11),
                       command=self._apply_alert_settings).grid(row=0, column=2, rowspan=2, padx=10)

        # --- Session ---
        sep1 = ctk.CTkFrame(scroll, height=2, fg_color="#444444")
        sep1.pack(fill="x", pady=20)
        
        ctk.CTkLabel(scroll, text="Session", font=self.FONT_SUBHEAD).pack(anchor="w", pady=(0, 10))
        
        ctk.CTkButton(scroll, text="🔄 Reset Session Totals", font=self.FONT_BUTTON, 
                       fg_color="#444444", hover_color="#555555", width=200,
                       command=self.reset_session_totals).pack(anchor="w")

        # --- About ---
        sep2 = ctk.CTkFrame(scroll, height=2, fg_color="#444444")
        sep2.pack(fill="x", pady=20)
        
        ctk.CTkLabel(scroll, text="About", font=self.FONT_SUBHEAD).pack(anchor="w", pady=(0, 10))
        
        about_frame = ctk.CTkFrame(scroll, fg_color="#2b2b2b", corner_radius=8)
        about_frame.pack(fill="x", pady=5)

        about_items = [
            ("Application", "Ned — Ultimate Network Monitor"),
            ("Version", APP_VERSION),
            ("Author", "hheshanj"),
            ("Platform", "Windows"),
            ("License", "MIT"),
        ]
        for label, value in about_items:
            row = ctk.CTkFrame(about_frame, fg_color="transparent")
            row.pack(fill="x", padx=15, pady=3)
            ctk.CTkLabel(row, text=f"{label}:", font=("Segoe UI", 12, "bold"), width=100, anchor="w").pack(side="left")
            ctk.CTkLabel(row, text=value, font=self.FONT_BODY, text_color="#cccccc", anchor="w").pack(side="left")

    def toggle_theme(self):
        mode = "Dark" if self.theme_switch.get() == 1 else "Light"
        ctk.set_appearance_mode(mode)
        self.set_status(f"🎨 Theme changed to {mode} mode.")
    
    def change_interval(self, val):
        self.update_interval = int(val)
        self.lbl_interval.configure(text=f"{int(val)} ms")

    def reset_session_totals(self):
        """Reset session upload/download counters."""
        net_io = psutil.net_io_counters()
        self.start_upload = net_io.bytes_sent
        self.start_download = net_io.bytes_recv
        self.total_dl_label.configure(text="Total: 0 B")
        self.total_ul_label.configure(text="Total: 0 B")
        self.set_status("🔄 Session totals reset.")

    def _toggle_tray_setting(self):
        self._minimize_to_tray = self.tray_switch.get() == 1

    def _change_interface(self, value):
        """Change the network interface for monitoring."""
        if value == "All Interfaces":
            self._selected_interface = None
        else:
            self._selected_interface = value
        self.set_status(f"🌐 Monitoring interface: {value}")

    def _toggle_alerts(self):
        self._alert_enabled = self.alert_switch.get() == 1
        self._alert_session_fired = False
        self._alert_speed_fired = False
        state = "enabled" if self._alert_enabled else "disabled"
        self.set_status(f"🔔 Bandwidth alerts {state}.")

    def _apply_alert_settings(self):
        try:
            self._alert_session_mb = float(self.alert_session_entry.get())
        except ValueError:
            self._alert_session_mb = 500
        try:
            self._alert_speed_mbps = float(self.alert_speed_entry.get())
        except ValueError:
            self._alert_speed_mbps = 10
        self._alert_session_fired = False
        self._alert_speed_fired = False
        self.set_status(f"\u2705 Alert thresholds: session={self._alert_session_mb} MB, speed={self._alert_speed_mbps} MB/s")

    def _check_alerts(self, session_dl_bytes, session_ul_bytes, dl_speed_bytes, ul_speed_bytes):
        """Check bandwidth thresholds and fire alerts."""
        if not self._alert_enabled:
            return
        
        total_session_mb = (session_dl_bytes + session_ul_bytes) / (1024 * 1024)
        max_speed_mbps = max(dl_speed_bytes, ul_speed_bytes) / (1024 * 1024)
        
        if total_session_mb >= self._alert_session_mb and not self._alert_session_fired:
            self._alert_session_fired = True
            self.set_status(f"⚠\ufe0f ALERT: Session total exceeded {self._alert_session_mb} MB!")
            self.after(0, lambda: messagebox.showwarning(
                "\u26a0\ufe0f Bandwidth Alert",
                f"Session data usage has exceeded {self._alert_session_mb} MB!\n\n"
                f"Current: {total_session_mb:.1f} MB"
            ))
        
        if max_speed_mbps >= self._alert_speed_mbps and not self._alert_speed_fired:
            self._alert_speed_fired = True
            self.set_status(f"⚠\ufe0f ALERT: Speed exceeded {self._alert_speed_mbps} MB/s!")
            self.after(100, lambda: messagebox.showwarning(
                "\u26a0\ufe0f Speed Alert",
                f"Network speed exceeded {self._alert_speed_mbps} MB/s!\n\n"
                f"Current: {max_speed_mbps:.2f} MB/s"
            ))

    # ==========================
    # SYSTEM TRAY
    # ==========================
    def _on_close(self):
        """Handle window close — minimize to tray or quit."""
        if self._minimize_to_tray:
            self._minimize_to_tray_action()
        else:
            self._quit_app()

    def _minimize_to_tray_action(self):
        """Hide window and show system tray icon."""
        self.withdraw()
        self.set_status("Minimized to system tray.")
        if self._tray_icon is None:
            self._create_tray_icon()

    def _create_tray_icon(self):
        """Create the system tray icon with menu."""
        try:
            ico_path = Path(__file__).parent / "gls.ico"
            if ico_path.exists():
                icon_image = Image.open(str(ico_path))
            else:
                icon_image = Image.new('RGB', (64, 64), color=(0, 200, 0))
        except Exception:
            icon_image = Image.new('RGB', (64, 64), color=(0, 200, 0))

        menu = pystray.Menu(
            pystray.MenuItem("Show Ned", self._tray_show, default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Speed Test", self._tray_speedtest),
            pystray.MenuItem("Kill Internet", self._tray_kill),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", self._tray_quit),
        )

        self._tray_icon = pystray.Icon("ned", icon_image, "Ned | Network Monitor", menu)
        threading.Thread(target=self._tray_icon.run, daemon=True).start()

    def _tray_show(self, icon=None, item=None):
        """Restore window from tray."""
        self.after(0, self._restore_window)

    def _restore_window(self):
        self.deiconify()
        self.focus_force()
        self.set_status("Window restored from tray.")

    def _tray_speedtest(self, icon=None, item=None):
        self.after(0, lambda: (self._restore_window(), self.tabview.set("Speed Test"), self.run_speedtest_thread()))

    def _tray_kill(self, icon=None, item=None):
        self.after(0, self.kill_switch)

    def _tray_quit(self, icon=None, item=None):
        self.after(0, self._quit_app)

    def _quit_app(self):
        """Fully exit the application."""
        self.monitor_active = False
        self._app_bw_tracking = False
        if self._tray_icon:
            self._tray_icon.stop()
            self._tray_icon = None
        self.destroy()

    # ==========================
    # GLOBAL HELPERS
    # ==========================
    def monitor_loop(self):
        if not self.monitor_active: return
        try:
            net_io = psutil.net_io_counters()
            u = net_io.bytes_sent
            d = net_io.bytes_recv
            t = time.time()
            
            dt = t - self.last_time
            if dt <= 0:
                dt = 0.001  # Avoid division by zero
            
            us_bytes = (u - self.last_upload) / dt
            ds_bytes = (d - self.last_download) / dt
            us_kb = us_bytes / 1024
            ds_kb = ds_bytes / 1024
            
            session_ul = u - self.start_upload
            session_dl = d - self.start_download
            
            # Auto-scaled speed labels
            self.dl_label.configure(text=f"⬇ {self.format_speed(ds_bytes)}")
            self.ul_label.configure(text=f"⬆ {self.format_speed(us_bytes)}")
            self.total_dl_label.configure(text=f"Total: {self.format_bytes(session_dl)}")
            self.total_ul_label.configure(text=f"Total: {self.format_bytes(session_ul)}")
            
            self.y_dl.append(ds_kb)
            self.y_ul.append(us_kb)
            self.line_dl.set_data(self.x_data, self.y_dl)
            self.line_ul.set_data(self.x_data, self.y_ul)
            
            peak = max(max(self.y_dl), max(self.y_ul), 10)
            self.ax.set_ylim(0, peak * 1.2)
            self.canvas.draw()
            
            self.last_upload, self.last_download, self.last_time = u, d, t
            
            # Update tray tooltip with live speeds
            self._tray_speed_text = f"DL: {self.format_speed(ds_bytes)} | UL: {self.format_speed(us_bytes)}"
            if self._tray_icon:
                self._tray_icon.title = f"Ned | {self._tray_speed_text}"
            
            # Check bandwidth alerts
            self._check_alerts(session_dl, session_ul, ds_bytes, us_bytes)
            
            # Auto-save history every 5 min
            self._auto_save_history()
        except (psutil.Error, ValueError, ZeroDivisionError):
            pass
            
        self.after(self.update_interval, self.monitor_loop)

    def kill_switch(self):
        """Kill internet with confirmation dialog."""
        confirm = messagebox.askyesno("⚠️ Confirm Kill Switch", 
                                       "Are you sure you want to kill ALL internet connections?\n\nThis will release your IP address.")
        if not confirm:
            return
        
        def _kill():
            try:
                subprocess.run("ipconfig /release", shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
            except OSError:
                pass
            self.after(0, lambda: self.dl_label.configure(text="KILLED", text_color="red"))
            self.after(0, lambda: self.ul_label.configure(text="OFFLINE", text_color="red"))
            self.after(0, lambda: self.set_status("💀 Internet killed. Use Restore to reconnect."))

        threading.Thread(target=_kill, daemon=True).start()
        self.dl_label.configure(text="KILLING...", text_color="yellow")

    def restore_internet(self):
        def _restore():
            try:
                subprocess.run("ipconfig /renew", shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
            except OSError:
                pass
            self.after(0, lambda: self.set_status("✅ Internet restored."))
        threading.Thread(target=_restore, daemon=True).start()
        self.dl_label.configure(text="RESTORING...", text_color="yellow")
        self.set_status("🩹 Restoring internet connection...")

    def export_data(self, source):
        data = []
        filename = ""
        
        if source == "connections":
            data = [["Local Port", "Remote", "GeoIP", "Status", "PID"]] + self.current_conns_data
            filename = "ned_connections.csv"
        elif source == "scanner":
            data = [["IP", "MAC", "Type"]] + self.current_scan_data
            filename = "ned_lan_scan.csv"
        elif source == "bandwidth":
            rows = []
            for pid, d in self._app_bw_data.items():
                rows.append([d['name'], pid, f"{d['recv_rate']:.0f}", f"{d['send_rate']:.0f}",
                             d['recv'], d['sent']])
            data = [["Process", "PID", "DL Speed (B/s)", "UL Speed (B/s)", "Total Recv", "Total Sent"]] + rows
            filename = "ned_bandwidth.csv"
        elif source == "dns":
            data = [["Record Name", "Type", "Data"]] + self.current_dns_data
            filename = "ned_dns_cache.csv"
            
        if not data or len(data) <= 1:
            messagebox.showwarning("Empty", "No data to export. Refresh the data first.")
            return

        path = filedialog.asksaveasfilename(defaultextension=".csv", initialfile=filename,
                                            filetypes=[("CSV Files", "*.csv")])
        if path:
            try:
                with open(path, 'w', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerows(data)
                self.set_status(f"💾 Exported {len(data) - 1} rows to {Path(path).name}")
                messagebox.showinfo("Success", f"Saved to {path}")
            except (IOError, OSError) as e:
                messagebox.showerror("Error", str(e))

    def format_bytes(self, size):
        """Format bytes into human-readable string."""
        if size <= 0:
            return "0 B"
        power = 2**10
        n = 0
        power_labels = {0: 'B', 1: 'KB', 2: 'MB', 3: 'GB', 4: 'TB'}
        while size > power and n < 4:
            size /= power
            n += 1
        return f"{size:.2f} {power_labels.get(n, 'TB')}"

    def format_speed(self, bytes_per_sec):
        """Format bytes/sec into human-readable speed string."""
        if bytes_per_sec <= 0:
            return "0 B/s"
        power = 1024
        n = 0
        labels = {0: 'B/s', 1: 'KB/s', 2: 'MB/s', 3: 'GB/s'}
        while bytes_per_sec > power and n < 3:
            bytes_per_sec /= power
            n += 1
        return f"{bytes_per_sec:.1f} {labels.get(n, 'GB/s')}"

if __name__ == "__main__":
    app = ned()
    app.mainloop()