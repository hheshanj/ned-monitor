import customtkinter as ctk
import psutil
import threading
import time
import os
import subprocess
import collections
from tkinter import messagebox

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

class NetMonitorUltimate(ctk.CTk):
    def __init__(self):
        super().__init__()

        # --- FONT CONFIG (Change these to swap vibes) ---
        self.FONT_HEADER = ("Segoe UI", 26, "bold")
        self.FONT_SUBHEAD = ("Segoe UI", 18, "bold")
        self.FONT_BODY = ("Segoe UI", 12)
        self.FONT_BUTTON = ("Segoe UI", 13, "bold")

        # Window Setup
        self.title("NetMonitor Ultimate 💀")
        self.geometry("1000x720")
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # --- TABS ---
        self.tabview = ctk.CTkTabview(self)
        self.tabview.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")
        self.tabview._segmented_button.configure(font=self.FONT_BUTTON) # Change tab font
        
        self.tab_dash = self.tabview.add("Dashboard")
        self.tab_apps = self.tabview.add("App Manager")
        self.tab_conn = self.tabview.add("Connections")
        self.tab_scan = self.tabview.add("LAN Scanner")
        
        # Setup Views
        self.setup_dashboard()
        self.setup_app_manager()
        self.setup_connections()
        self.setup_scanner()

        # Data for Graphs
        self.x_data = list(range(60))
        self.y_dl = collections.deque([0]*60, maxlen=60)
        self.y_ul = collections.deque([0]*60, maxlen=60)
        
        # Init Tracking
        self.last_upload = psutil.net_io_counters().bytes_sent
        self.last_download = psutil.net_io_counters().bytes_recv
        self.last_time = time.time()
        
        # Start Loop
        self.monitor_loop()

    # ==========================
    # TAB 1: DASHBOARD
    # ==========================
    def setup_dashboard(self):
        self.tab_dash.grid_columnconfigure((0, 1), weight=1)
        self.tab_dash.grid_rowconfigure(1, weight=1)
        
        # Labels
        self.dl_label = ctk.CTkLabel(self.tab_dash, text="⬇ 0 KB/s", font=self.FONT_HEADER, text_color="#00ff00")
        self.dl_label.grid(row=0, column=0, pady=10)
        
        self.ul_label = ctk.CTkLabel(self.tab_dash, text="⬆ 0 KB/s", font=self.FONT_HEADER, text_color="#ff9900")
        self.ul_label.grid(row=0, column=1, pady=10)

        # Graph
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
        self.ax.legend(facecolor='#2b2b2b', labelcolor='white', prop={'family': 'Consolas', 'size': 10})
        self.ax.grid(True, color='#444444', linestyle='--', linewidth=0.5)
        
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.tab_dash)
        self.canvas.get_tk_widget().grid(row=1, column=0, columnspan=2, sticky="nsew", padx=10, pady=10)

        # Kill Switch
        self.kill_btn = ctk.CTkButton(self.tab_dash, text="💀 PANIC (KILL INTERNET)", font=self.FONT_BUTTON, 
                                      fg_color="red", hover_color="darkred", height=50, command=self.kill_switch)
        self.kill_btn.grid(row=2, column=0, columnspan=2, pady=20)

    # ==========================
    # TAB 2: APP MANAGER
    # ==========================
    def setup_app_manager(self):
        self.tab_apps.grid_columnconfigure((0, 1), weight=1)
        self.tab_apps.grid_rowconfigure(1, weight=1)
        
        # Controls
        self.control_frame = ctk.CTkFrame(self.tab_apps)
        self.control_frame.grid(row=0, column=0, columnspan=2, padx=10, pady=10, sticky="ew")
        
        self.refresh_btn = ctk.CTkButton(self.control_frame, text="🔄 Refresh Lists", font=self.FONT_BUTTON, command=self.refresh_all_apps)
        self.refresh_btn.pack(side="left", padx=10, pady=10)
        
        ctk.CTkLabel(self.control_frame, text="⚠️ Admin Required", font=self.FONT_BODY, text_color="orange").pack(side="right", padx=10)

        # Lists
        self.active_frame = ctk.CTkScrollableFrame(self.tab_apps, label_text="🟢 Active Apps")
        self.active_frame.grid(row=1, column=0, padx=(10, 5), pady=10, sticky="nsew")
        # Fix internal label fonts if possible, or just accept default for header

        self.blocked_frame = ctk.CTkScrollableFrame(self.tab_apps, label_text="🔴 Blocked Apps")
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
                        active_apps[p.name()] = p.exe()
                    except: pass
        except: pass
        
        for name, path in active_apps.items():
            f = ctk.CTkFrame(self.active_frame)
            f.pack(fill="x", pady=2)
            ctk.CTkLabel(f, text=name, font=self.FONT_BODY).pack(side="left", padx=5)
            ctk.CTkButton(f, text="BLOCK", width=60, font=self.FONT_BUTTON, fg_color="#ff9900", 
                          command=lambda n=name, p=path: self.block_app(n, p)).pack(side="right", padx=5)

        # 2. Blocked Rules
        for w in self.blocked_frame.winfo_children(): w.destroy()
        try:
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            output = subprocess.check_output('netsh advfirewall firewall show rule name=all', startupinfo=startupinfo).decode('utf-8', errors='ignore')
            
            for line in output.split('\n'):
                if "Rule Name:" in line and "_PythonTool" in line:
                    rule_name = line.split("Rule Name:")[1].strip()
                    app_name = rule_name.replace("Block_", "").replace("_PythonTool", "")
                    
                    f = ctk.CTkFrame(self.blocked_frame)
                    f.pack(fill="x", pady=2)
                    ctk.CTkLabel(f, text=app_name, font=self.FONT_BODY, text_color="red").pack(side="left", padx=5)
                    ctk.CTkButton(f, text="UNBLOCK", width=70, font=self.FONT_BUTTON, fg_color="green", 
                                  command=lambda r=rule_name: self.unblock_app(r)).pack(side="right", padx=5)
        except: pass

    def block_app(self, name, path):
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
        self.tab_conn.grid_rowconfigure(1, weight=1)
        
        ctk.CTkButton(self.tab_conn, text="🔄 Refresh Table", font=self.FONT_BUTTON, command=self.get_conns).grid(row=0, column=0, pady=10)
        
        self.conn_text = ctk.CTkTextbox(self.tab_conn, font=self.FONT_BODY)
        self.conn_text.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)

    def get_conns(self):
        self.conn_text.delete("1.0", "end")
        header = f"{'L.PORT':<10} {'REMOTE IP':<25} {'STATUS':<15} {'PID'}\n" + "-"*65 + "\n"
        self.conn_text.insert("1.0", header)
        try:
            for c in psutil.net_connections(kind='inet'):
                if c.status == 'ESTABLISHED':
                    r = f"{c.raddr.ip}:{c.raddr.port}" if c.raddr else "N/A"
                    line = f"{c.laddr.port:<10} {r:<25} {c.status:<15} {c.pid}\n"
                    self.conn_text.insert("end", line)
        except: self.conn_text.insert("end", "Error reading connections.")

    # ==========================
    # TAB 4: SCANNER
    # ==========================
    def setup_scanner(self):
        self.tab_scan.grid_columnconfigure(0, weight=1)
        self.tab_scan.grid_rowconfigure(1, weight=1)

        ctk.CTkButton(self.tab_scan, text="📡 Scan Local Network", font=self.FONT_BUTTON, command=self.run_scan).grid(row=0, column=0, pady=10)
        
        self.scan_text = ctk.CTkTextbox(self.tab_scan, font=self.FONT_BODY)
        self.scan_text.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)

    def run_scan(self):
        self.scan_text.delete("1.0", "end")
        self.scan_text.insert("1.0", "Scanning ARP table...\n\n")
        try:
            output = os.popen('arp -a').read()
            self.scan_text.insert("end", output)
        except: self.scan_text.insert("end", "Scan failed.")

    # ==========================
    # CORE LOOP
    # ==========================
    def monitor_loop(self):
        try:
            u = psutil.net_io_counters().bytes_sent
            d = psutil.net_io_counters().bytes_recv
            t = time.time()
            
            us = (u - self.last_upload) / 1024 / (t - self.last_time)
            ds = (d - self.last_download) / 1024 / (t - self.last_time)
            
            self.dl_label.configure(text=f"⬇ {ds:.1f} KB/s")
            self.ul_label.configure(text=f"⬆ {us:.1f} KB/s")
            
            self.y_dl.append(ds)
            self.y_ul.append(us)
            self.line_dl.set_data(self.x_data, self.y_dl)
            self.line_ul.set_data(self.x_data, self.y_ul)
            
            # Auto-scale Y axis
            peak = max(max(self.y_dl), max(self.y_ul), 10)
            self.ax.set_ylim(0, peak * 1.2)
            self.canvas.draw()
            
            self.last_upload, self.last_download, self.last_time = u, d, t
        except: pass
        self.after(1000, self.monitor_loop)

    def kill_switch(self):
        os.system("ipconfig /release")
        self.dl_label.configure(text="KILLED", text_color="red")
        self.ul_label.configure(text="OFFLINE", text_color="red")

if __name__ == "__main__":
    app = NetMonitorUltimate()
    app.mainloop()