from pathlib import Path

JAVA = Path('android/OrbisG28Bridge/app/src/main/java/com/orbisg28bridge/BridgeActivity.java')
BUILD = Path('android/OrbisG28Bridge/app/build.gradle')
README = Path('android/OrbisG28Bridge/README_BRIDGE.md')
PC = Path('pc/orbis_g28_bridge/orbis_g28_pc.py')
INSTRUCTIONS = Path('pc/orbis_g28_bridge/INSTRUCOES.txt')

text = JAVA.read_text(encoding='utf-8')

old_state = '''    private boolean notificationsReady;
    private boolean protocolValid;
    private String protocolVersion = "";
'''
new_state = '''    private boolean notificationsReady;
    private boolean protocolValid;
    private boolean rebootAttemptUsed;
    private String protocolVersion = "";
'''
if old_state not in text:
    raise SystemExit('state block not found')
text = text.replace(old_state, new_state, 1)

old_case = '''                case "identity":
                    sendSafeFrame(id, 0x01, new byte[0]);
                    break;
                default:
'''
new_case = '''                case "identity":
                    sendSafeFrame(id, 0x01, new byte[0]);
                    break;
                case "finalize_reboot":
                    sendRebootOnce(id);
                    break;
                default:
'''
if old_case not in text:
    raise SystemExit('command switch block not found')
text = text.replace(old_case, new_case, 1)

marker = '''    private void sendSafeFrame(int requestId, int command, byte[] payload) {
'''
method = '''    private void sendRebootOnce(int requestId) {
        if (rebootAttemptUsed) {
            sendFailure(requestId, "D5/0E já foi enviado nesta sessão do aplicativo");
            return;
        }
        if (gatt == null || writeCharacteristic == null || !notificationsReady) {
            sendFailure(requestId, "Conecte ao G28 e aguarde as notificações OTA");
            return;
        }
        rebootAttemptUsed = true;
        append("TENTATIVA FINAL: enviando somente D5/0E para encerrar/reiniciar a sessão OTA.");
        sendSafeFrame(requestId, 0x0E, new byte[0]);
    }

'''
if marker not in text:
    raise SystemExit('sendSafeFrame marker not found')
text = text.replace(marker, method + marker, 1)

old_guard = '''        if (command != 0x0F && command != 0x01) {
'''
new_guard = '''        if (command != 0x0F && command != 0x01 && command != 0x0E) {
'''
if old_guard not in text:
    raise SystemExit('command allow-list not found')
text = text.replace(old_guard, new_guard, 1)

old_parse = '''        } else if (command == 0x01 && status == 1) {
            parseIdentity(payload);
        }
'''
new_parse = '''        } else if (command == 0x01 && status == 1) {
            parseIdentity(payload);
        } else if (command == 0x0E) {
            try {
                JSONObject event = new JSONObject();
                event.put("type", "reboot_ack");
                event.put("status", status);
                event.put("payload_hex", hexCompact(payload));
                sendJson(event);
            } catch (Exception ignored) { }
        }
'''
if old_parse not in text:
    raise SystemExit('parse block not found')
text = text.replace(old_parse, new_parse, 1)

text = text.replace('Ponte carregada. Somente D5/0F e D5/01 são permitidos.',
                    'Ponte carregada. D5/0F e D5/01 são consultas; D5/0E é uma tentativa final de reinício, limitada a uma vez.')
text = text.replace('Este aplicativo não contém firmware e bloqueia comandos de gravação.',
                    'Este aplicativo não contém firmware. Bloqueia partições e dados; permite uma única tentativa D5/0E de reinício OTA.')
text = text.replace('Orbis G28 BLE Bridge v2.2', 'Orbis G28 BLE Bridge v2.3')
text = text.replace('event.put("version", "2.2")', 'event.put("version", "2.3")')
JAVA.write_text(text, encoding='utf-8')

build = BUILD.read_text(encoding='utf-8')
build = build.replace('versionCode 220', 'versionCode 230')
build = build.replace("versionName '2.2-background-socket-writes'", "versionName '2.3-one-shot-ota-reboot'")
BUILD.write_text(build, encoding='utf-8')

pc = PC.read_text(encoding='utf-8')
pc = pc.replace('Android BLE Bridge v2.1', 'Android BLE Bridge v2.3')

