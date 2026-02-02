import customtkinter as ctk
import psutil
import threading
import time
import os
import subprocess
import collections
import csv
import json
import requests
import speedtest
from datetime import datetime
from tkinter import messagebox, filedialog
from pathlib import Path

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
        except:
            pass

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # --- CACHING & STATE ---
        self.geoip_cache = {}
        self.monitor_active = True
        self.update_interval = 1000 # ms

        # --- TABS ---
        self.tabview = ctk.CTkTabview(self)
        self.tabview.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")
        self.tabview._segmented_button.configure(font=self.FONT_BUTTON) 
        
        self.tab_dash = self.tabview.add("Dashboard")
        self.tab_apps = self.tabview.add("App Manager")
        self.tab_conn = self.tabview.add("Connections")
        self.tab_scan = self.tabview.add("LAN Scanner")
        self.tab_speed = self.tabview.add("Speed Test")
        self.tab_settings = self.tabview.add("Settings")
        
        # Setup Views
        self.setup_dashboard()
        self.setup_app_manager()
        self.setup_connections()
        self.setup_scanner()
        self.setup_speedtest()
        self.setup_settings()

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

    # ==========================
    # TAB 1: DASHBOARD
    # ==========================
    def setup_dashboard(self):
        self.tab_dash.grid_columnconfigure((0, 1), weight=1)
        self.tab_dash.grid_rowconfigure(2, weight=1)
        
        # --- Speed Labels ---
        self.dl_label = ctk.CTkLabel(self.tab_dash, text="⬇ 0 KB/s", font=self.FONT_HEADER, text_color="#00ff00")
        self.dl_label.grid(row=0, column=0, pady=(20, 5))
        
        self.ul_label = ctk.CTkLabel(self.tab_dash, text="⬆ 0 KB/s", font=self.FONT_HEADER, text_color="#ff9900")
        self.ul_label.grid(row=0, column=1, pady=(20, 5))

        # --- Session Totals ---
        self.total_dl_label = ctk.CTkLabel(self.tab_dash, text="Total: 0 MB", font=self.FONT_BODY, text_color="#88ff88")
        self.total_dl_label.grid(row=1, column=0, pady=(0, 20))
        
        self.total_ul_label = ctk.CTkLabel(self.tab_dash, text="Total: 0 MB", font=self.FONT_BODY, text_color="#ffcc88")
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
        self.tab_apps.grid_rowconfigure(1, weight=1)
        
        # Controls
        self.control_frame = ctk.CTkFrame(self.tab_apps, fg_color="transparent")
        self.control_frame.grid(row=0, column=0, columnspan=2, padx=10, pady=5, sticky="ew")
        
        self.refresh_btn = ctk.CTkButton(self.control_frame, text="🔄 Refresh Lists", font=self.FONT_BUTTON, command=self.refresh_all_apps)
        self.refresh_btn.pack(side="left", padx=0, pady=10)
        
        ctk.CTkLabel(self.control_frame, text="⚠️ Admin Required", font=self.FONT_BODY, text_color="orange").pack(side="right", padx=10)

        # Lists
        self.active_frame = ctk.CTkScrollableFrame(self.tab_apps, label_text="🟢 Active Data Hogs")
        self.active_frame.grid(row=1, column=0, padx=(10, 5), pady=10, sticky="nsew")

        self.blocked_frame = ctk.CTkScrollableFrame(self.tab_apps, label_text="🔴 Blocked / Jailed")
        self.blocked_frame.grid(row=1, column=1, padx=(5, 10), pady=10, sticky="nsew")

    def refresh_all_apps(self):
        # 1. Active Apps
        for w in self.active_frame.winfo_children(): w.destroy()
        active_apps = {}
        try:
            for conn in psutil.net_connections(kind='inet'):
                if conn.status == 'ESTABLISHED':
                    try:
                        p = psutil.Process(conn.pid)
                        active_apps[p.name()] = p # Store Obj
                    except: pass
        except: pass
        
        if not active_apps:
            ctk.CTkLabel(self.active_frame, text="No active connections found.", font=self.FONT_BODY, text_color="gray").pack(pady=20)

        for name, p_obj in active_apps.items():
            f = ctk.CTkFrame(self.active_frame, fg_color="#2b2b2b", corner_radius=6)
            f.pack(fill="x", pady=4, padx=5)
            
            ctk.CTkLabel(f, text=f"📦 {name}", font=self.FONT_BODY).pack(side="left", padx=10, pady=10)
            
            # Action Buttons
            btn_frame = ctk.CTkFrame(f, fg_color="transparent")
            btn_frame.pack(side="right", padx=5)

            ctk.CTkButton(btn_frame, text="DETAILS", width=60, font=("Segoe UI", 10), fg_color="#444444", hover_color="#666666",
                          command=lambda p=p_obj: self.show_process_details(p)).pack(side="left", padx=2)
            
            path = ""
            try: path = p_obj.exe() 
            except: pass
            
            ctk.CTkButton(btn_frame, text="BLOCK", width=60, font=("Segoe UI", 10, "bold"), fg_color="#ff9900", hover_color="#b36b00",
                          command=lambda n=name, p=path: self.block_app(n, p)).pack(side="left", padx=2)

        # 2. Blocked Rules
        for w in self.blocked_frame.winfo_children(): w.destroy()
        try:
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            output = subprocess.check_output('netsh advfirewall firewall show rule name=all', startupinfo=startupinfo).decode('utf-8', errors='ignore')
            
            found = False
            for line in output.split('\n'):
                if "Rule Name:" in line and "_PythonTool" in line:
                    found = True
                    rule_name = line.split("Rule Name:")[1].strip()
                    app_name = rule_name.replace("Block_", "").replace("_PythonTool", "")
                    
                    f = ctk.CTkFrame(self.blocked_frame, fg_color="#3d0000", corner_radius=6)
                    f.pack(fill="x", pady=4, padx=5)
                    
                    ctk.CTkLabel(f, text=f"🔒 {app_name}", font=self.FONT_BODY, text_color="#ffcccc").pack(side="left", padx=10, pady=10)
                    ctk.CTkButton(f, text="UNBLOCK", width=70, font=("Segoe UI", 11, "bold"), fg_color="#2eb82e", hover_color="#238f23",
                                  command=lambda r=rule_name: self.unblock_app(r)).pack(side="right", padx=10)
            if not found:
                ctk.CTkLabel(self.blocked_frame, text="No apps blocked.", font=self.FONT_BODY, text_color="gray").pack(pady=20)
        except: pass

    def show_process_details(self, process):
        try:
            info = f"Name: {process.name()}\n"
            info += f"PID: {process.pid}\n"
            info += f"Status: {process.status()}\n"
            info += f"CPU Usage: {process.cpu_percent(interval=None)}%\n"
            info += f"Memory: {process.memory_info().rss / 1024 / 1024:.2f} MB\n"
            info += f"Path: {process.exe()}\n"
        except Exception as e:
            info = f"Error fetching details: {e}"
        
        messagebox.showinfo("Process Details", info)

    def block_app(self, name, path):
        if not path:
            messagebox.showerror("Error", "Could not find executable path.")
            return
        rule = f"Block_{name}_PythonTool"
        cmd = f'netsh advfirewall firewall add rule name="{rule}" dir=out action=block program="{path}" enable=yes'
        self.run_netsh(cmd)
        self.refresh_all_apps()

    def unblock_app(self, rule):
        cmd = f'netsh advfirewall firewall delete rule name="{rule}"'
        self.run_netsh(cmd)
        self.refresh_all_apps()

    def run_netsh(self, cmd):
        try:
            subprocess.run(cmd, shell=True, check=True, creationflags=subprocess.CREATE_NO_WINDOW)
        except:
            messagebox.showerror("Error", "Action Failed. Run as Admin!")

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
        
        # Headers
        header_frame = ctk.CTkFrame(self.tab_conn, height=30, fg_color="#1a1a1a")
        header_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(5,0))
        
        headers = [("LOCAL PORT", 80), ("REMOTE IP", 140), ("GEO / ISP", 200), ("STATUS", 100), ("PID", 60)]
        for text, width in headers:
            ctk.CTkLabel(header_frame, text=text, width=width, font=("Segoe UI", 11, "bold"), anchor="w").pack(side="left", padx=5)

        # Scrollable Area
        self.conn_scroll = ctk.CTkScrollableFrame(self.tab_conn, fg_color="transparent")
        self.conn_scroll.grid(row=2, column=0, sticky="nsew", padx=10, pady=5)
        
        # Store connection data for export
        self.current_conns_data = []

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
            except: pass
            
            # Update UI on Main Thread
            self.after(0, lambda: self.render_connections(active_conns))
            
        threading.Thread(target=fetch_thread, daemon=True).start()

    def render_connections(self, connections):
        for w in self.conn_scroll.winfo_children(): w.destroy()
        
        if not connections:
             ctk.CTkLabel(self.conn_scroll, text="No established connections.", font=self.FONT_BODY).pack(pady=20)
             return

        for c in connections:
            r_ip = c.raddr.ip if c.raddr else "N/A"
            r_port = str(c.raddr.port) if c.raddr else ""
            remote = f"{r_ip}:{r_port}"
            
            # GeoIP Lookup (Cached)
            geo_info = "Local/Unknown"
            if r_ip != "127.0.0.1" and r_ip != "N/A" and not r_ip.startswith("192.168"):
                 if r_ip in self.geoip_cache:
                     geo_info = self.geoip_cache[r_ip]
                 else:
                     # Perform lookup (Simple blocking for now in thread? No, we are in main thread callback)
                     # To avoid freezing, we should have done this in the background or use a very fast timeout
                     # For now, we will mark as "Loading..." and fetch async or just skip detailed verification for valid non-LAN
                     geo_info = "..." 
                     threading.Thread(target=self.resolve_geoip, args=(r_ip,)).start()

            # Record for export
            self.current_conns_data.append([c.laddr.port, remote, geo_info, c.status, c.pid])

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
                 # Use a dict to store pending labels: self.pending_geo_labels[ip] = [label1, label2]
                 if not hasattr(self, 'pending_geo_labels'): self.pending_geo_labels = collections.defaultdict(list)
                 self.pending_geo_labels[r_ip].append(geo_lbl)

            ctk.CTkLabel(card, text=c.status, width=100, font=self.FONT_MONO, anchor="w", text_color="#00ff00").pack(side="left", padx=5)
            self.create_selectable_label(card, str(c.pid), 60, "gray")

    def resolve_geoip(self, ip):
        try:
            # Simple free API
            r = requests.get(f"http://ip-api.com/json/{ip}", timeout=3).json()
            if r['status'] == 'success':
                info = f"{r.get('countryCode', '')} | {r.get('isp', 'Unknown')[:15]}"
                self.geoip_cache[ip] = info
                
                # Update UI
                if hasattr(self, 'pending_geo_labels') and ip in self.pending_geo_labels:
                    for lbl in self.pending_geo_labels[ip]:
                        lbl.configure(text=info)
                    del self.pending_geo_labels[ip]
        except:
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
        
        # Headers
        h_frame = ctk.CTkFrame(self.tab_scan, height=30, fg_color="#1a1a1a")
        h_frame.grid(row=1, column=0, sticky="ew", padx=20)
        
        ctk.CTkLabel(h_frame, text="IP ADDRESS", width=200, font=("Segoe UI", 11, "bold"), anchor="w").pack(side="left", padx=20)
        ctk.CTkLabel(h_frame, text="MAC ADDRESS", width=200, font=("Segoe UI", 11, "bold"), anchor="w").pack(side="left", padx=20)
        ctk.CTkLabel(h_frame, text="TYPE", width=100, font=("Segoe UI", 11, "bold"), anchor="w").pack(side="left", padx=20)

        # Results Area
        self.scan_scroll = ctk.CTkScrollableFrame(self.tab_scan, fg_color="transparent")
        self.scan_scroll.grid(row=2, column=0, sticky="nsew", padx=20, pady=5)
        
        self.current_scan_data = []

    def run_scan(self):
        for w in self.scan_scroll.winfo_children(): w.destroy()
        self.current_scan_data = []
        
        try:
            output = os.popen('arp -a').read()
            lines = output.splitlines()
            
            found_any = False
            for line in lines:
                parts = line.split()
                if len(parts) == 3 and parts[2] in ['dynamic', 'static']:
                    found_any = True
                    ip, mac, type_ = parts[0], parts[1], parts[2]
                    self.current_scan_data.append([ip, mac, type_])
                    
                    card = ctk.CTkFrame(self.scan_scroll, fg_color="#2b2b2b")
                    card.pack(fill="x", pady=3)
                    
                    icon = "🖥️" if type_ == 'dynamic' else "⚙️"
                    
                    self.create_selectable_label(card, f"{icon} {ip}", 200, "#00ccff")
                    self.create_selectable_label(card, mac, 200, "white")
                    ctk.CTkLabel(card, text=type_.upper(), width=100, font=self.FONT_MONO, anchor="w", text_color="gray").pack(side="left", padx=20)

            if not found_any:
                ctk.CTkLabel(self.scan_scroll, text="No devices found.", font=self.FONT_BODY).pack(pady=20)

        except Exception as e: 
            ctk.CTkLabel(self.scan_scroll, text="Scan failed.", text_color="red").pack(pady=20)

    # ==========================
    # TAB 5: SPEED TEST (NEW)
    # ==========================
    def setup_speedtest(self):
        self.tab_speed.grid_columnconfigure(0, weight=1)
        self.tab_speed.grid_rowconfigure(1, weight=1)

        btn_frame = ctk.CTkFrame(self.tab_speed, fg_color="transparent")
        btn_frame.grid(row=0, column=0, pady=40)

        self.st_btn = ctk.CTkButton(btn_frame, text="🚀 START SPEED TEST", font=("Segoe UI", 16, "bold"), 
                                    height=50, width=250, command=self.run_speedtest_thread)
        self.st_btn.pack()

        # Results Grid
        res_frame = ctk.CTkFrame(self.tab_speed, fg_color="#2b2b2b")
        res_frame.grid(row=1, column=0, padx=50, pady=(0, 50), sticky="nsew")
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
        self.st_ping.configure(text="...")
        self.st_down.configure(text="...")
        self.st_up.configure(text="...")
        
        threading.Thread(target=self.run_speedtest, daemon=True).start()

    def run_speedtest(self):
        try:
            st = speedtest.Speedtest()
            st.get_best_server()
            
            p = st.results.ping
            self.st_ping.configure(text=f"{p:.1f} ms")
            
            d = st.download() / 1024 / 1024
            self.st_down.configure(text=f"{d:.2f} Mbps")
            
            u = st.upload() / 1024 / 1024
            self.st_up.configure(text=f"{u:.2f} Mbps")

            self.st_btn.configure(state="normal", text="🚀 START SPEED TEST")
        except Exception as e:
            self.st_btn.configure(state="normal", text="🚀 RETRY")
            messagebox.showerror("Speedtest Failed", str(e))

    # ==========================
    # TAB 6: SETTINGS (NEW)
    # ==========================
    def setup_settings(self):
        self.tab_settings.grid_columnconfigure(0, weight=1)
        
        f = ctk.CTkFrame(self.tab_settings, fg_color="transparent")
        f.pack(pady=40, padx=40, fill="x")
        
        ctk.CTkLabel(f, text="Appearance", font=self.FONT_SUBHEAD).pack(anchor="w", pady=(0, 10))
        
        self.theme_switch = ctk.CTkSwitch(f, text="Dark Mode", command=self.toggle_theme)
        self.theme_switch.select()
        self.theme_switch.pack(anchor="w")
        
        ctk.CTkLabel(f, text="Update Interval (ms)", font=self.FONT_SUBHEAD).pack(anchor="w", pady=(20, 10))
        
        self.slider = ctk.CTkSlider(f, from_=500, to=5000, number_of_steps=9, command=self.change_interval)
        self.slider.set(1000)
        self.slider.pack(anchor="w", fill="x")
        self.lbl_interval = ctk.CTkLabel(f, text="1000 ms")
        self.lbl_interval.pack(anchor="w")

    def toggle_theme(self):
        mode = "Dark" if self.theme_switch.get() == 1 else "Light"
        ctk.set_appearance_mode(mode)
    
    def change_interval(self, val):
        self.update_interval = int(val)
        self.lbl_interval.configure(text=f"{int(val)} ms")

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
            
            us = (u - self.last_upload) / 1024 / (t - self.last_time)
            ds = (d - self.last_download) / 1024 / (t - self.last_time)
            
            session_ul = u - self.start_upload
            session_dl = d - self.start_download
            
            self.dl_label.configure(text=f"⬇ {ds:.1f} KB/s")
            self.ul_label.configure(text=f"⬆ {us:.1f} KB/s")
            self.total_dl_label.configure(text=f"Total: {self.format_bytes(session_dl)}")
            self.total_ul_label.configure(text=f"Total: {self.format_bytes(session_ul)}")
            
            self.y_dl.append(ds)
            self.y_ul.append(us)
            self.line_dl.set_data(self.x_data, self.y_dl)
            self.line_ul.set_data(self.x_data, self.y_ul)
            
            peak = max(max(self.y_dl), max(self.y_ul), 10)
            self.ax.set_ylim(0, peak * 1.2)
            self.canvas.draw()
            
            self.last_upload, self.last_download, self.last_time = u, d, t
        except: pass
            
        self.after(self.update_interval, self.monitor_loop)

    def kill_switch(self):
        os.system("ipconfig /release")
        self.dl_label.configure(text="KILLED", text_color="red")
        self.ul_label.configure(text="OFFLINE", text_color="red")

    def restore_internet(self):
        def _restore():
            os.system("ipconfig /renew")
        threading.Thread(target=_restore).start()
        self.dl_label.configure(text="RESTORING...", text_color="yellow")

    def export_data(self, source):
        data = []
        filename = ""
        
        if source == "connections":
            data = [["Local Port", "Remote", "GeoIP", "Status", "PID"]] + self.current_conns_data
            filename = "ned_connections.csv"
        elif source == "scanner":
            data = [["IP", "MAC", "Type"]] + self.current_scan_data
            filename = "ned_lan_scan.csv"
            
        if not data:
            messagebox.showwarning("Empty", "No data to export.")
            return

        path = filedialog.asksaveasfilename(defaultextension=".csv", initialfile=filename,
                                            filetypes=[("CSV Files", "*.csv")])
        if path:
            try:
                with open(path, 'w', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerows(data)
                messagebox.showinfo("Success", f"Saved to {path}")
            except Exception as e:
                messagebox.showerror("Error", str(e))

    def format_bytes(self, size):
        power = 2**10
        n = 0
        power_labels = {0 : '', 1: 'KB', 2: 'MB', 3: 'GB', 4: 'TB'}
        while size > power:
            size /= power
            n += 1
        return f"{size:.2f} {power_labels[n]}"

if __name__ == "__main__":
    app = ned()
    app.mainloop()