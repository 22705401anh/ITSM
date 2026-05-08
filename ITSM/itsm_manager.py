import sys
import os

# Fix Tkinter in virtual environments for Python 3.13
tcl_dir = os.path.join(sys.base_prefix, "tcl", "tcl8.6")
tk_dir = os.path.join(sys.base_prefix, "tcl", "tk8.6")
if os.path.exists(tcl_dir):
    os.environ["TCL_LIBRARY"] = tcl_dir
if os.path.exists(tk_dir):
    os.environ["TK_LIBRARY"] = tk_dir

import subprocess
import threading
import time
import queue
import datetime

# --- Auto-Install Dependencies ---
def install_and_import():
    try:
        import customtkinter as ctk
        import psutil
        return ctk, psutil
    except ImportError:
        print("Missing required dependencies. Auto-installing customtkinter and psutil...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "customtkinter", "psutil"])
        os.execv(sys.executable, ['python'] + sys.argv)

ctk, psutil = install_and_import()
# ---------------------------------

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class ITSMServiceManager(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("ITSM Service Manager")
        self.geometry("1300x900")
        self.minsize(1000, 700)

        # State mapping
        self.services = {
            "fastapi": {
                "name": "FastAPI Web Server",
                "cmd": [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"],
                "proc": None, "q": queue.Queue(maxsize=1000), "icon": "🌐 WEB"
            },
            "telemetry": {
                "name": "Network Telemetry",
                "cmd": [sys.executable, "scripts/network_telemetry_worker.py"],
                "proc": None, "q": queue.Queue(maxsize=1000), "icon": "📡 NET"
            },
            "assets": {
                "name": "Asset Inventory Sync",
                "cmd": ["powershell.exe", "-ExecutionPolicy", "Bypass", "-File", "scripts/Sync-ITSMAssets.ps1"],
                "proc": None, "q": queue.Queue(maxsize=1000), "icon": "💻 AST"
            },
            "printers": {
                "name": "Printer Inventory Sync",
                "cmd": ["powershell.exe", "-ExecutionPolicy", "Bypass", "-File", "scripts/Sync-ITSMPrinters.ps1"],
                "proc": None, "q": queue.Queue(maxsize=1000), "icon": "🖨️ PRN"
            }
        }
        
        self.metrics = {
            "sys_cpu": 0, "sys_ram": 0, "sys_ram_total": round(psutil.virtual_memory().total / (1024**3), 1),
            "itsm_cpu": 0, "itsm_ram": 0,
            "net_sent": 0, "net_recv": 0,
            "users": [],
            "user_count": 0
        }
        self.prev_net_io = psutil.net_io_counters()

        self.build_ui()
        
        # Start background threads
        self.running = True
        self.metric_thread = threading.Thread(target=self.poll_metrics_loop, daemon=True)
        self.metric_thread.start()
        
        # Start UI update loops
        self.update_ui_loop()
        self.update_logs_loop()

        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def build_ui(self):
        # Header
        header_frame = ctk.CTkFrame(self, height=60, corner_radius=0, fg_color="#111827")
        header_frame.pack(fill="x", side="top")
        header_frame.pack_propagate(False)

        title_lbl = ctk.CTkLabel(header_frame, text="⚡ ITSM Service Manager", font=ctk.CTkFont(size=20, weight="bold"), text_color="white")
        title_lbl.pack(side="left", padx=20)

        self.btn_start_all = ctk.CTkButton(header_frame, text="▶ Start All", fg_color="#059669", hover_color="#047857", command=self.start_all)
        self.btn_start_all.pack(side="right", padx=(0,20))
        
        self.btn_stop_all = ctk.CTkButton(header_frame, text="⏹ Stop All", fg_color="#DC2626", hover_color="#991B1B", command=self.stop_all)
        self.btn_stop_all.pack(side="right", padx=(0,10))

        # Global Metrics
        metrics_frame = ctk.CTkFrame(self, corner_radius=10, fg_color="#1F2937")
        metrics_frame.pack(fill="x", padx=20, pady=15)

        self.lbl_sys_cpu = ctk.CTkLabel(metrics_frame, text="Sys CPU: 0% | RAM: 0GB", font=ctk.CTkFont(size=18, weight="bold"))
        self.lbl_sys_cpu.pack(side="left", padx=30, pady=15)

        self.lbl_itsm_load = ctk.CTkLabel(metrics_frame, text="ITSM Load: 0% | RAM: 0MB", font=ctk.CTkFont(size=18, weight="bold"), text_color="#3B82F6")
        self.lbl_itsm_load.pack(side="left", padx=30)

        self.lbl_net = ctk.CTkLabel(metrics_frame, text="▲ 0 KB/s  ▼ 0 KB/s", font=ctk.CTkFont(size=18, weight="bold"), text_color="#10B981")
        self.lbl_net.pack(side="right", padx=30)

        # Service Cards
        cards_container = ctk.CTkFrame(self, fg_color="transparent")
        cards_container.pack(fill="x", padx=10)
        cards_container.columnconfigure((0,1,2,3), weight=1)

        self.card_ui = {}
        for idx, (key, svc) in enumerate(self.services.items()):
            card = ctk.CTkFrame(cards_container, corner_radius=10, fg_color="#111827")
            card.grid(row=0, column=idx, padx=10, sticky="nsew")

            title = ctk.CTkLabel(card, text=f"{svc['icon']}  {svc['name']}", font=ctk.CTkFont(size=14, weight="bold"))
            title.pack(anchor="w", padx=15, pady=(15, 5))

            status_lbl = ctk.CTkLabel(card, text="● Stopped", font=ctk.CTkFont(size=12, weight="bold"), text_color="#EF4444")
            status_lbl.pack(anchor="w", padx=15)
            
            stats_lbl = ctk.CTkLabel(card, text="CPU: -  |  RAM: -  |  PID: -", font=ctk.CTkFont(size=12), text_color="#9CA3AF")
            stats_lbl.pack(anchor="w", padx=15, pady=(10, 5))

            btn_frame = ctk.CTkFrame(card, fg_color="transparent")
            btn_frame.pack(fill="x", padx=15, pady=(10, 15))
            
            btn_start = ctk.CTkButton(btn_frame, text="Start", width=60, fg_color="#1F2937", hover_color="#374151", command=lambda k=key: self.start_service(k))
            btn_start.pack(side="left", padx=(0,5))
            
            btn_stop = ctk.CTkButton(btn_frame, text="Stop", width=60, fg_color="#1F2937", hover_color="#374151", command=lambda k=key: self.stop_service(k))
            btn_stop.pack(side="left", padx=(0,5))
            
            btn_restart = ctk.CTkButton(btn_frame, text="Restart", width=60, fg_color="#1F2937", hover_color="#374151", command=lambda k=key: self.restart_service(k))
            btn_restart.pack(side="left")

            self.card_ui[key] = {
                "status": status_lbl,
                "stats": stats_lbl,
                "btn_start": btn_start,
                "btn_stop": btn_stop,
                "btn_restart": btn_restart
            }

        # Bottom section: Users and Logs
        bottom_frame = ctk.CTkFrame(self, fg_color="transparent")
        bottom_frame.pack(fill="both", expand=True, padx=20, pady=(15, 20))

        # Users
        users_frame = ctk.CTkFrame(bottom_frame, width=300, corner_radius=10, fg_color="#111827")
        users_frame.pack(side="left", fill="y", padx=(0, 20))
        users_frame.pack_propagate(False)

        ctk.CTkLabel(users_frame, text="👥 CONNECTED USERS", font=ctk.CTkFont(size=12, weight="bold"), text_color="#9CA3AF").pack(anchor="w", padx=15, pady=(15, 5))
        self.lbl_user_count = ctk.CTkLabel(users_frame, text="0 Active Connections (Port 8000)", font=ctk.CTkFont(size=14, weight="bold"))
        self.lbl_user_count.pack(anchor="w", padx=15, pady=(0, 10))

        self.users_box = ctk.CTkTextbox(users_frame, fg_color="#0A0E17", font=ctk.CTkFont("Consolas", size=12))
        self.users_box.pack(fill="both", expand=True, padx=15, pady=(0, 15))
        self.users_box.configure(state="disabled")

        # Logs
        logs_frame = ctk.CTkFrame(bottom_frame, corner_radius=10, fg_color="#111827")
        logs_frame.pack(side="right", fill="both", expand=True)
        
        ctk.CTkLabel(logs_frame, text="📝 LIVE LOG OUTPUT", font=ctk.CTkFont(size=12, weight="bold"), text_color="#9CA3AF").pack(anchor="w", padx=15, pady=(15, 5))

        self.tabview = ctk.CTkTabview(logs_frame, fg_color="transparent")
        self.tabview.pack(fill="both", expand=True, padx=15, pady=(0, 15))

        self.log_boxes = {}
        for key, svc in self.services.items():
            self.tabview.add(svc["name"])
            box = ctk.CTkTextbox(self.tabview.tab(svc["name"]), fg_color="#0A0E17", font=ctk.CTkFont("Consolas", size=12))
            box.pack(fill="both", expand=True)
            self.log_boxes[key] = box

    # --- PROCESS MANAGEMENT ---
    def start_service(self, key):
        svc = self.services[key]
        if svc["proc"] is not None and svc["proc"].poll() is None:
            return # Already running
        
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        try:
            svc["proc"] = subprocess.Popen(
                svc["cmd"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True, bufsize=1, universal_newlines=True,
                cwd=os.path.abspath(os.path.join(os.path.dirname(__file__), ".")),
                env=env
            )
            svc["start_time"] = time.time()
            svc["q"].put(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] Started (PID: {svc['proc'].pid})\n")
            
            # Start background reader thread
            threading.Thread(target=self.read_output, args=(key, svc["proc"]), daemon=True).start()
        except Exception as e:
            svc["q"].put(f"[ERROR] Failed to start: {e}\n")

    def stop_service(self, key):
        svc = self.services[key]
        if svc["proc"] is not None:
            try:
                parent = psutil.Process(svc["proc"].pid)
                for child in parent.children(recursive=True):
                    child.kill()
                parent.kill()
                svc["proc"].wait(timeout=3)
            except Exception:
                pass
            svc["proc"] = None
            svc["q"].put(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] Stopped.\n")

    def restart_service(self, key):
        self.stop_service(key)
        self.start_service(key)

    def start_all(self):
        self.start_service("fastapi")
        self.services["fastapi"]["q"].put("Waiting 5s for API to boot...\n")
        # Non-blocking wait for others
        self.after(5000, lambda: [self.start_service(k) for k in ["telemetry", "assets", "printers"]])

    def stop_all(self):
        for k in self.services:
            self.stop_service(k)

    def read_output(self, key, proc):
        for line in iter(proc.stdout.readline, ''):
            if not self.running: break
            if line:
                if self.services[key]["q"].qsize() > 900:
                    self.services[key]["q"].get() # avoid infinite growth
                self.services[key]["q"].put(line)
        proc.stdout.close()

    # --- BACKGROUND POLLING ---
    def poll_metrics_loop(self):
        while self.running:
            try:
                # System Metrics
                self.metrics["sys_cpu"] = psutil.cpu_percent()
                mem = psutil.virtual_memory()
                self.metrics["sys_ram"] = round(mem.used / (1024**3), 1)

                # Network Metrics
                net_io = psutil.net_io_counters()
                self.metrics["net_sent"] = (net_io.bytes_sent - self.prev_net_io.bytes_sent) / 1024 # KB/s
                self.metrics["net_recv"] = (net_io.bytes_recv - self.prev_net_io.bytes_recv) / 1024
                self.prev_net_io = net_io

                # Per-Service Metrics
                t_cpu = 0
                t_ram = 0
                for key, svc in self.services.items():
                    if svc["proc"] and svc["proc"].poll() is None:
                        try:
                            p = psutil.Process(svc["proc"].pid)
                            cpu = p.cpu_percent() / psutil.cpu_count()
                            ram = p.memory_info().rss / (1024**2)
                            t_cpu += cpu
                            t_ram += ram
                            
                            svc["stats"] = {"cpu": round(cpu, 1), "ram": round(ram, 1), "pid": p.pid}
                        except psutil.NoSuchProcess:
                            svc["stats"] = None
                    else:
                        svc["stats"] = None
                        
                self.metrics["itsm_cpu"] = round(t_cpu, 1)
                self.metrics["itsm_ram"] = round(t_ram, 1)

                # Network connections (port 8000)
                conns = psutil.net_connections(kind='tcp')
                active_ips = {}
                for c in conns:
                    if c.laddr.port == 8000 and c.status == 'ESTABLISHED' and c.raddr:
                        ip = c.raddr.ip
                        if ip not in ('127.0.0.1', '::1'):
                            active_ips[ip] = active_ips.get(ip, 0) + 1
                
                self.metrics["users"] = active_ips
                self.metrics["user_count"] = sum(active_ips.values())

            except Exception as e:
                print(f"Metrics error: {e}")
            
            time.sleep(1) # Poll exactly every 1 second

    # --- FAST UI UPDATES ---
    def update_ui_loop(self):
        # Update labels instantly from memory dict
        self.lbl_sys_cpu.configure(text=f"Sys CPU: {self.metrics['sys_cpu']}% | RAM: {self.metrics['sys_ram']}GB / {self.metrics['sys_ram_total']}GB")
        self.lbl_itsm_load.configure(text=f"ITSM Load: {self.metrics['itsm_cpu']}% | RAM: {self.metrics['itsm_ram']}MB")
        
        sent = f"{self.metrics['net_sent']:.1f} KB/s" if self.metrics['net_sent'] < 1000 else f"{self.metrics['net_sent']/1024:.1f} MB/s"
        recv = f"{self.metrics['net_recv']:.1f} KB/s" if self.metrics['net_recv'] < 1000 else f"{self.metrics['net_recv']/1024:.1f} MB/s"
        self.lbl_net.configure(text=f"▲ {sent}  ▼ {recv}")

        # Update cards
        any_running = False
        all_running = True
        for key, svc in self.services.items():
            ui = self.card_ui[key]
            is_running = svc.get("stats") is not None
            if is_running:
                any_running = True
            else:
                all_running = False
                
            if is_running:
                ui["status"].configure(text="● Running", text_color="#10B981")
                uptime = str(datetime.timedelta(seconds=int(time.time() - svc["start_time"])))
                ui["stats"].configure(text=f"CPU: {svc['stats']['cpu']}%  |  RAM: {svc['stats']['ram']}MB  |  PID: {svc['stats']['pid']}\nUptime: {uptime}")
                ui["btn_start"].configure(state="disabled", fg_color="#111827", text_color="#4B5563")
                ui["btn_stop"].configure(state="normal", fg_color="#DC2626", text_color="white")
                ui["btn_restart"].configure(state="normal", fg_color="#1F2937", text_color="white")
            else:
                ui["status"].configure(text="● Stopped", text_color="#EF4444")
                ui["stats"].configure(text="CPU: -  |  RAM: -  |  PID: -\nUptime: -")
                ui["btn_start"].configure(state="normal", fg_color="#059669", text_color="white")
                ui["btn_stop"].configure(state="disabled", fg_color="#111827", text_color="#4B5563")
                ui["btn_restart"].configure(state="disabled", fg_color="#111827", text_color="#4B5563")

        # Global buttons state
        if all_running:
            self.btn_start_all.configure(state="disabled", fg_color="#111827", text_color="#4B5563")
        else:
            self.btn_start_all.configure(state="normal", fg_color="#059669", text_color="white")
            
        if not any_running:
            self.btn_stop_all.configure(state="disabled", fg_color="#111827", text_color="#4B5563")
        else:
            self.btn_stop_all.configure(state="normal", fg_color="#DC2626", text_color="white")

        # Update Users list
        self.lbl_user_count.configure(text=f"{self.metrics['user_count']} Active Connections (Port 8000)")
        self.users_box.configure(state="normal")
        self.users_box.delete("1.0", "end")
        for ip, count in self.metrics["users"].items():
            self.users_box.insert("end", f"{ip:<15} : {count} conns\n")
        self.users_box.configure(state="disabled")

        self.after(1000, self.update_ui_loop) # UI refreshes every 1 second

    def update_logs_loop(self):
        # Drain queues extremely fast without blocking
        for key, svc in self.services.items():
            lines = []
            try:
                for _ in range(50):
                    lines.append(svc["q"].get_nowait())
            except queue.Empty:
                pass
            
            if lines:
                box = self.log_boxes[key]
                box.insert("end", "".join(lines))
                box.see("end")
        
        self.after(100, self.update_logs_loop) # Log updates every 100ms

    def on_closing(self):
        self.running = False
        self.stop_all()
        self.destroy()
        sys.exit(0)

if __name__ == "__main__":
    app = ITSMServiceManager()
    try:
        app.mainloop()
    except KeyboardInterrupt:
        print("\nShutting down ITSM Service Manager gracefully...")
        app.on_closing()