old_ui = '''        ttk.Button(safe_frame, text="Salvar log", command=self._save_log).pack(side="right", padx=4)

        self.identity = ttk.LabelFrame(self, text="Identidade do bootloader", padding=10)
'''
new_ui = '''        ttk.Button(safe_frame, text="Salvar log", command=self._save_log).pack(side="right", padx=4)

        final_frame = ttk.LabelFrame(self, text="4. Tentativa final por Bluetooth", padding=10)
        final_frame.pack(fill="x", padx=12, pady=6)
        ttk.Label(
            final_frame,
            text="Envia uma única vez D5/0E, sem firmware, para encerrar/reiniciar a sessão OTA.",
        ).pack(side="left", padx=4)
        ttk.Button(
            final_frame,
            text="Tentar sair do bootloader — D5/0E",
            command=self._final_reboot,
        ).pack(side="right", padx=4)

        self.identity = ttk.LabelFrame(self, text="Identidade do bootloader", padding=10)
'''
if old_ui not in pc:
    raise SystemExit('PC UI insertion point not found')
pc = pc.replace(old_ui, new_ui, 1)

old_append = '''        self._append("Esta versão só permite D5/0F e D5/01. Não há comandos de gravação.")

    def _append(self, text: str) -> None:
'''
new_append = '''        self._append("D5/0F e D5/01 são consultas. D5/0E é uma tentativa final, sem firmware, limitada a uma vez no APK.")

    def _final_reboot(self) -> None:
        confirmed = messagebox.askyesno(
            "Tentativa final D5/0E",
            "Enviar agora o comando D5/0E?\n\n"
            "Ele não transmite firmware nem tabela de partições. Ele encerra/reinicia a sessão OTA e pode desconectar o relógio imediatamente.\n\n"
            "Use somente uma vez. Se o G28 voltar no endereço terminado em :02, a tentativa falhou e o projeto será encerrado.",
        )
        if confirmed:
            self._send("finalize_reboot")

    def _append(self, text: str) -> None:
'''
if old_append not in pc:
    raise SystemExit('PC method insertion point not found')
pc = pc.replace(old_append, new_append, 1)

old_event = '''        elif etype == "identity":
            self.identity_text.configure(text=(
                f"Protocolo: {event.get('protocol', '—')}    Versão: {event.get('version', '—')}    "
                f"Projeto: {event.get('project', '—')}    Unique code: {event.get('unique_code', '—')}"
            ))
        elif etype in {"pc_error", "bridge_error", "error"}:
'''
new_event = '''        elif etype == "identity":
            self.identity_text.configure(text=(
                f"Protocolo: {event.get('protocol', '—')}    Versão: {event.get('version', '—')}    "
                f"Projeto: {event.get('project', '—')}    Unique code: {event.get('unique_code', '—')}"
            ))
        elif etype == "reboot_ack":
            self._append(f"D6/0E recebido: status={event.get('status')} payload={event.get('payload_hex', '')}")
        elif etype in {"pc_error", "bridge_error", "error"}:
'''
if old_event not in pc:
    raise SystemExit('PC event insertion point not found')
pc = pc.replace(old_event, new_event, 1)
PC.write_text(pc, encoding='utf-8')

README.write_text(
    '# Orbis G28 Android BLE Bridge v2.3\n\n'
    'Tentativa final por Bluetooth: adiciona somente D5/0E sem payload, exatamente como o HryFine envia após uma OTA concluída.\n\n'
    'A ponte continua bloqueando tabela de partições, firmware, dados, checksums e qualquer comando fora de D5/0F, D5/01 e D5/0E.\n\n'
    'O D5/0E pode ser enviado apenas uma vez durante a execução do aplicativo.\n',
    encoding='utf-8',
)

INSTRUCTIONS.write_text(
    'ORBIS G28 — TENTATIVA FINAL BLUETOOTH v2.3\n\n'
    '1. Instale o APK v2.3 no Android e inicie a ponte USB.\n'
    '2. Abra este controlador no PC.\n'
    '3. Conecte ao celular, escaneie e conecte ao G28 terminado em :02.\n'
    '4. Valide D5/0F e leia D5/01.\n'
    '5. Clique uma única vez em Tentar sair do bootloader — D5/0E.\n'
    '6. Aguarde 20 segundos e escaneie novamente.\n\n'
    'Sucesso: o relógio inicia ou reaparece no endereço normal terminado em :57.\n'
    'Falha: ele reaparece em :02. Nesse caso, encerre os testes.\n',
    encoding='utf-8',
)
