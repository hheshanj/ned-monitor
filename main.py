import customtkinter as ctk
import psutil
import threading
import time

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("green")  # Matrix vibes

class NetMonitor(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("NetMonitor v1 👁️")
        self.geometry("500x400")
        
        # Grid Layout
        self.grid_columnconfigure((0, 1), weight=1)

        # --- HEADERS ---
        self.header = ctk.CTkLabel(self, text="SYSTEM COMMAND CENTER", font=("Consolas", 20, "bold"), text_color="#00ff00")
        self.header.grid(row=0, column=0, columnspan=2, pady=20)

        # --- NETWORK SECTION ---
        self.net_frame = ctk.CTkFrame(self)
        self.net_frame.grid(row=1, column=0, columnspan=2, padx=20, pady=10, sticky="ew")
        
        self.dl_label = ctk.CTkLabel(self.net_frame, text="⬇ Download: 0 KB/s", font=("Consolas", 14))
        self.dl_label.pack(side="left", padx=20, pady=10)
        
        self.ul_label = ctk.CTkLabel(self.net_frame, text="⬆ Upload: 0 KB/s", font=("Consolas", 14))
        self.ul_label.pack(side="right", padx=20, pady=10)

        # --- CPU SECTION ---
        self.cpu_label = ctk.CTkLabel(self, text="CPU Usage: 0%", font=("Roboto", 12))
        self.cpu_label.grid(row=2, column=0, pady=(20, 0))
        
        self.cpu_bar = ctk.CTkProgressBar(self, orientation="horizontal", width=200)
        self.cpu_bar.grid(row=3, column=0, padx=20, pady=5)
        self.cpu_bar.set(0)

        # --- RAM SECTION ---
        self.ram_label = ctk.CTkLabel(self, text="RAM Usage: 0%", font=("Roboto", 12))
        self.ram_label.grid(row=2, column=1, pady=(20, 0))
        
        self.ram_bar = ctk.CTkProgressBar(self, orientation="horizontal", width=200, progress_color="orange")
        self.ram_bar.grid(row=3, column=1, padx=20, pady=5)
        self.ram_bar.set(0)

        # --- START MONITORING ---
        self.last_upload = psutil.net_io_counters().bytes_sent
        self.last_download = psutil.net_io_counters().bytes_recv
        self.last_time = time.time()
        
        self.monitor_loop()

    def monitor_loop(self):
        # 1. CPU & RAM
        cpu = psutil.cpu_percent()
        ram = psutil.virtual_memory().percent
        
        self.cpu_label.configure(text=f"CPU Usage: {cpu}%")
        self.cpu_bar.set(cpu / 100)
        
        self.ram_label.configure(text=f"RAM Usage: {ram}%")
        self.ram_bar.set(ram / 100)

        # 2. Network Speed Math
        current_upload = psutil.net_io_counters().bytes_sent
        current_download = psutil.net_io_counters().bytes_recv
        current_time = time.time()

        # Bytes changed since last check
        ul_diff = current_upload - self.last_upload
        dl_diff = current_download - self.last_download
        
        # Convert to KB/s (Basic math)
        ul_speed = (ul_diff / 1024) / (current_time - self.last_time)
        dl_speed = (dl_diff / 1024) / (current_time - self.last_time)

        self.ul_label.configure(text=f"⬆ Upload: {ul_speed:.1f} KB/s")
        self.dl_label.configure(text=f"⬇ Download: {dl_speed:.1f} KB/s")

        # Reset counters for next loop
        self.last_upload = current_upload
        self.last_download = current_download
        self.last_time = current_time

        # Update every 1000ms (1 second)
        self.after(1000, self.monitor_loop)

if __name__ == "__main__":
    app = NetMonitor()
    app.mainloop()