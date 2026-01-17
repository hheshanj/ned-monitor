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
  # --- APP MANAGER TAB (Updated) ---
    def setup_app_manager(self):
        self.tab_apps.grid_columnconfigure((0, 1), weight=1) # Split into 2 columns
        self.tab_apps.grid_rowconfigure(1, weight=1)
        
        # --- CONTROLS ---
        self.control_frame = ctk.CTkFrame(self.tab_apps)
        self.control_frame.grid(row=0, column=0, columnspan=2, padx=10, pady=10, sticky="ew")
        
        self.refresh_btn = ctk.CTkButton(self.control_frame, text="🔄 Refresh All", command=self.refresh_all_apps)
        self.refresh_btn.pack(side="left", padx=10, pady=10)
        
        self.admin_label = ctk.CTkLabel(self.control_frame, text="⚠️ Admin Rights Required", text_color="orange")
        self.admin_label.pack(side="right", padx=10)

        # --- LEFT: ACTIVE APPS ---
        self.active_frame = ctk.CTkScrollableFrame(self.tab_apps, label_text="🟢 Active Data Hogs")
        self.active_frame.grid(row=1, column=0, padx=(10, 5), pady=10, sticky="nsew")

        # --- RIGHT: BLOCKED RULES ---
        self.blocked_frame = ctk.CTkScrollableFrame(self.tab_apps, label_text="🔴 Blocked / Jailed")
        self.blocked_frame.grid(row=1, column=1, padx=(5, 10), pady=10, sticky="nsew")

    def refresh_all_apps(self):
        self.scan_active_apps()
        self.scan_blocked_rules()

    # --- 1. SCAN ACTIVE APPS ---
    def scan_active_apps(self):
        for widget in self.active_frame.winfo_children(): widget.destroy()

        active_apps = {}
        try:
            for conn in psutil.net_connections(kind='inet'):
                if conn.status == 'ESTABLISHED':
                    try:
                        proc = psutil.Process(conn.pid)
                        active_apps[proc.name()] = {'pid': conn.pid, 'path': proc.exe()}
                    except: pass
        except: pass

        for name, data in active_apps.items():
            self.create_active_row(name, data['pid'], data['path'])
            
        if not active_apps:
            ctk.CTkLabel(self.active_frame, text="No active connections.").pack(pady=10)

    def create_active_row(self, name, pid, path):
        f = ctk.CTkFrame(self.active_frame)
        f.pack(fill="x", pady=2)
        
        ctk.CTkLabel(f, text=f"{name}", font=("Consolas", 12, "bold")).pack(side="left", padx=5)
        
        # BLOCK BUTTON
        ctk.CTkButton(f, text="🛡️ BLOCK", width=60, fg_color="#ff9900", hover_color="#b36b00",
                      command=lambda: self.block_app(name, path)).pack(side="right", padx=5, pady=2)

    # --- 2. SCAN BLOCKED RULES ---
    def scan_blocked_rules(self):
        for widget in self.blocked_frame.winfo_children(): widget.destroy()

        # We use netsh to list rules and parse the text output
        # Look for rules named "Block_X_PythonTool"
        try:
            # Run command, hide window
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            
            output = subprocess.check_output('netsh advfirewall firewall show rule name=all', 
                                           startupinfo=startupinfo).decode('utf-8', errors='ignore')
            
            # Simple parsing logic
            found_rules = []
            for line in output.split('\n'):
                if "Rule Name:" in line and "_PythonTool" in line:
                    rule_name = line.split("Rule Name:")[1].strip()
                    app_name = rule_name.replace("Block_", "").replace("_PythonTool", "")
                    found_rules.append((rule_name, app_name))

            for rule, app in found_rules:
                self.create_blocked_row(rule, app)
                
            if not found_rules:
                ctk.CTkLabel(self.blocked_frame, text="No active blocks.").pack(pady=10)

        except Exception as e:
            ctk.CTkLabel(self.blocked_frame, text="Error reading Firewall").pack()

    def create_blocked_row(self, rule_name, app_name):
        f = ctk.CTkFrame(self.blocked_frame)
        f.pack(fill="x", pady=2)
        
        ctk.CTkLabel(f, text=f"{app_name}", text_color="red").pack(side="left", padx=5)
        
        # UNBLOCK BUTTON
        ctk.CTkButton(f, text="🔓 UNBLOCK", width=70, fg_color="green", hover_color="darkgreen",
                      command=lambda: self.unblock_app(rule_name)).pack(side="right", padx=5, pady=2)

    # --- ACTIONS ---
    def block_app(self, name, path):
        rule_name = f"Block_{name}_PythonTool"
        cmd = f'netsh advfirewall firewall add rule name="{rule_name}" dir=out action=block program="{path}" enable=yes'
        self.run_netsh(cmd)
        self.refresh_all_apps() # Move from Active -> Blocked list

    def unblock_app(self, rule_name):
        cmd = f'netsh advfirewall firewall delete rule name="{rule_name}"'
        self.run_netsh(cmd)
        self.refresh_all_apps() # Remove from Blocked list

    def run_netsh(self, cmd):
        try:
            subprocess.run(cmd, shell=True, check=True, creationflags=subprocess.CREATE_NO_WINDOW)
        except:
            messagebox.showerror("Error", "Action Failed. Run as Admin!")
# ... (Run app logic)