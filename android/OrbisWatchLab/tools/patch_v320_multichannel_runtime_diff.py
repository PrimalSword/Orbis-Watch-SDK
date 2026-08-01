from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: patch_v320_multichannel_runtime_diff.py <MainActivity.java>')

path = Path(sys.argv[1])
src = path.read_text(encoding='utf-8')

src = src.replace('Orbis Watch OTA 5610 v3.19', 'Orbis Watch OTA 5610 v3.20')
src = src.replace('A v3.19 acrescenta consultas oficiais de configuração e identificação do produto no firmware normal; handshake e identidade continuam manuais.',
                  'A v3.20 acrescenta captura multicanal e comparação A/B das configurações, sem alterar hora, RTC ou firmware; handshake e identidade continuam manuais.')

field_anchor = '''    private boolean passiveCaptureRunning;
    private int passiveCaptureNotifications;
    private long passiveCaptureStartedAt;
'''
field_insert = '''    private boolean passiveCaptureRunning;
    private int passiveCaptureNotifications;
    private long passiveCaptureStartedAt;
    private final Map<String, Integer> passiveChannelCounts = new LinkedHashMap<>();
    private byte[] runtimeSettingsBytes = new byte[0];
    private byte[] runtimeSettingsSnapshotA = new byte[0];
    private byte[] runtimeSettingsSnapshotB = new byte[0];
    private int runtimeSettingsSnapshotTarget;
    private boolean runtimeAllNotifyRequested;
'''
if field_anchor not in src:
    raise SystemExit('v3.20 field anchor missing')
src = src.replace(field_anchor, field_insert, 1)

ui_anchor = '''        Button runtimeReport = button("11. Gerar relatório runtime — local");
        runtimeReport.setOnClickListener(v -> appendRuntimeSurveyReport());
        content.addView(runtimeReport, marginLayout(0, 2, 0, 3));

'''
ui_insert = ui_anchor + '''        Button allRuntimeNotify = button("12. Ativar canais runtime NUS/FF14/FF01/bateria — somente CCCD");
        allRuntimeNotify.setOnClickListener(v -> activateAllRuntimeNotifications());
        content.addView(allRuntimeNotify, marginLayout(0, 2, 0, 2));

        Button settingsSnapshotA = button("13. Capturar configurações A — leitura NUS 0x09");
        settingsSnapshotA.setOnClickListener(v -> requestRuntimeSettingsSnapshot(1));
        content.addView(settingsSnapshotA, marginLayout(0, 2, 0, 2));

        Button settingsSnapshotB = button("14. Capturar configurações B e comparar — leitura NUS 0x09");
        settingsSnapshotB.setOnClickListener(v -> requestRuntimeSettingsSnapshot(2));
        content.addView(settingsSnapshotB, marginLayout(0, 2, 0, 2));

        Button multiPassiveCapture = button("15. Captura multicanal por 60 s — sem comando de aplicação");
        multiPassiveCapture.setOnClickListener(v -> startMultiChannelRuntimeCapture());
        content.addView(multiPassiveCapture, marginLayout(0, 2, 0, 2));

        Button runtimeDiffReport = button("16. Gerar relatório multicanal/diferencial — local");
        runtimeDiffReport.setOnClickListener(v -> appendRuntimeDiffReport());
        content.addView(runtimeDiffReport, marginLayout(0, 2, 0, 3));

'''
if ui_anchor not in src:
    raise SystemExit('v3.20 UI anchor missing')
src = src.replace(ui_anchor, ui_insert, 1)

passive_anchor = '''        if (passiveCaptureRunning) {
            passiveCaptureNotifications++;
            append("  ↳ PASSIVO #" + passiveCaptureNotifications + " canal=" + characteristic.getUuid()
                    + " len=" + copy.length + " ASCII=" + printableAscii(copy));
        }
'''
passive_insert = '''        if (passiveCaptureRunning) {
            passiveCaptureNotifications++;
            String channel = characteristic.getUuid().toString();
            passiveChannelCounts.put(channel, passiveChannelCounts.getOrDefault(channel, 0) + 1);
            append("  ↳ PASSIVO #" + passiveCaptureNotifications + " canal=" + characteristic.getUuid()
                    + " len=" + copy.length + " ASCII=" + printableAscii(copy));
        }
'''
if passive_anchor not in src:
    raise SystemExit('v3.20 passive counter anchor missing')
src = src.replace(passive_anchor, passive_insert, 1)

