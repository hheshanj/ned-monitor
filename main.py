import customtkinter as ctk
import psutil
import os
import subprocess
from tkinter import messagebox

# ... (Keep your previous imports like threading, time, etc.)

class NetMonitorUltimate(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("NetMonitor Ultimate 💀")
        self.geometry("900x700")
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # --- TABS ---
        self.tabview = ctk.CTkTabview(self)
        self.tabview.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")
        
        self.tab_dash = self.tabview.add("Dashboard")
        self.tab_apps = self.tabview.add("App Manager")  # <--- NEW TAB
        
        # Setup Tabs
        self.setup_dashboard()
        self.setup_app_manager() # <--- NEW FUNCTION

        # ... (Keep your existing loop logic) ...

    # ... (Keep setup_dashboard code from before) ...

    # --- NEW: APP MANAGER TAB ---
    def setup_app_manager(self):
        self.tab_apps.grid_columnconfigure(0, weight=1)
        self.tab_apps.grid_rowconfigure(1, weight=1)
        
        # Controls
        self.control_frame = ctk.CTkFrame(self.tab_apps)
        self.control_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        
        self.refresh_btn = ctk.CTkButton(self.control_frame, text="🔄 Scan Active Apps", command=self.scan_active_apps)
        self.refresh_btn.pack(side="left", padx=10, pady=10)
        
        self.admin_label = ctk.CTkLabel(self.control_frame, text="⚠️ 'Block' requires Admin Rights", text_color="orange")
        self.admin_label.pack(side="right", padx=10)

        # Scrollable List for Apps
        self.apps_scroll = ctk.CTkScrollableFrame(self.tab_apps, label_text="Apps Consuming Data")
        self.apps_scroll.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")
        self.apps_scroll.grid_columnconfigure(0, weight=1)

    def scan_active_apps(self):
        # Clear previous list
        for widget in self.apps_scroll.winfo_children():
            widget.destroy()

        # Find apps with ESTABLISHED connections
        active_apps = {}
        try:
            for conn in psutil.net_connections(kind='inet'):
                if conn.status == 'ESTABLISHED':
                    try:
                        proc = psutil.Process(conn.pid)
                        app_name = proc.name()
                        app_path = proc.exe() # Needed for blocking
                        
                        # Group by name so we don't list Chrome 50 times
                        if app_name not in active_apps:
                            active_apps[app_name] = {'pid': conn.pid, 'path': app_path}
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
        except Exception as e:
            print(f"Scan Error: {e}")

        # Render the list
        row = 0
        for app_name, data in active_apps.items():
            self.create_app_row(row, app_name, data['pid'], data['path'])
            row += 1
            
        if not active_apps:
            label = ctk.CTkLabel(self.apps_scroll, text="No active data connections found.")
            label.pack(pady=20)

    def create_app_row(self, row, name, pid, path):
        # A container for each app row
        frame = ctk.CTkFrame(self.apps_scroll)
        frame.grid(row=row, column=0, padx=5, pady=5, sticky="ew")
        
        # App Name Label
        lbl = ctk.CTkLabel(frame, text=f"📦 {name} (PID: {pid})", font=("Consolas", 14, "bold"), anchor="w")
        lbl.pack(side="left", padx=10, pady=5)
        
        # Kill Button (Force Quit)
        kill_btn = ctk.CTkButton(frame, text="💀 KILL", width=60, fg_color="#ff5555", hover_color="darkred",
                                 command=lambda: self.kill_app(pid))
        kill_btn.pack(side="right", padx=5, pady=5)

        # Block Button (Firewall)
        block_btn = ctk.CTkButton(frame, text="🛡️ BLOCK NET", width=80, fg_color="#ff9900", hover_color="#b36b00",
                                  command=lambda: self.block_app_internet(name, path))
        block_btn.pack(side="right", padx=5, pady=5)

    # --- ACTION: FORCE QUIT ---
    def kill_app(self, pid):
        try:
            p = psutil.Process(pid)
            p.terminate() # or p.kill()
            self.scan_active_apps() # Refresh list
            print(f"Killed {pid}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not kill process: {e}")

    # --- ACTION: BLOCK INTERNET (Requires Admin) ---
    def block_app_internet(self, name, path):
        # We use Windows 'netsh' command to add a firewall rule
        rule_name = f"Block_{name}_PythonTool"
        
        # Command: netsh advfirewall firewall add rule name="..." dir=out action=block program="..."
        cmd = f'netsh advfirewall firewall add rule name="{rule_name}" dir=out action=block program="{path}" enable=yes'
        
        try:
            # Creation flag suppresses the console window popping up
            subprocess.run(cmd, shell=True, check=True, creationflags=subprocess.CREATE_NO_WINDOW)
            messagebox.showinfo("Success", f"Blocked Internet for {name}!\n\nTo undo, delete the rule '{rule_name}' in Windows Firewall.")
        except subprocess.CalledProcessError:
            messagebox.showerror("Failed", "Could not add Firewall rule.\n\nDid you run as Administrator?")

# ... (Run app logic)