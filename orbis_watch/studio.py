from __future__ import annotations

import argparse
import asyncio
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path

from .lab import analyze_capture, write_report
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
        self.title("Orbis Watch Studio v0.3-dev")
        self.geometry("1100x720")
        self.minsize(900, 600)
        self.worker = AsyncWorker()
        self.watch: Watch | None = None
        self.events: queue.Queue[tuple[str, object]] = queue.Queue()

        self.address_var = tk.StringVar(value=address)
        self.status_var = tk.StringVar(value="Disconnected — safe mode")
        self._build_ui()
        self.after(100, self._poll_events)
        self.protocol("WM_DELETE_WINDOW", self._close)

    def _build_ui(self) -> None:
        toolbar = ttk.Frame(self, padding=8)
        toolbar.pack(fill="x")
        ttk.Label(toolbar, text="BLE address:").pack(side="left")
        ttk.Entry(toolbar, textvariable=self.address_var, width=28).pack(side="left", padx=6)
        ttk.Button(toolbar, text="Connect", command=self.connect_watch).pack(side="left")
        ttk.Button(toolbar, text="Disconnect", command=self.disconnect_watch).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Device info", command=self.device_info).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Battery", command=self.battery).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Features", command=self.features).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Services", command=self.services).pack(side="left", padx=4)

        paned = ttk.Panedwindow(self, orient="horizontal")
        paned.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        left = ttk.Frame(paned)
        right = ttk.Frame(paned)
        paned.add(left, weight=1)
        paned.add(right, weight=3)

        ttk.Label(left, text="Research tools", font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(0, 6))
        ttk.Button(left, text="Open capture", command=self.open_capture).pack(fill="x", pady=2)
        ttk.Button(left, text="Generate report", command=self.generate_report).pack(fill="x", pady=2)
        ttk.Separator(left).pack(fill="x", pady=10)
        ttk.Label(left, text="Safe packet requests").pack(anchor="w")
        self.command_var = tk.StringVar(value="0xF3")
        ttk.Entry(left, textvariable=self.command_var).pack(fill="x", pady=4)
        ttk.Button(left, text="Send packet", command=self.send_packet).pack(fill="x")
        ttk.Label(left, text="Only read-only command IDs are accepted.\nMutating commands remain blocked.", wraplength=220).pack(anchor="w", pady=8)

        notebook = ttk.Notebook(right)
        notebook.pack(fill="both", expand=True)

        console_tab = ttk.Frame(notebook)
        services_tab = ttk.Frame(notebook)
        analysis_tab = ttk.Frame(notebook)
        notebook.add(console_tab, text="Console")
        notebook.add(services_tab, text="GATT")
        notebook.add(analysis_tab, text="Capture analysis")

        self.console = tk.Text(console_tab, wrap="none", font=("Consolas", 10))
        self.console.pack(fill="both", expand=True)
        self.service_tree = ttk.Treeview(services_tab, columns=("uuid", "properties"), show="tree headings")
        self.service_tree.heading("#0", text="Type")
        self.service_tree.heading("uuid", text="UUID")
        self.service_tree.heading("properties", text="Properties")
        self.service_tree.column("#0", width=130)
        self.service_tree.column("uuid", width=430)
        self.service_tree.pack(fill="both", expand=True)
        self.analysis = tk.Text(analysis_tab, wrap="word", font=("Consolas", 10))
        self.analysis.pack(fill="both", expand=True)

        status = ttk.Label(self, textvariable=self.status_var, relief="sunken", anchor="w", padding=5)
        status.pack(fill="x")

    def _log(self, text: str) -> None:
        self.console.insert("end", text.rstrip() + "\n")
        self.console.see("end")

    def _submit(self, coroutine, label: str) -> None:
        self.status_var.set(label)
        future = self.worker.submit(coroutine)

        def done(result):
            try:
                value = result.result()
                self.events.put(("result", value))
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
                elif kind == "result":
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
        async def action():
            return await (await self._ensure_watch()).get_device_info()
        self._submit(action(), "Reading device info...")

    def battery(self) -> None:
        async def action():
            return f"Battery: {await (await self._ensure_watch()).get_battery_level()}%"
        self._submit(action(), "Reading battery...")

    def features(self) -> None:
        async def action():
            features = await (await self._ensure_watch()).get_features()
            return f"Feature ACK: {features.acknowledged}\nBitmap: {features.hex}\nBits: {features.enabled_bits}"
        self._submit(action(), "Reading features...")

    def services(self) -> None:
        async def action():
            watch = await self._ensure_watch()
            rows = []
            for service in watch._client._client.services:
                rows.append(("SERVICE", str(service.uuid), ""))
                for char in service.characteristics:
                    rows.append(("CHAR", str(char.uuid), ",".join(char.properties)))
            self.events.put(("services", rows))
            return f"Loaded {len(rows)} GATT entries"

        future = self.worker.submit(action())
        def done(result):
            try:
                value = result.result()
                self.events.put(("result", value))
            except Exception as exc:
                self.events.put(("error", f"{type(exc).__name__}: {exc}"))
        future.add_done_callback(done)
        self.status_var.set("Reading services...")

    def _poll_events(self) -> None:
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == "services":
                    self.service_tree.delete(*self.service_tree.get_children())
                    parent = ""
                    for row_type, uuid, props in value:
                        if row_type == "SERVICE":
                            parent = self.service_tree.insert("", "end", text="Service", values=(uuid, props), open=True)
                        else:
                            self.service_tree.insert(parent, "end", text="Characteristic", values=(uuid, props))
                elif kind == "error":
                    self.status_var.set("Error")
                    self._log(f"ERROR: {value}")
                elif kind == "result":
                    self.status_var.set("Ready — safe mode")
                    if value is not None:
                        self._log(str(value))
        except queue.Empty:
            pass
        self.after(100, self._poll_events)

    def send_packet(self) -> None:
        try:
            command = int(self.command_var.get(), 0)
        except ValueError:
            messagebox.showerror("Invalid command", "Use a value such as 0xF3")
            return
        if command in {0x01, 0x02, 0x0F}:
            messagebox.showwarning("Blocked", "This command is mutating and is blocked in Studio safe mode.")
            return
        async def action():
            result = await (await self._ensure_watch()).probe_command(command)
            return f"0x{command:02X} {result.status} {result.elapsed_ms:.1f} ms\n{result.response.hex(' ').upper()}"
        self._submit(action(), f"Sending 0x{command:02X}...")

    def open_capture(self) -> None:
        filename = filedialog.askopenfilename(filetypes=[("JSONL captures", "*.jsonl"), ("All files", "*.*")])
        if not filename:
            return
        try:
            result = analyze_capture(Path(filename))
            import json
            self.analysis.delete("1.0", "end")
            self.analysis.insert("end", json.dumps(result, indent=2, ensure_ascii=False))
        except Exception as exc:
            messagebox.showerror("Analysis failed", str(exc))

    def generate_report(self) -> None:
        source = filedialog.askopenfilename(filetypes=[("JSONL captures", "*.jsonl")])
        if not source:
            return
        output = filedialog.asksaveasfilename(defaultextension=".md", filetypes=[("Markdown", "*.md")])
        if not output:
            return
        try:
            write_report(analyze_capture(Path(source)), Path(output))
            messagebox.showinfo("Report", f"Saved to {output}")
        except Exception as exc:
            messagebox.showerror("Report failed", str(exc))

    def _close(self) -> None:
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