settings_anchor = '''                runtimeSettingsReceived = true;
                runtimeSettingsPayload = hex(genericPayload);
                append("RUNTIME SETTINGS RX → key=0x" + String.format(Locale.US, "%02X", key)
                        + " len=" + genericPayload.length
                        + " payload=" + hex(genericPayload)
                        + " ASCII=" + printableAscii(genericPayload));
                append("RUNTIME SETTINGS: dados preservados em formato bruto; nenhum campo será alterado ou adivinhado.");
'''
settings_insert = '''                runtimeSettingsReceived = true;
                runtimeSettingsPayload = hex(genericPayload);
                runtimeSettingsBytes = genericPayload.clone();
                append("RUNTIME SETTINGS RX → key=0x" + String.format(Locale.US, "%02X", key)
                        + " len=" + genericPayload.length
                        + " payload=" + hex(genericPayload)
                        + " ASCII=" + printableAscii(genericPayload));
                if (runtimeSettingsSnapshotTarget == 1) {
                    runtimeSettingsSnapshotA = genericPayload.clone();
                    runtimeSettingsSnapshotTarget = 0;
                    append("CONFIGURAÇÕES A armazenadas localmente: bytes=" + runtimeSettingsSnapshotA.length);
                } else if (runtimeSettingsSnapshotTarget == 2) {
                    runtimeSettingsSnapshotB = genericPayload.clone();
                    runtimeSettingsSnapshotTarget = 0;
                    append("CONFIGURAÇÕES B armazenadas localmente: bytes=" + runtimeSettingsSnapshotB.length);
                    appendRuntimeSettingsDiff();
                }
                append("RUNTIME SETTINGS: dados preservados em formato bruto; nenhum campo será alterado ou adivinhado.");
'''
if settings_anchor not in src:
    raise SystemExit('v3.20 settings parser anchor missing')
src = src.replace(settings_anchor, settings_insert, 1)

methods_anchor = '''    private void appendRuntimeSurveyReport() {
'''
methods = r'''    private void activateAllRuntimeNotifications() {
        if (emergencyStopped || gatt == null || !hasConnectPermission()) {
            toast("Conecte ao G28 no modo normal primeiro");
            return;
        }
        if (otaObserved18a8Transport || otaWrite != null) {
            toast("Esta função é somente para o firmware normal");
            return;
        }
        notifyQueue.clear();
        int queued = 0;
        if (!nusLinkValidated && nusNotify != null) {
            notifyQueue.add(nusNotify);
            queued++;
        }
        if (ff14Notify != null) {
            notifyQueue.add(ff14Notify);
            queued++;
        }
        if (ff01Notify != null) {
            notifyQueue.add(ff01Notify);
            queued++;
        }
        if (batteryCharacteristic != null
                && (batteryCharacteristic.getProperties() & BluetoothGattCharacteristic.PROPERTY_NOTIFY) != 0) {
            notifyQueue.add(batteryCharacteristic);
            queued++;
        }
        runtimeAllNotifyRequested = true;
        append("===== ATIVAÇÃO MULTICANAL RUNTIME v3.20 =====");
        append("CCCDs enfileirados=" + queued
                + "; isto ativa notificações BLE, sem comando de configuração, hora, RTC ou firmware.");
        if (queued == 0) {
            append("Nenhum CCCD adicional encontrado para ativar.");
            return;
        }
        configureNextNotification();
    }

    private void requestRuntimeSettingsSnapshot(int target) {
        if (!ensureNusSession("capturar configurações A/B")) return;
        if (target == 2 && runtimeSettingsSnapshotA.length == 0) {
            toast("Capture primeiro as configurações A");
            append("CONFIGURAÇÕES B BLOQUEADAS: snapshot A ainda não existe.");
            return;
        }
        runtimeSettingsSnapshotTarget = target;
        runtimeSettingsReceived = false;
        byte[] frame = buildNusCommand(0x09, 0x00, new byte[0]);
        append("CONFIGURAÇÕES " + (target == 1 ? "A" : "B")
                + " TX: leitura oficial NUS 0x09/0x00 → " + hex(frame));
        sendNusFrame(frame);
        schedule(8_000, () -> {
            if (runtimeSettingsSnapshotTarget == target) {
                append("CONFIGURAÇÕES " + (target == 1 ? "A" : "B")
                        + ": janela encerrada sem resposta DF/0x09.");
                runtimeSettingsSnapshotTarget = 0;
            }
        });
    }

    private void appendRuntimeSettingsDiff() {
        append("===== DIFERENÇA CONFIGURAÇÕES A/B v3.20 =====");
        if (runtimeSettingsSnapshotA.length == 0 || runtimeSettingsSnapshotB.length == 0) {
            append("Comparação indisponível: capture A e B.");
            append("===== FIM DIFERENÇA A/B =====");
            return;
        }
        int max = Math.max(runtimeSettingsSnapshotA.length, runtimeSettingsSnapshotB.length);
        int changes = 0;
        for (int i = 0; i < max; i++) {
            int a = i < runtimeSettingsSnapshotA.length ? runtimeSettingsSnapshotA[i] & 0xFF : -1;
            int b = i < runtimeSettingsSnapshotB.length ? runtimeSettingsSnapshotB[i] & 0xFF : -1;
            if (a != b) {
                changes++;
                append(String.format(Locale.US,
                        "DIFF offset=%d (0x%02X) A=%s B=%s",
                        i, i,
                        a < 0 ? "--" : String.format(Locale.US, "%02X", a),
                        b < 0 ? "--" : String.format(Locale.US, "%02X", b)));
            }
        }
        append("DIFF total_offsets_alterados=" + changes
                + " tamanho_A=" + runtimeSettingsSnapshotA.length
                + " tamanho_B=" + runtimeSettingsSnapshotB.length);
        if (changes == 0) {
            append("Nenhum byte mudou entre A e B.");
        } else {
            append("Os offsets são evidência bruta; a v3.20 não atribui significado sem teste de ida e volta.");
        }
        append("===== FIM DIFERENÇA A/B =====");
    }

    private void startMultiChannelRuntimeCapture() {
        if (!ensureNusSession("captura multicanal")) return;
        if (!runtimeAllNotifyRequested) {
            toast("Execute primeiro o passo 12 para ativar FF14, FF01 e bateria");
            append("CAPTURA MULTICANAL BLOQUEADA: canais adicionais ainda não foram solicitados.");
            return;
        }
        if (passiveCaptureRunning) {
            toast("Captura passiva já está em andamento");
            return;
        }
        passiveCaptureRunning = true;
        passiveCaptureNotifications = 0;
        passiveChannelCounts.clear();
        passiveCaptureStartedAt = System.currentTimeMillis();
        append("===== CAPTURA MULTICANAL RUNTIME v3.20 =====");
        append("Janela=60 s; nenhum comando de aplicação será transmitido. CCCDs já ativados podem entregar NUS, FF14, FF01 e bateria.");
        schedule(60_000, () -> {
            passiveCaptureRunning = false;
            long elapsed = Math.max(0, System.currentTimeMillis() - passiveCaptureStartedAt);
            append("CAPTURA MULTICANAL concluída: notificações=" + passiveCaptureNotifications
                    + " duração_ms=" + elapsed + ".");
            for (Map.Entry<String, Integer> entry : passiveChannelCounts.entrySet()) {
                append("CANAL " + entry.getKey() + " notificações=" + entry.getValue());
            }
            if (passiveChannelCounts.isEmpty()) {
                append("Nenhum canal emitiu notificação espontânea durante a janela.");
            }
            append("===== FIM CAPTURA MULTICANAL =====");
        });
    }

    private void appendRuntimeDiffReport() {
        append("===== RELATÓRIO MULTICANAL/DIFERENCIAL G28 v3.20 =====");
        append("all_notify_requested=" + runtimeAllNotifyRequested
                + " nus_validado=" + nusLinkValidated
                + " ff14_ativo=" + ff14NotificationsReady
                + " ff01_ativo=" + ff01NotificationsReady);
        append("settings_latest_bytes=" + runtimeSettingsBytes.length
                + " snapshot_A=" + runtimeSettingsSnapshotA.length
                + " snapshot_B=" + runtimeSettingsSnapshotB.length);
        append("passive_total=" + passiveCaptureNotifications
                + " canais=" + passiveChannelCounts.size());
        for (Map.Entry<String, Integer> entry : passiveChannelCounts.entrySet()) {
            append("runtime_channel=" + entry.getKey() + " count=" + entry.getValue());
        }
        append("product_0x20: neste G28 foi observado ACK FD sem payload DF; não será usado como requisito de compatibilidade.");
        append("hora/RTC: envio permanece bloqueado até recuperar o quadro exato de SettingIssuedUtils.settingSysTime().");
        append("REQUISITOS IMUTÁVEIS: horas/RTC; BLE de manutenção; saída do Doom; recuperação sem abrir o relógio.");
        append("===== FIM RELATÓRIO MULTICANAL/DIFERENCIAL =====");
        appendRuntimeSettingsDiff();
    }

'''
if methods_anchor not in src:
    raise SystemExit('v3.20 method insertion anchor missing')
