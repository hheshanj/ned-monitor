import customtkinter as ctk
import psutil
import threading
import time
import socket
import os
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import collections

# Theme Config
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("green")

class NedMonitor(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Window Setup
        self.title("NetMonitor Ultimate 💀")
        self.geometry("900x650")
        
        # Grid Layout
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # --- TABS ---
        self.tabview = ctk.CTkTabview(self)
        self.tabview.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")
        
        self.tab_dash = self.tabview.add("Dashboard")
        self.tab_conn = self.tabview.add("Connections")
        self.tab_scan = self.tabview.add("LAN Scanner")
        
        # Setup Tabs
        self.setup_dashboard()
        self.setup_connections()
        self.setup_scanner()

        # Data Containers for Graph (Last 60 points)
        self.x_data = list(range(60))
        self.y_dl = collections.deque([0]*60, maxlen=60)
        self.y_ul = collections.deque([0]*60, maxlen=60)
        
        # Start Loops
        self.last_upload = psutil.net_io_counters().bytes_sent
        self.last_download = psutil.net_io_counters().bytes_recv
        self.last_time = time.time()
        
        self.monitor_loop()

    # --- TAB 1: DASHBOARD ---
    def setup_dashboard(self):
        self.tab_dash.grid_columnconfigure((0, 1), weight=1)
        
        # Stats Row
        self.dl_label = ctk.CTkLabel(self.tab_dash, text="⬇ 0 KB/s", font=("Consolas", 24, "bold"), text_color="#00ff00")
        self.dl_label.grid(row=0, column=0, pady=10)
        
        self.ul_label = ctk.CTkLabel(self.tab_dash, text="⬆ 0 KB/s", font=("Consolas", 24, "bold"), text_color="#ff9900")
        self.ul_label.grid(row=0, column=1, pady=10)

        # Graph Area
        self.fig = Figure(figsize=(5, 3), dpi=100, facecolor='#2b2b2b')
        self.ax = self.fig.add_subplot(111)
        self.ax.set_facecolor('#2b2b2b')
        self.ax.tick_params(colors='white')
        self.ax.spines['bottom'].set_color('white')
        self.ax.spines['left'].set_color('white')
        
        # Init Lines
        self.line_dl, = self.ax.plot([], [], color='#00ff00', label='Download')
        self.line_ul, = self.ax.plot([], [], color='#ff9900', label='Upload')
        self.ax.legend(facecolor='#2b2b2b', labelcolor='white')
        
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.tab_dash)
        self.canvas.get_tk_widget().grid(row=1, column=0, columnspan=2, sticky="nsew", padx=10, pady=10)

        # Kill Switch
        self.kill_btn = ctk.CTkButton(self.tab_dash, text="💀 KILL INTERNET", fg_color="red", hover_color="darkred", command=self.kill_switch)
        self.kill_btn.grid(row=2, column=0, columnspan=2, pady=20)

    # --- TAB 2: CONNECTIONS (Netstat) ---
    def setup_connections(self):
        self.tab_conn.grid_columnconfigure(0, weight=1)
        self.tab_conn.grid_rowconfigure(1, weight=1)
        
        self.refresh_conn_btn = ctk.CTkButton(self.tab_conn, text="🔄 Refresh Connections", command=self.get_active_connections)
        self.refresh_conn_btn.grid(row=0, column=0, pady=10)

        self.conn_textbox = ctk.CTkTextbox(self.tab_conn, font=("Consolas", 12))
        self.conn_textbox.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)

    # --- TAB 3: LAN SCANNER ---
    def setup_scanner(self):
        self.tab_scan.grid_columnconfigure(0, weight=1)
        
        self.scan_btn = ctk.CTkButton(self.tab_scan, text="📡 Scan Local Network", command=self.start_scan_thread)
        self.scan_btn.grid(row=0, column=0, pady=10)
        
        self.scan_status = ctk.CTkLabel(self.tab_scan, text="Ready to scan", text_color="gray")
        self.scan_status.grid(row=1, column=0)

        self.scan_results = ctk.CTkTextbox(self.tab_scan, font=("Consolas", 12))
        self.scan_results.grid(row=2, column=0, sticky="nsew", padx=10, pady=10)

    # --- LOGIC: MONITOR LOOP ---
    def monitor_loop(self):
        # Calc Speeds
        curr_ul = psutil.net_io_counters().bytes_sent
        curr_dl = psutil.net_io_counters().bytes_recv
        curr_time = time.time()
        
        ul_speed = (curr_ul - self.last_upload) / 1024 / (curr_time - self.last_time)
        dl_speed = (curr_dl - self.last_download) / 1024 / (curr_time - self.last_time)
        
        # Update Labels
        self.dl_label.configure(text=f"⬇ {dl_speed:.1f} KB/s")
        self.ul_label.configure(text=f"⬆ {ul_speed:.1f} KB/s")
        
        # Update Graph Data
        self.y_dl.append(dl_speed)
        self.y_ul.append(ul_speed)
        
        self.line_dl.set_data(self.x_data, self.y_dl)
        self.line_ul.set_data(self.x_data, self.y_ul)
        self.ax.set_ylim(0, max(max(self.y_dl), max(self.y_ul), 10) * 1.2) # Auto scale Y axis
        self.ax.set_xlim(0, 60)
        self.canvas.draw()

        # Reset
        self.last_upload = curr_ul
        self.last_download = curr_dl
        self.last_time = curr_time
        
        self.after(1000, self.monitor_loop)

    # --- LOGIC: CONNECTIONS ---
    def get_active_connections(self):
        self.conn_textbox.delete("0.0", "end")
        self.conn_textbox.insert("0.0", f"{'L.PORT':<10} {'REMOTE IP':<25} {'STATUS':<15} {'PID'}\n")
        self.conn_textbox.insert("end", "-"*60 + "\n")
        
        try:
            for conn in psutil.net_connections(kind='inet'):
                if conn.status == 'ESTABLISHED':
                    laddr = f"{conn.laddr.port}"
                    raddr = f"{conn.raddr.ip}:{conn.raddr.port}" if conn.raddr else "N/A"
                    self.conn_textbox.insert("end", f"{laddr:<10} {raddr:<25} {conn.status:<15} {conn.pid}\n")
        except Exception as e:
            self.conn_textbox.insert("end", f"Error: {e} (Try running as Admin)")

    # --- LOGIC: SCANNER ---
    def start_scan_thread(self):
        self.scan_btn.configure(state="disabled")
        self.scan_status.configure(text="Scanning... This may take a moment.")
        threading.Thread(target=self.scan_network).start()

    def scan_network(self):
        # Simple ARP scan by reading system ARP table (Fast & Safe)
        # For a true 'Ping Sweep', we'd need to loop through IPs, which is slower in Python.
        output_text = "IP Address\t\tPhysical Address\tType\n"
        output_text += "-"*50 + "\n"
        
        try:
            # Run command line ARP check
            cmd = os.popen('arp -a').read()
            self.update_scan_ui(cmd)
        except Exception as e:
            self.update_scan_ui(f"Error: {e}")

    def update_scan_ui(self, text):
        self.scan_results.delete("0.0", "end")
        self.scan_results.insert("0.0", text)
        self.scan_status.configure(text="Scan Complete.")
        self.scan_btn.configure(state="normal")

    # --- LOGIC: KILL SWITCH ---
    def kill_switch(self):
        # Windows command to release IP
        os.system("ipconfig /release")
        self.dl_label.configure(text="INTERNET KILLED", text_color="red")

if __name__ == "__main__":
    app = NedMonitor()
    app.mainloop()