from __future__ import annotations

import asyncio
import json
import queue
import threading
import tkinter as tk
from dataclasses import asdict
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from ble_link import G28BootLink, ScannedDevice
from ota_protocol import (
    COMMAND_NAMES,
    READ_ONLY_COMMANDS,
    OtaIdentity,
    OtaResponse,
    TrafficRecord,
    build_request,
    format_hex,
    parse_hex,
    parse_identity,
    validate_request,
)

APP_TITLE = "Orbis G28 Recovery Studio v0.1"


class AsyncWorker:
    def __init__(self) -> None:
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self._run, name="orbis-async", daemon=True)
        self.thread.start()

    def _run(self) -> None:
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def submit(self, coroutine):
        return asyncio.run_coroutine_threadsafe(coroutine, self.loop)

    def stop(self) -> None:
        self.loop.call_soon_threadsafe(self.loop.stop)


class RecoveryStudio(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1060x760")
        self.minsize(900, 650)

        self.worker = AsyncWorker()
        self.ui_queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self.traffic: list[TrafficRecord] = []
        self.devices: list[ScannedDevice] = []
        self.protocol_negotiated = False
        self.identity: OtaIdentity | None = None
        self.link = G28BootLink(self._thread_log, self._thread_traffic, self._thread_response)

        self._build_ui()
        self.after(80, self._drain_ui_queue)
        self.protocol("WM_DELETE_WINDOW", self._close)
        self._log("Aplicativo iniciado. Nenhum comando de gravação é transmitido nesta versão.")

    def _build_ui(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("vista")
        except tk.TclError:
            pass

        top = ttk.Frame(self, padding=10)
        top.pack(fill="x")
        ttk.Label(top, text=APP_TITLE, font=("Segoe UI", 16, "bold")).pack(side="left")
        self.status_var = tk.StringVar(value="Desconectado")
        ttk.Label(top, textvariable=self.status_var).pack(side="right")

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        diagnostic = ttk.Frame(notebook, padding=10)
        simulator = ttk.Frame(notebook, padding=10)
        recovery = ttk.Frame(notebook, padding=10)
        notebook.add(diagnostic, text="Diagnóstico BLE")
        notebook.add(simulator, text="Simulador de frames")
        notebook.add(recovery, text="Recuperação")

        self._build_diagnostic_tab(diagnostic)
        self._build_simulator_tab(simulator)
        self._build_recovery_tab(recovery)

    def _build_diagnostic_tab(self, parent: ttk.Frame) -> None:
        connection = ttk.LabelFrame(parent, text="Conexão ao bootloader OTA", padding=10)
        connection.pack(fill="x")

        row = ttk.Frame(connection)
        row.pack(fill="x")
        self.scan_button = ttk.Button(row, text="Escanear G28/OTA", command=self._scan)
        self.scan_button.pack(side="left")
        self.device_combo = ttk.Combobox(row, state="readonly", width=62)
        self.device_combo.pack(side="left", fill="x", expand=True, padx=8)
        ttk.Button(row, text="Conectar", command=self._connect).pack(side="left")
        ttk.Button(row, text="Desconectar", command=self._disconnect).pack(side="left", padx=(8, 0))

        manual = ttk.Frame(connection)
        manual.pack(fill="x", pady=(8, 0))
        ttk.Label(manual, text="Endereço manual:").pack(side="left")
        self.manual_address = ttk.Entry(manual)
        self.manual_address.insert(0, "41:42:99:10:58:02")
        self.manual_address.pack(side="left", fill="x", expand=True, padx=8)

        probes = ttk.LabelFrame(parent, text="Consultas seguras", padding=10)
        probes.pack(fill="x", pady=(10, 0))
        self.handshake_button = ttk.Button(probes, text="1. Negociar protocolo D5/0F", command=self._handshake)
        self.handshake_button.pack(side="left")
        self.identity_button = ttk.Button(probes, text="2. Ler identidade D5/01", command=self._query_identity)
        self.identity_button.pack(side="left", padx=8)
        ttk.Button(probes, text="Salvar sessão JSONL", command=self._save_session).pack(side="right")

        identity_box = ttk.LabelFrame(parent, text="Identidade do bootloader", padding=10)
        identity_box.pack(fill="x", pady=(10, 0))
        self.protocol_var = tk.StringVar(value="Protocolo: ainda não negociado")
        self.identity_var = tk.StringVar(value="Identidade: ainda não consultada")
        self.transport_var = tk.StringVar(value="Transporte: não detectado")
        ttk.Label(identity_box, textvariable=self.transport_var).pack(anchor="w")
        ttk.Label(identity_box, textvariable=self.protocol_var).pack(anchor="w")
        ttk.Label(identity_box, textvariable=self.identity_var).pack(anchor="w")

        log_box = ttk.LabelFrame(parent, text="Tráfego e eventos", padding=6)
        log_box.pack(fill="both", expand=True, pady=(10, 0))
        self.log_text = tk.Text(log_box, wrap="none", font=("Consolas", 10), state="disabled")
        yscroll = ttk.Scrollbar(log_box, orient="vertical", command=self.log_text.yview)
        xscroll = ttk.Scrollbar(log_box, orient="horizontal", command=self.log_text.xview)
        self.log_text.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        self.log_text.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")
        log_box.rowconfigure(0, weight=1)
        log_box.columnconfigure(0, weight=1)

    def _build_simulator_tab(self, parent: ttk.Frame) -> None:
        info = ttk.Label(
            parent,
            text=(
                "Esta aba monta e valida quadros localmente. Comandos de tabela, dados, checksum total e "
                "finalização jamais são transmitidos nesta versão."
            ),
            wraplength=900,
        )
        info.pack(anchor="w")

        form = ttk.LabelFrame(parent, text="Construtor HryFine 5610 D5", padding=10)
        form.pack(fill="x", pady=(10, 0))

        self.command_var = tk.StringVar(value="0F")
        self.block_var = tk.StringVar(value="0")
        self.fragment_var = tk.StringVar(value="0")
        self.payload_var = tk.StringVar(value="10 00")

        labels = (("Comando hexadecimal", self.command_var), ("Bloco", self.block_var), ("Fragmento", self.fragment_var))
        for column, (label, variable) in enumerate(labels):
            ttk.Label(form, text=label).grid(row=0, column=column, sticky="w", padx=(0, 8))
            ttk.Entry(form, textvariable=variable, width=18).grid(row=1, column=column, sticky="ew", padx=(0, 8))
        ttk.Label(form, text="Payload hexadecimal").grid(row=2, column=0, columnspan=3, sticky="w", pady=(8, 0))
        ttk.Entry(form, textvariable=self.payload_var).grid(row=3, column=0, columnspan=3, sticky="ew")
        ttk.Button(form, text="Montar quadro", command=self._simulate).grid(row=4, column=0, pady=(10, 0), sticky="w")
        for column in range(3):
            form.columnconfigure(column, weight=1)

        self.simulation_text = tk.Text(parent, height=14, wrap="word", font=("Consolas", 10), state="disabled")
        self.simulation_text.pack(fill="both", expand=True, pady=(10, 0))

    def _build_recovery_tab(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text="Recuperação de firmware", font=("Segoe UI", 14, "bold")).pack(anchor="w")
        ttk.Label(
            parent,
            text=(
                "O transporte BLE já está implementado, mas a gravação permanece bloqueada até existir um pacote "
                "com manifesto verificável: part_id, endereço, tamanho, arquivo, checksum e identidade compatível. "
                "Isso impede novas escritas em endereços presumidos."
            ),
            wraplength=900,
        ).pack(anchor="w", pady=(8, 0))

        validator = ttk.LabelFrame(parent, text="Validador de manifesto — somente leitura", padding=10)
        validator.pack(fill="x", pady=(16, 0))
        ttk.Button(validator, text="Abrir manifesto JSON", command=self._validate_manifest).pack(side="left")
        self.manifest_var = tk.StringVar(value="Nenhum manifesto carregado.")
        ttk.Label(validator, textvariable=self.manifest_var, wraplength=700).pack(side="left", padx=10)

        blocked = ttk.LabelFrame(parent, text="Transmissão", padding=10)
        blocked.pack(fill="x", pady=(16, 0))
        disabled = ttk.Button(blocked, text="Iniciar recuperação — bloqueado", state="disabled")
        disabled.pack(side="left")
        ttk.Label(
            blocked,
            text="Será liberado somente depois que um pacote real passar pela validação offline e por testes automatizados.",
            wraplength=700,
        ).pack(side="left", padx=10)

    def _scan(self) -> None:
        self.scan_button.configure(state="disabled")
        self.status_var.set("Escaneando...")
        future = self.worker.submit(self.link.scan())
        future.add_done_callback(lambda item: self.ui_queue.put(("scan_done", item)))

    def _connect(self) -> None:
        address = ""
        selected = self.device_combo.current()
        if 0 <= selected < len(self.devices):
            address = self.devices[selected].address
        if not address:
            address = self.manual_address.get().strip()
        if not address:
            messagebox.showwarning(APP_TITLE, "Informe ou selecione um endereço BLE.")
            return
        self.status_var.set("Conectando...")
        future = self.worker.submit(self.link.connect(address))
        future.add_done_callback(lambda item: self.ui_queue.put(("connect_done", item)))

    def _disconnect(self) -> None:
        future = self.worker.submit(self.link.disconnect())
        future.add_done_callback(lambda item: self.ui_queue.put(("disconnect_done", item)))

    def _handshake(self) -> None:
        frame = build_request(0x0F, protocol_version=1, payload=b"\x10\x00")
        future = self.worker.submit(self.link.send_read_only(frame, "D5/0x0F protocol handshake"))
        future.add_done_callback(lambda item: self.ui_queue.put(("command_done", item)))

    def _query_identity(self) -> None:
        if not self.protocol_negotiated:
            messagebox.showwarning(APP_TITLE, "Execute primeiro a negociação D5/0x0F e aguarde a confirmação V1.1.")
            return
        frame = build_request(0x01, protocol_version=1)
        future = self.worker.submit(self.link.send_read_only(frame, "D5/0x01 OTA identity"))
        future.add_done_callback(lambda item: self.ui_queue.put(("command_done", item)))

    def _simulate(self) -> None:
        try:
            command = int(self.command_var.get().strip(), 16)
            block = int(self.block_var.get().strip(), 10)
            fragment = int(self.fragment_var.get().strip(), 10)
            payload = parse_hex(self.payload_var.get())
            frame = build_request(command, protocol_version=1, block=block, fragment=fragment, payload=payload)
            classification = "somente leitura" if command in READ_ONLY_COMMANDS else "classe de escrita/sessão"
            command_name = COMMAND_NAMES.get(command, "desconhecido")
            transmission = "poderia ser transmitido pela área segura" if command in READ_ONLY_COMMANDS else "TRANSMISSÃO BLOQUEADA"
            text = (
                f"Comando: 0x{command:02X} — {command_name}\n"
                f"Classificação: {classification}\n"
                f"Ação: {transmission}\n"
                f"Comprimento: {len(frame)} bytes\n"
                f"Checksum válido: {validate_request(frame)}\n\n"
                f"{format_hex(frame)}\n"
            )
        except Exception as error:
            text = f"Erro: {type(error).__name__}: {error}"
        self._replace_text(self.simulation_text, text)

    def _save_session(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Salvar sessão OTA",
            defaultextension=".jsonl",
            filetypes=(("JSON Lines", "*.jsonl"), ("Todos os arquivos", "*.*")),
            initialfile="orbis-g28-ota-session.jsonl",
        )
        if not path:
            return
        with Path(path).open("w", encoding="utf-8") as handle:
            metadata = {
                "type": "metadata",
                "application": APP_TITLE,
                "protocol_negotiated": self.protocol_negotiated,
                "identity": asdict(self.identity) if self.identity else None,
                "transport": self.link.profile_name,
            }
            handle.write(json.dumps(metadata, ensure_ascii=False) + "\n")
            for record in self.traffic:
                handle.write(json.dumps({"type": "traffic", **asdict(record)}, ensure_ascii=False) + "\n")
        self._log(f"Sessão salva: {path}")

    def _validate_manifest(self) -> None:
        path = filedialog.askopenfilename(filetypes=(("JSON", "*.json"), ("Todos os arquivos", "*.*")))
        if not path:
            return
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            required_root = {"device", "version", "parts"}
            missing_root = required_root - set(data)
            if missing_root:
                raise ValueError(f"campos ausentes: {', '.join(sorted(missing_root))}")
            if not isinstance(data["parts"], list) or not data["parts"]:
                raise ValueError("parts precisa ser uma lista não vazia")
            required_part = {"part_id", "address", "length", "file", "sha256"}
            for index, part in enumerate(data["parts"]):
                missing = required_part - set(part)
                if missing:
                    raise ValueError(f"parts[{index}] sem: {', '.join(sorted(missing))}")
                if int(part["length"]) <= 0:
                    raise ValueError(f"parts[{index}].length precisa ser positivo")
            self.manifest_var.set(
                f"Estrutura válida: dispositivo={data['device']}, versão={data['version']}, partes={len(data['parts'])}. "
                "Nenhum arquivo foi transmitido."
            )
        except Exception as error:
            self.manifest_var.set(f"Manifesto rejeitado: {type(error).__name__}: {error}")

    def _thread_log(self, message: str) -> None:
        self.ui_queue.put(("log", message))

    def _thread_traffic(self, record: TrafficRecord) -> None:
        self.ui_queue.put(("traffic", record))

    def _thread_response(self, response: OtaResponse) -> None:
        self.ui_queue.put(("response", response))

    def _handle_response(self, response: OtaResponse) -> None:
        self._log(
            f"D6/0x{response.command:02X} {response.command_name}: status={response.status}, "
            f"bloco={response.block}, fragmento={response.fragment}, payload={format_hex(response.payload)}"
        )
        if response.command == 0x0F and response.status == 1:
            version = response.payload.decode("utf-8", errors="replace").strip("\x00 \r\n\t")
            self.protocol_negotiated = version == "V1.1"
            self.protocol_var.set(f"Protocolo: {version or '(vazio)'} | parityStyle=true | validado={self.protocol_negotiated}")
        elif response.command == 0x01 and response.status == 1:
            self.identity = parse_identity(response.payload)
            self.identity_var.set(
                f"Identidade: versão={self.identity.version or '?'} | projeto={self.identity.project or '?'} | "
                f"prefixo={self.identity.prefix_hex} | unique_code={self.identity.unique_code}"
            )

    def _drain_ui_queue(self) -> None:
        try:
            while True:
                event, payload = self.ui_queue.get_nowait()
                if event == "log":
                    self._log(str(payload))
                elif event == "traffic":
                    self.traffic.append(payload)  # type: ignore[arg-type]
                elif event == "response":
                    self._handle_response(payload)  # type: ignore[arg-type]
                elif event == "scan_done":
                    self.scan_button.configure(state="normal")
                    future = payload
                    try:
                        self.devices = future.result()
                    except Exception as error:
                        self.status_var.set("Falha no escaneamento")
                        messagebox.showerror(APP_TITLE, f"Falha no escaneamento BLE:\n{error}")
                    else:
                        self.device_combo["values"] = [device.label for device in self.devices]
                        if self.devices:
                            self.device_combo.current(0)
                        self.status_var.set(f"{len(self.devices)} candidato(s) encontrado(s)")
                elif event == "connect_done":
                    future = payload
                    try:
                        profile = future.result()
                    except Exception as error:
                        self.status_var.set("Falha na conexão")
                        messagebox.showerror(APP_TITLE, f"Falha ao conectar:\n{error}")
                    else:
                        self.status_var.set("Conectado ao bootloader OTA")
                        self.transport_var.set(f"Transporte: {profile}")
                        self.protocol_negotiated = False
                        self.identity = None
                elif event == "disconnect_done":
                    future = payload
                    try:
                        future.result()
                    except Exception as error:
                        self._log(f"Falha ao desconectar: {error}")
                    self.status_var.set("Desconectado")
                elif event == "command_done":
                    future = payload
                    try:
                        future.result()
                    except Exception as error:
                        messagebox.showerror(APP_TITLE, f"Falha ao transmitir consulta segura:\n{error}")
        except queue.Empty:
            pass
        self.after(80, self._drain_ui_queue)

    def _log(self, message: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert("end", message + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    @staticmethod
    def _replace_text(widget: tk.Text, content: str) -> None:
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", content)
        widget.configure(state="disabled")

    def _close(self) -> None:
        try:
            self.worker.submit(self.link.disconnect()).result(timeout=3)
        except Exception:
            pass
        self.worker.stop()
        self.destroy()


if __name__ == "__main__":
    RecoveryStudio().mainloop()