src = src.replace(methods_anchor, methods + methods_anchor, 1)

src = src.replace('===== CAPTURA PASSIVA RUNTIME v3.19 =====', '===== CAPTURA PASSIVA RUNTIME v3.20 =====')
src = src.replace('===== RELATÓRIO RUNTIME G28 v3.19 =====', '===== RELATÓRIO RUNTIME G28 v3.20 =====')
src = src.replace('A v3.17 permite o handshake D5/0x0F e, somente após V1.1, a consulta D5/0x01.',
                  'A v3.20 mantém o handshake D5/0x0F e a consulta D5/0x01, além do inventário runtime sem escrita de firmware.')

required = [
    'Orbis Watch OTA 5610 v3.20',
    '12. Ativar canais runtime NUS/FF14/FF01/bateria — somente CCCD',
    '13. Capturar configurações A — leitura NUS 0x09',
    '14. Capturar configurações B e comparar — leitura NUS 0x09',
    '15. Captura multicanal por 60 s — sem comando de aplicação',
    '16. Gerar relatório multicanal/diferencial — local',
    'ATIVAÇÃO MULTICANAL RUNTIME v3.20',
    'DIFERENÇA CONFIGURAÇÕES A/B v3.20',
    'CAPTURA MULTICANAL RUNTIME v3.20',
    'RELATÓRIO MULTICANAL/DIFERENCIAL G28 v3.20',
    'settingSysTime()',
]
for marker in required:
    if marker not in src:
        raise SystemExit('missing v3.20 marker: ' + marker)

path.write_text(src, encoding='utf-8')
print('v3.20 multichannel runtime diff patch applied')
