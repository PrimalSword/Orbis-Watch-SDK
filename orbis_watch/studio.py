from __future__ import annotations

import argparse
import asyncio
import csv
import json
import queue
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from time import perf_counter
from tkinter import filedialog, messagebox, ttk

from bleak import BleakScanner

from .lab import DANGEROUS_COMMANDS, analyze_capture, write_report
from .protocol.packet import Packet
from .protocol_tools import decode_hex, diff_captures, filter_records, load_jsonl
from .watch import Watch


class AsyncWorker:
    def __init__(self) -> None:
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self) -> None:
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def submit(self, coroutine):
        return asyncio.run_coroutine_threadsafe(coroutine, self.loop)

    def close(self) -> None:
        self.loop.call_soon_threadsafe(self.loop.stop)


class OrbisStudio(tk.Tk):
    def __init__(self, address: str = "") -> None:
        super().__init__()
        self.title("Orbis Watch Studio v0.3-dev2")
        self.geometry("1320x820")
        self.minsize(1050, 680)
        self.worker = AsyncWorker()
        self.watch: Watch | None = None
        self.events: queue.Queue[tuple[str, object]] = queue.Queue()
        self.capture_records: list[dict] = []
        self.capture_path: Path | None = None
        self.capture_file = None
        self.capture_observer = None

        self.address_var = tk.StringVar(value=address)
        self.status_var = tk.StringVar(value="Disconnected — safe mode")
        self.filter_var = tk.StringVar()
        self.command_var = tk.StringVar(value="0xF3")
        self.subcommand_var = tk.StringVar(value="0")
        self.payload_var = tk.StringVar()
        self.gatt_uuid_var = tk.StringVar()
        self.decoder_var = tk.StringVar(value="DF 00 05 D8 F3 01 00 00 00")
        self.crawl_start_var = tk.StringVar(value="0x18")
        self.crawl_end_var = tk.StringVar(value="0x1A")
        self.crawl_sub_start_var = tk.StringVar(value="0")
        self.crawl_sub_end_var = tk.StringVar(value="3")
        self.crawl_timeout_var = tk.StringVar(value="1.2")

        self._build_ui()
        self.after(100, self._poll_events)
        self.protocol("WM_DELETE_WINDOW", self._close)

    def _build_ui(self) -> None:
        toolbar = ttk.Frame(self, padding=8)
        toolbar.pack(fill="x")
        ttk.Label(toolbar, text="BLE address:").pack(side="left")
        ttk.Entry(toolbar, textvariable=self.address_var, width=25).pack(side="left", padx=6)
        for text, command in (
            ("Scan", self.scan), ("Connect", self.connect_watch), ("Disconnect", self.disconnect_watch),
            ("Device info", self.device_info), ("Battery", self.battery),
            ("Features", self.features), ("Services", self.services),
        ):
            ttk.Button(toolbar, text=text, command=command).pack(side="left", padx=2)

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        self._build_dashboard_tab()
        self._build_gatt_tab()
        self._build_protocol_tab()
        self._build_capture_tab()
        self._build_analysis_tab()
        self._build_diff_tab()
        self._build_crawler_tab()

        ttk.Label(self, textvariable=self.status_var, relief="sunken", anchor="w", padding=5).pack(fill="x")

    def _new_tab(self, title: str) -> ttk.Frame:
        frame = ttk.Frame(self.notebook, padding=8)
        self.notebook.add(frame, text=title)
        return frame

    def _build_dashboard_tab(self) -> None:
        tab = self._new_tab("Dashboard")
        left = ttk.Frame(tab)
        left.pack(side="left", fill="y", padx=(0, 8))
        right = ttk.Frame(tab)
        right.pack(side="left", fill="both", expand=True)

        ttk.Label(left, text="Device", font=("Segoe UI", 12, "bold")).pack(anchor="w")
        self.dashboard_tree = ttk.Treeview(left, columns=("value",), show="tree headings", height=18)
        self.dashboard_tree.heading("#0", text="Field")
        self.dashboard_tree.heading("value", text="Value")
        self.dashboard_tree.column("#0", width=150)
        self.dashboard_tree.column("value", width=350)
        self.dashboard_tree.pack(fill="both", expand=True, pady=6)
        ttk.Button(left, text="Refresh dashboard", command=self.refresh_dashboard).pack(fill="x")
        ttk.Button(left, text="Benchmark battery x10", command=lambda: self.benchmark(10)).pack(fill="x", pady=4)

        ttk.Label(right, text="Console", font=("Segoe UI", 12, "bold")).pack(anchor="w")
        self.console = tk.Text(right, wrap="none", font=("Consolas", 10))
        self.console.pack(fill="both", expand=True, pady=6)
        ttk.Button(right, text="Clear console", command=lambda: self.console.delete("1.0", "end")).pack(anchor="e")

    def _build_gatt_tab(self) -> None:
        tab = self._new_tab("BLE / GATT")
        controls = ttk.Frame(tab)
        controls.pack(fill="x")
        ttk.Label(controls, text="Characteristic UUID:").pack(side="left")
        ttk.Entry(controls, textvariable=self.gatt_uuid_var, width=48).pack(side="left", padx=6)
        ttk.Button(controls, text="Read", command=self.read_gatt).pack(side="left")
        ttk.Button(controls, text="Refresh services", command=self.services).pack(side="left", padx=4)

        self.service_tree = ttk.Treeview(tab, columns=("uuid", "properties", "description"), show="tree headings")
        for key, label, width in (("#0", "Type", 110), ("uuid", "UUID", 390), ("properties", "Properties", 220), ("description", "Description", 260)):
            self.service_tree.heading(key, text=label)
            self.service_tree.column(key, width=width)
        self.service_tree.pack(fill="both", expand=True, pady=8)
        self.service_tree.bind("<<TreeviewSelect>>", self._select_gatt)

        self.gatt_output = tk.Text(tab, height=8, wrap="none", font=("Consolas", 10))
        self.gatt_output.pack(fill="x")

    def _build_protocol_tab(self) -> None:
        tab = self._new_tab("Protocol")
        builder = ttk.LabelFrame(tab, text="Safe packet builder", padding=8)
        builder.pack(fill="x")
        for label, variable, width in (
            ("Command", self.command_var, 12), ("Subcommand", self.subcommand_var, 12), ("Payload hex", self.payload_var, 65),
        ):
            ttk.Label(builder, text=label).pack(side="left")
            ttk.Entry(builder, textvariable=variable, width=width).pack(side="left", padx=5)
        ttk.Button(builder, text="Build", command=self.build_packet).pack(side="left", padx=3)
        ttk.Button(builder, text="Send", command=self.send_packet).pack(side="left", padx=3)

        decoder = ttk.LabelFrame(tab, text="Packet decoder", padding=8)
        decoder.pack(fill="x", pady=8)
        ttk.Entry(decoder, textvariable=self.decoder_var).pack(side="left", fill="x", expand=True)
        ttk.Button(decoder, text="Decode", command=self.decode_packet).pack(side="left", padx=5)

        self.protocol_output = tk.Text(tab, wrap="none", font=("Consolas", 10))
        self.protocol_output.pack(fill="both", expand=True)

    def _build_capture_tab(self) -> None:
        tab = self._new_tab("Capture")
        controls = ttk.Frame(tab)
        controls.pack(fill="x")
        for text, command in (("Open", self.open_capture), ("Start live capture", self.start_capture), ("Stop", self.stop_capture), ("Save filtered CSV", self.export_filtered)):
            ttk.Button(controls, text=text, command=command).pack(side="left", padx=2)
        ttk.Label(controls, text="Filter:").pack(side="left", padx=(12, 2))
        ttk.Entry(controls, textvariable=self.filter_var, width=38).pack(side="left")
        ttk.Button(controls, text="Apply", command=self.refresh_capture_table).pack(side="left", padx=4)
        ttk.Label(controls, text="Examples: rx ack | cmd=0xF3 | len>20").pack(side="left", padx=6)

        self.capture_tree = ttk.Treeview(tab, columns=("time", "dir", "type", "cmd", "len", "hex"), show="headings")
        widths = {"time": 185, "dir": 45, "type": 75, "cmd": 65, "len": 55, "hex": 720}
        for key in ("time", "dir", "type", "cmd", "len", "hex"):
            self.capture_tree.heading(key, text=key.upper())
            self.capture_tree.column(key, width=widths[key])
        self.capture_tree.pack(fill="both", expand=True, pady=8)
        self.capture_tree.bind("<<TreeviewSelect>>", self._capture_selected)
        self.capture_detail = tk.Text(tab, height=9, wrap="none", font=("Consolas", 10))
        self.capture_detail.pack(fill="x")

    def _build_analysis_tab(self) -> None:
        tab = self._new_tab("Analyzer")
        controls = ttk.Frame(tab)
        controls.pack(fill="x")
        ttk.Button(controls, text="Analyze capture", command=self.open_capture_analysis).pack(side="left")
        ttk.Button(controls, text="Generate Markdown report", command=self.generate_report).pack(side="left", padx=4)
        self.analysis = tk.Text(tab, wrap="word", font=("Consolas", 10))
        self.analysis.pack(fill="both", expand=True, pady=8)

    def _build_diff_tab(self) -> None:
        tab = self._new_tab("Capture diff")
        ttk.Label(tab, text="Compare two JSONL captures to find new/removed frames and command-count deltas.").pack(anchor="w")
        ttk.Button(tab, text="Select captures and compare", command=self.compare_captures).pack(anchor="w", pady=6)
        self.diff_output = tk.Text(tab, wrap="none", font=("Consolas", 10))
        self.diff_output.pack(fill="both", expand=True)

    def _build_crawler_tab(self) -> None:
        tab = self._new_tab("Safe crawler")
        controls = ttk.Frame(tab)
        controls.pack(fill="x")
        fields = (
            ("CMD start", self.crawl_start_var), ("CMD end", self.crawl_end_var),
            ("SUB start", self.crawl_sub_start_var), ("SUB end", self.crawl_sub_end_var),
            ("Timeout", self.crawl_timeout_var),
        )
        for label, variable in fields:
            ttk.Label(controls, text=label).pack(side="left")
            ttk.Entry(controls, textvariable=variable, width=9).pack(side="left", padx=4)
        ttk.Button(controls, text="Run safe crawl", command=self.run_crawler).pack(side="left", padx=8)
        ttk.Label(tab, text="OTA (0x01), settings (0x02), and watchface (0x0F) are always skipped here.").pack(anchor="w", pady=6)
        self.crawler_tree = ttk.Treeview(tab, columns=("cmd", "sub", "status", "ms", "response"), show="headings")
        for key, label, width in (("cmd", "CMD", 70), ("sub", "SUB", 70), ("status", "Status", 100), ("ms", "Latency", 100), ("response", "Response", 780)):
            self.crawler_tree.heading(key, text=label)
            self.crawler_tree.column(key, width=width)
        self.crawler_tree.pack(fill="both", expand=True)

    def _log(self, text: str) -> None:
        self.console.insert("end", text.rstrip() + "\n")
        self.console.see("end")

    def _submit(self, coroutine, label: str, event_kind: str = "result") -> None:
        self.status_var.set(label)
        future = self.worker.submit(coroutine)
        def done(result):
            try:
                self.events.put((event_kind, result.result()))
            except Exception as exc:
                self.events.put(("error", f"{type(exc).__name__}: {exc}"))
        future.add_done_callback(done)

    def _poll_events(self) -> None:
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == "error":
                    self.status_var.set("Error")
                    self._log(f"ERROR: {value}")
                    messagebox.showerror("Operation failed", str(value))
                elif kind == "services":
                    self._load_services(value)
                elif kind == "dashboard":
                    self._load_dashboard(value)
                elif kind == "crawl":
                    self._load_crawl(value)
                elif kind == "capture_event":
                    self.capture_records.append(value)
                    self.refresh_capture_table()
                elif kind == "scan":
                    self._show_scan(value)
                else:
                    self.status_var.set("Ready — safe mode")
                    if value is not None:
                        self._log(str(value))
        except queue.Empty:
            pass
        self.after(100, self._poll_events)

    async def _ensure_watch(self) -> Watch:
        address = self.address_var.get().strip()
        if not address:
            raise ValueError("Enter the BLE address")
        if self.watch is None or self.watch.address != address:
            if self.watch is not None:
                await self.watch.disconnect()
            self.watch = Watch(address)
        if not self.watch.is_connected:
            await self.watch.connect()
        return self.watch

    def scan(self) -> None:
        async def action():
            devices = await BleakScanner.discover(timeout=5, return_adv=True)
            rows = []
            for _address, (device, adv) in devices.items():
                rows.append((device.address, device.name or "Unknown", adv.rssi))
            return sorted(rows, key=lambda row: row[2], reverse=True)
        self._submit(action(), "Scanning BLE devices...", "scan")

    def _show_scan(self, rows) -> None:
        window = tk.Toplevel(self)
        window.title("Nearby BLE devices")
        tree = ttk.Treeview(window, columns=("address", "name", "rssi"), show="headings")
        for key in ("address", "name", "rssi"):
            tree.heading(key, text=key.upper())
            tree.column(key, width=250 if key != "rssi" else 80)
        for row in rows:
            tree.insert("", "end", values=row)
        tree.pack(fill="both", expand=True, padx=8, pady=8)
        def choose():
            selected = tree.selection()
            if selected:
                self.address_var.set(tree.item(selected[0], "values")[0])
                window.destroy()
        ttk.Button(window, text="Use selected", command=choose).pack(pady=(0, 8))
        window.geometry("650x420")
        self.status_var.set("Ready — safe mode")

    def connect_watch(self) -> None:
        async def action():
            watch = await self._ensure_watch()
            return f"Connected: {watch.address}"
        self._submit(action(), "Connecting...")

    def disconnect_watch(self) -> None:
        async def action():
            if self.watch is not None:
                await self.watch.disconnect()
            return "Disconnected"
        self._submit(action(), "Disconnecting...")

    def device_info(self) -> None:
        self._submit(self._device_info(), "Reading device info...")

    async def _device_info(self):
        return await (await self._ensure_watch()).get_device_info()

    def battery(self) -> None:
        async def action():
            return f"Battery: {await (await self._ensure_watch()).get_battery_level()}%"
        self._submit(action(), "Reading battery...")

    def features(self) -> None:
        async def action():
            features = await (await self._ensure_watch()).get_features()
            return f"Feature ACK: {features.acknowledged}\nBitmap: {features.hex}\nBits: {features.enabled_bits}"
        self._submit(action(), "Reading features...")

    def refresh_dashboard(self) -> None:
        async def action():
            watch = await self._ensure_watch()
            info = await watch.get_device_info()
            battery = await watch.get_battery_level()
            features = await watch.get_features()
            return {
                "Address": watch.address, "Connected": watch.is_connected,
                "Firmware": info.firmware, "Project": info.project, "Model": info.model,
                "Screen": f"{info.screen_width}x{info.screen_height}", "Battery": f"{battery}%",
                "Feature ACK": features.acknowledged, "Feature bits": len(features.enabled_bits),
                "Feature bitmap": features.hex,
            }
        self._submit(action(), "Refreshing dashboard...", "dashboard")

    def _load_dashboard(self, data: dict) -> None:
        self.dashboard_tree.delete(*self.dashboard_tree.get_children())
        for key, value in data.items():
            self.dashboard_tree.insert("", "end", text=key, values=(value,))
        self.status_var.set("Ready — safe mode")

    def benchmark(self, count: int) -> None:
        async def action():
            watch = await self._ensure_watch()
            samples = []
            for _ in range(count):
                start = perf_counter()
                await watch.get_battery_level()
                samples.append((perf_counter() - start) * 1000)
            return f"Battery benchmark ({count}): min={min(samples):.1f} avg={sum(samples)/len(samples):.1f} max={max(samples):.1f} ms"
        self._submit(action(), "Benchmarking...")

    def services(self) -> None:
        async def action():
            watch = await self._ensure_watch()
            rows = []
            for service in watch._client._client.services:
                rows.append(("SERVICE", str(service.uuid), "", service.description or ""))
                for char in service.characteristics:
                    rows.append(("CHAR", str(char.uuid), ",".join(char.properties), char.description or ""))
            return rows
        self._submit(action(), "Reading services...", "services")

    def _load_services(self, rows) -> None:
        self.service_tree.delete(*self.service_tree.get_children())
        parent = ""
        for row_type, uuid, props, description in rows:
            if row_type == "SERVICE":
                parent = self.service_tree.insert("", "end", text="Service", values=(uuid, props, description), open=True)
            else:
                self.service_tree.insert(parent, "end", text="Characteristic", values=(uuid, props, description))
        self.status_var.set(f"Loaded {len(rows)} GATT entries")

    def _select_gatt(self, _event=None) -> None:
        selected = self.service_tree.selection()
        if selected:
            values = self.service_tree.item(selected[0], "values")
            if values and self.service_tree.item(selected[0], "text") == "Characteristic":
                self.gatt_uuid_var.set(values[0])

    def read_gatt(self) -> None:
        uuid = self.gatt_uuid_var.get().strip()
        if not uuid:
            messagebox.showwarning("UUID required", "Select or enter a characteristic UUID")
            return
        async def action():
            raw = await (await self._ensure_watch())._client.read_gatt(uuid)
            return raw
        self.status_var.set("Reading GATT...")
        future = self.worker.submit(action())
        def done(result):
            try:
                raw = result.result()
                self.events.put(("result", f"GATT {uuid}: {raw.hex(' ').upper()} | {repr(raw)}"))
                self.after(0, lambda: (self.gatt_output.delete("1.0", "end"), self.gatt_output.insert("end", f"HEX: {raw.hex(' ').upper()}\nBYTES: {raw!r}")))
            except Exception as exc:
                self.events.put(("error", f"{type(exc).__name__}: {exc}"))
        future.add_done_callback(done)

    def _packet_values(self):
        command = int(self.command_var.get(), 0)
        subcommand = int(self.subcommand_var.get(), 0)
        payload = bytes.fromhex(self.payload_var.get().replace(" ", "")) if self.payload_var.get().strip() else b""
        if command in DANGEROUS_COMMANDS:
            raise PermissionError(f"Command 0x{command:02X} is blocked in Studio safe mode")
        return command, subcommand, payload

    def build_packet(self) -> None:
        try:
            command, subcommand, payload = self._packet_values()
            raw = Packet.build(command, subcommand=subcommand, payload=payload).to_bytes()
            self.decoder_var.set(raw.hex(" ").upper())
            self.protocol_output.insert("end", f"BUILT {raw.hex(' ').upper()}\n")
        except Exception as exc:
            messagebox.showerror("Build failed", str(exc))

    def send_packet(self) -> None:
        try:
            command, subcommand, payload = self._packet_values()
        except Exception as exc:
            messagebox.showerror("Blocked/invalid", str(exc))
            return
        async def action():
            watch = await self._ensure_watch()
            response = await watch._client.request(Packet.build(command, subcommand=subcommand, payload=payload), timeout=3.0, accept_ack=True, retry_on_timeout=False)
            return f"0x{command:02X}/0x{subcommand:02X} {'ACK' if response.is_ack else 'DATA'}\n{response.to_bytes().hex(' ').upper()}"
        self._submit(action(), f"Sending 0x{command:02X}...")

    def decode_packet(self) -> None:
        try:
            decoded = decode_hex(self.decoder_var.get())
            self.protocol_output.insert("end", json.dumps(decoded.to_dict(), indent=2, ensure_ascii=False) + "\n\n")
            self.protocol_output.see("end")
        except Exception as exc:
            messagebox.showerror("Decode failed", str(exc))

    def open_capture(self) -> None:
        filename = filedialog.askopenfilename(filetypes=[("JSONL captures", "*.jsonl"), ("All files", "*.*")])
        if not filename:
            return
        self.capture_path = Path(filename)
        self.capture_records = load_jsonl(self.capture_path)
        self.refresh_capture_table()
        self.status_var.set(f"Loaded {len(self.capture_records)} capture records")

    def start_capture(self) -> None:
        if self.capture_file is not None:
            messagebox.showinfo("Capture", "Capture is already active")
            return
        filename = filedialog.asksaveasfilename(defaultextension=".jsonl", filetypes=[("JSONL", "*.jsonl")])
        if not filename:
            return
        path = Path(filename)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.capture_file = path.open("a", encoding="utf-8")
        self.capture_path = path
        self.capture_records = []

        def observer(event):
            record = {"timestamp": event.timestamp, "direction": event.direction, "hex": event.data.hex().upper(), "command": event.packet.command if event.packet else None}
            if self.capture_file is not None:
                self.capture_file.write(json.dumps(record) + "\n")
                self.capture_file.flush()
            self.events.put(("capture_event", record))
        self.capture_observer = observer

        async def action():
            watch = await self._ensure_watch()
            watch.add_traffic_observer(observer)
            return f"Capture started: {path.resolve()}"
        self._submit(action(), "Starting capture...")

    def stop_capture(self) -> None:
        if self.capture_observer is not None and self.watch is not None:
            self.watch.remove_traffic_observer(self.capture_observer)
        self.capture_observer = None
        if self.capture_file is not None:
            self.capture_file.close()
        self.capture_file = None
        self.status_var.set("Capture stopped")

    def refresh_capture_table(self) -> None:
        self.capture_tree.delete(*self.capture_tree.get_children())
        try:
            records = filter_records(self.capture_records, self.filter_var.get())
        except Exception as exc:
            messagebox.showerror("Invalid filter", str(exc))
            return
        for index, record in enumerate(records):
            raw = bytes.fromhex(record.get("hex", "")) if record.get("hex") else b""
            decoded = decode_hex(record.get("hex", "")) if raw else None
            self.capture_tree.insert("", "end", iid=str(index), values=(
                record.get("timestamp", ""), record.get("direction", ""), decoded.frame_type if decoded else "RAW",
                f"0x{decoded.command:02X}" if decoded and decoded.command is not None else "", len(raw), record.get("hex", ""),
            ), tags=(str(record.get("_line", index)),))

    def _capture_selected(self, _event=None) -> None:
        selected = self.capture_tree.selection()
        if not selected:
            return
        values = self.capture_tree.item(selected[0], "values")
        raw_hex = values[5]
        try:
            decoded = decode_hex(raw_hex)
            self.capture_detail.delete("1.0", "end")
            self.capture_detail.insert("end", json.dumps(decoded.to_dict(), indent=2, ensure_ascii=False))
        except Exception as exc:
            self.capture_detail.delete("1.0", "end")
            self.capture_detail.insert("end", str(exc))

    def export_filtered(self) -> None:
        if not self.capture_records:
            messagebox.showwarning("No capture", "Open or record a capture first")
            return
        output = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if not output:
            return
        records = filter_records(self.capture_records, self.filter_var.get())
        with Path(output).open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["timestamp", "direction", "type", "command", "subcommand", "length", "hex", "payload_ascii"])
            for record in records:
                decoded = decode_hex(record.get("hex", ""))
                writer.writerow([record.get("timestamp", ""), record.get("direction", ""), decoded.frame_type,
                                 decoded.command, decoded.subcommand, decoded.length, decoded.raw_hex, decoded.payload_ascii])
        messagebox.showinfo("Export", f"Saved to {output}")

    def open_capture_analysis(self) -> None:
        filename = filedialog.askopenfilename(filetypes=[("JSONL captures", "*.jsonl")])
        if not filename:
            return
        result = analyze_capture(Path(filename))
        self.analysis.delete("1.0", "end")
        self.analysis.insert("end", json.dumps(result, indent=2, ensure_ascii=False))

    def generate_report(self) -> None:
        source = filedialog.askopenfilename(filetypes=[("JSONL captures", "*.jsonl")])
        if not source:
            return
        output = filedialog.asksaveasfilename(defaultextension=".md", filetypes=[("Markdown", "*.md")])
        if not output:
            return
        write_report(analyze_capture(Path(source)), Path(output))
        messagebox.showinfo("Report", f"Saved to {output}")

    def compare_captures(self) -> None:
        left = filedialog.askopenfilename(title="Select baseline capture", filetypes=[("JSONL", "*.jsonl")])
        if not left:
            return
        right = filedialog.askopenfilename(title="Select comparison capture", filetypes=[("JSONL", "*.jsonl")])
        if not right:
            return
        result = diff_captures(Path(left), Path(right))
        self.diff_output.delete("1.0", "end")
        self.diff_output.insert("end", json.dumps(result, indent=2, ensure_ascii=False))

    def run_crawler(self) -> None:
        try:
            start = int(self.crawl_start_var.get(), 0)
            end = int(self.crawl_end_var.get(), 0)
            sub_start = int(self.crawl_sub_start_var.get(), 0)
            sub_end = int(self.crawl_sub_end_var.get(), 0)
            timeout = float(self.crawl_timeout_var.get())
            if not (0 <= start <= end <= 0xFF and 0 <= sub_start <= sub_end <= 0xFF):
                raise ValueError("Ranges must stay between 0 and 255")
            if (end - start + 1) * (sub_end - sub_start + 1) > 256:
                raise ValueError("Studio limits one crawl to 256 probes")
        except Exception as exc:
            messagebox.showerror("Invalid crawler settings", str(exc))
            return

        async def action():
            watch = await self._ensure_watch()
            rows = []
            for command in range(start, end + 1):
                if command in DANGEROUS_COMMANDS:
                    rows.append((command, None, "SKIPPED", 0.0, "Safety policy"))
                    continue
                for subcommand in range(sub_start, sub_end + 1):
                    started = perf_counter()
                    try:
                        response = await watch._client.request(Packet.build(command, subcommand=subcommand), timeout=timeout, accept_ack=True, retry_on_timeout=False)
                        rows.append((command, subcommand, "ACK" if response.is_ack else "DATA", (perf_counter()-started)*1000, response.to_bytes().hex(" ").upper()))
                    except asyncio.TimeoutError:
                        rows.append((command, subcommand, "TIMEOUT", (perf_counter()-started)*1000, ""))
                    except Exception as exc:
                        rows.append((command, subcommand, "ERROR", (perf_counter()-started)*1000, f"{type(exc).__name__}: {exc}"))
            return rows
        self._submit(action(), "Running safe crawler...", "crawl")

    def _load_crawl(self, rows) -> None:
        self.crawler_tree.delete(*self.crawler_tree.get_children())
        for command, subcommand, status, elapsed, response in rows:
            self.crawler_tree.insert("", "end", values=(f"0x{command:02X}", "" if subcommand is None else f"0x{subcommand:02X}", status, f"{elapsed:.1f} ms", response))
        self.status_var.set(f"Crawler complete: {len(rows)} rows")

    def _close(self) -> None:
        self.stop_capture()
        async def shutdown():
            if self.watch is not None:
                await self.watch.disconnect()
        try:
            self.worker.submit(shutdown()).result(timeout=3)
        except Exception:
            pass
        self.worker.close()
        self.destroy()


def main() -> None:
    parser = argparse.ArgumentParser(description="Orbis Watch Studio")
    parser.add_argument("address", nargs="?", default="")
    args = parser.parse_args()
    OrbisStudio(args.address).mainloop()


if __name__ == "__main__":
    main()
