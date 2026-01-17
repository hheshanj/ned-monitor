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

class Ned(ctk.CTk):
    def __init__(self):
        super().__init__()

        # --- FONT CONFIG ---
        self.FONT_HEADER = ("Lucida Console", 26, "bold")
        self.FONT_SUBHEAD = ("Lucida Console", 16, "bold")
        self.FONT_BODY = ("Lucida Console", 12)
        self.FONT_MONO = ("Lucida Console", 12)
        self.FONT_BUTTON = ("Lucida Console", 13, "bold")

        # Window Setup
        self.title("Ned 👓")
        self.geometry("1100x750")
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # --- TABS ---
        self.tabview = ctk.CTkTabview(self)
        self.tabview.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")
        self.tabview._segmented_button.configure(font=self.FONT_BUTTON) 
        
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
        
        # --- INIT TRACKING (NEW) ---
        # We capture the system totals at the moment the app starts
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
        self.tab_dash.grid_rowconfigure(2, weight=1) # Graph expands
        
        # --- Speed Labels ---
        self.dl_label = ctk.CTkLabel(self.tab_dash, text="⬇ 0 KB/s", font=self.FONT_HEADER, text_color="#00ff00")
        self.dl_label.grid(row=0, column=0, pady=(20, 5))
        
        self.ul_label = ctk.CTkLabel(self.tab_dash, text="⬆ 0 KB/s", font=self.FONT_HEADER, text_color="#ff9900")
        self.ul_label.grid(row=0, column=1, pady=(20, 5))

        # --- Session Totals (NEW) ---
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
        self.ax.legend(facecolor='#2b2b2b', labelcolor='white', prop={'family': 'Consolas', 'size': 10})
        self.ax.grid(True, color='#444444', linestyle='--', linewidth=0.5)
        
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.tab_dash)
        self.canvas.get_tk_widget().grid(row=2, column=0, columnspan=2, sticky="nsew", padx=10, pady=10)

        # Kill Switch
        self.kill_btn = ctk.CTkButton(self.tab_dash, text="💀 PANIC (KILL INTERNET)", font=self.FONT_BUTTON, 
                                      fg_color="#cf0000", hover_color="#8a0000", height=50, command=self.kill_switch)
        self.kill_btn.grid(row=3, column=0, columnspan=2, pady=20)
    # ==========================
    # TAB 2: APP MANAGER (BEAUTIFIED)
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
                        active_apps[p.name()] = p.exe()
                    except: pass
        except: pass
        
        if not active_apps:
             ctk.CTkLabel(self.active_frame, text="No active connections found.", font=self.FONT_BODY, text_color="gray").pack(pady=20)

        for name, path in active_apps.items():
            f = ctk.CTkFrame(self.active_frame, fg_color="#2b2b2b", corner_radius=6)
            f.pack(fill="x", pady=4, padx=5)
            
            ctk.CTkLabel(f, text=f"📦 {name}", font=self.FONT_BODY).pack(side="left", padx=10, pady=10)
            ctk.CTkButton(f, text="BLOCK", width=60, font=("Segoe UI", 11, "bold"), fg_color="#ff9900", hover_color="#b36b00",
                          command=lambda n=name, p=path: self.block_app(n, p)).pack(side="right", padx=10)

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
                    
                    f = ctk.CTkFrame(self.blocked_frame, fg_color="#3d0000", corner_radius=6) # Red tint for blocked
                    f.pack(fill="x", pady=4, padx=5)
                    
                    ctk.CTkLabel(f, text=f"🔒 {app_name}", font=self.FONT_BODY, text_color="#ffcccc").pack(side="left", padx=10, pady=10)
                    ctk.CTkButton(f, text="UNBLOCK", width=70, font=("Segoe UI", 11, "bold"), fg_color="#2eb82e", hover_color="#238f23",
                                  command=lambda r=rule_name: self.unblock_app(r)).pack(side="right", padx=10)
            if not found:
                 ctk.CTkLabel(self.blocked_frame, text="No apps blocked.", font=self.FONT_BODY, text_color="gray").pack(pady=20)
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
    # TAB 3: CONNECTIONS (BEAUTIFIED)
    # ==========================
    def setup_connections(self):
        self.tab_conn.grid_columnconfigure(0, weight=1)
        
        # FIX 1: Tell Row 2 (The List) to expand, NOT Row 1 (The Headers)
        self.tab_conn.grid_rowconfigure(0, weight=0) # Top bar (Compact)
        self.tab_conn.grid_rowconfigure(1, weight=0) # Headers (Compact)
        self.tab_conn.grid_rowconfigure(2, weight=1) # List (Expands to fill space)
        
        # Top Bar
        top_bar = ctk.CTkFrame(self.tab_conn, fg_color="transparent")
        top_bar.grid(row=0, column=0, sticky="ew", padx=10, pady=5)
        
        ctk.CTkButton(top_bar, text="🔄 Refresh Table", font=self.FONT_BUTTON, command=self.get_conns).pack(side="left")
        ctk.CTkLabel(top_bar, text="Only showing ESTABLISHED connections", text_color="gray", font=("Segoe UI", 10)).pack(side="right", padx=10)
        
        # Headers
        header_frame = ctk.CTkFrame(self.tab_conn, height=30, fg_color="#1a1a1a")
        header_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(5,0))
        
        # Using Labels for headers is fine (you don't usually copy headers)
        ctk.CTkLabel(header_frame, text="LOCAL PORT", width=100, font=("Segoe UI", 11, "bold"), anchor="w").pack(side="left", padx=10)
        ctk.CTkLabel(header_frame, text="REMOTE IP", width=200, font=("Segoe UI", 11, "bold"), anchor="w").pack(side="left", padx=10)
        ctk.CTkLabel(header_frame, text="STATUS", width=100, font=("Segoe UI", 11, "bold"), anchor="w").pack(side="left", padx=10)
        ctk.CTkLabel(header_frame, text="PID", width=80, font=("Segoe UI", 11, "bold"), anchor="w").pack(side="left", padx=10)

        # Scrollable Area
        self.conn_scroll = ctk.CTkScrollableFrame(self.tab_conn, fg_color="transparent")
        self.conn_scroll.grid(row=2, column=0, sticky="nsew", padx=10, pady=5)

    def get_conns(self):
        for w in self.conn_scroll.winfo_children(): w.destroy()
        
        try:
            count = 0
            for c in psutil.net_connections(kind='inet'):
                if c.status == 'ESTABLISHED':
                    count += 1
                    r = f"{c.raddr.ip}:{c.raddr.port}" if c.raddr else "N/A"
                    
                    # Create Card
                    card = ctk.CTkFrame(self.conn_scroll, fg_color="#2b2b2b")
                    card.pack(fill="x", pady=2)
                    
                    # FIX 2: Use CTkEntry instead of CTkLabel
                    # state="readonly" lets you select/copy but not type
                    # fg_color="transparent" and border_width=0 makes it look like a label
                    
                    # Local Port
                    self.create_selectable_label(card, str(c.laddr.port), 100, "#00ccff")
                    
                    # Remote IP
                    self.create_selectable_label(card, str(r), 200, "white")
                    
                    # Status (Label is fine here, usually don't need to copy 'ESTABLISHED')
                    ctk.CTkLabel(card, text=f"🟢 {c.status}", width=120, font=self.FONT_MONO, anchor="w", text_color="#00ff00").pack(side="left", padx=10)
                    
                    # PID
                    self.create_selectable_label(card, str(c.pid), 80, "gray")

            if count == 0:
                 ctk.CTkLabel(self.conn_scroll, text="No established connections.", font=self.FONT_BODY).pack(pady=20)

        except Exception as e: 
            print(e)
            ctk.CTkLabel(self.conn_scroll, text="Error reading connections (Need Admin?)", text_color="red").pack(pady=20)

    # Helper function to make cleaner code
    def create_selectable_label(self, parent, text, width, color):
        entry = ctk.CTkEntry(parent, width=width, font=self.FONT_MONO, text_color=color,
                             fg_color="transparent", border_width=0)
        entry.insert(0, text)
        entry.configure(state="readonly")
        entry.pack(side="left", padx=20, pady=5)

    def format_bytes(self, size):
        # 1024^2 = 1,048,576 (MB)
        # 1024^3 = 1,073,741,824 (GB)
        power = 2**10
        n = 0
        power_labels = {0 : '', 1: 'KB', 2: 'MB', 3: 'GB', 4: 'TB'}
        while size > power:
            size /= power
            n += 1
        return f"{size:.2f} {power_labels[n]}"

    # ==========================
    # TAB 4: SCANNER (BEAUTIFIED)
    # ==========================
    def setup_scanner(self):
        self.tab_scan.grid_columnconfigure(0, weight=1)
        # Ensure the list row expands to fill empty space
        self.tab_scan.grid_rowconfigure(0, weight=0) # Button
        self.tab_scan.grid_rowconfigure(1, weight=0) # Headers
        self.tab_scan.grid_rowconfigure(2, weight=1) # List (Expands)

        ctk.CTkButton(self.tab_scan, text="📡 Scan Local Network (ARP)", font=self.FONT_BUTTON, command=self.run_scan).grid(row=0, column=0, pady=20)
        
        # Headers
        h_frame = ctk.CTkFrame(self.tab_scan, height=30, fg_color="#1a1a1a")
        h_frame.grid(row=1, column=0, sticky="ew", padx=20)
        
        ctk.CTkLabel(h_frame, text="IP ADDRESS", width=200, font=("Segoe UI", 11, "bold"), anchor="w").pack(side="left", padx=20)
        ctk.CTkLabel(h_frame, text="MAC ADDRESS", width=200, font=("Segoe UI", 11, "bold"), anchor="w").pack(side="left", padx=20)
        ctk.CTkLabel(h_frame, text="TYPE", width=100, font=("Segoe UI", 11, "bold"), anchor="w").pack(side="left", padx=20)

        # Results Area
        self.scan_scroll = ctk.CTkScrollableFrame(self.tab_scan, fg_color="transparent")
        self.scan_scroll.grid(row=2, column=0, sticky="nsew", padx=20, pady=5)

    def run_scan(self):
        for w in self.scan_scroll.winfo_children(): w.destroy()
        
        try:
            # We parse 'arp -a' output
            output = os.popen('arp -a').read()
            lines = output.splitlines()
            
            found_any = False
            for line in lines:
                parts = line.split()
                # Basic check if line looks like an ARP entry (IP, MAC, Type)
                if len(parts) == 3 and parts[2] in ['dynamic', 'static']:
                    found_any = True
                    ip, mac, type_ = parts[0], parts[1], parts[2]
                    
                    card = ctk.CTkFrame(self.scan_scroll, fg_color="#2b2b2b")
                    card.pack(fill="x", pady=3)
                    
                    icon = "🖥️" if type_ == 'dynamic' else "⚙️"
                    
                    # IP Address (Selectable)
                    self.create_selectable_label(card, f"{icon} {ip}", 200, "#00ccff")

                    # MAC Address (Selectable)
                    self.create_selectable_label(card, mac, 200, "white")
                    
                    # Type (Label is fine, usually don't need to copy 'dynamic')
                    ctk.CTkLabel(card, text=type_.upper(), width=100, font=self.FONT_MONO, anchor="w", text_color="gray").pack(side="left", padx=20)

            if not found_any:
                ctk.CTkLabel(self.scan_scroll, text="No devices found or ARP table empty.", font=self.FONT_BODY).pack(pady=20)

        except Exception as e: 
             ctk.CTkLabel(self.scan_scroll, text="Scan failed.", text_color="red").pack(pady=20)

    # ==========================
    # CORE LOOP
    # ==========================
    def monitor_loop(self):
        try:
            # Get current system-wide totals
            net_io = psutil.net_io_counters()
            u = net_io.bytes_sent
            d = net_io.bytes_recv
            t = time.time()
            
            # 1. Calculate Speed (Instantaneous)
            us = (u - self.last_upload) / 1024 / (t - self.last_time)
            ds = (d - self.last_download) / 1024 / (t - self.last_time)
            
            # 2. Calculate Session Total (Accumulated)
            session_ul = u - self.start_upload
            session_dl = d - self.start_download
            
            # Update Speed Labels
            self.dl_label.configure(text=f"⬇ {ds:.1f} KB/s")
            self.ul_label.configure(text=f"⬆ {us:.1f} KB/s")

            # Update Session Labels (NEW)
            self.total_dl_label.configure(text=f"Total: {self.format_bytes(session_dl)}")
            self.total_ul_label.configure(text=f"Total: {self.format_bytes(session_ul)}")
            
            # Update Graph
            self.y_dl.append(ds)
            self.y_ul.append(us)
            self.line_dl.set_data(self.x_data, self.y_dl)
            self.line_ul.set_data(self.x_data, self.y_ul)
            
            peak = max(max(self.y_dl), max(self.y_ul), 10)
            self.ax.set_ylim(0, peak * 1.2)
            self.canvas.draw()
            
            # Reset for next loop
            self.last_upload, self.last_download, self.last_time = u, d, t
        except Exception as e:
            print(e)
            pass
            
        self.after(1000, self.monitor_loop)

if __name__ == "__main__":
    app = Ned()
    app.mainloop()