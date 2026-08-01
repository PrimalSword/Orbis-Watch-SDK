from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: patch_v319_runtime_capability_survey.py <MainActivity.java>')

path = Path(sys.argv[1])
src = path.read_text(encoding='utf-8')

src = src.replace('Orbis Watch OTA 5610 v3.18', 'Orbis Watch OTA 5610 v3.19')
src = src.replace('A v3.18 acrescenta um baseline somente leitura e um passaporte de recuperação; handshake e identidade continuam manuais.',
                  'A v3.19 acrescenta consultas oficiais de configuração e identificação do produto no firmware normal; handshake e identidade continuam manuais.')

field_anchor = '''    private String preservationNormalAddress = "";
    private String preservationBootAddress = "";
'''
field_insert = field_anchor + '''    private boolean runtimeSettingsReceived;
    private boolean runtimeProductReceived;
    private String runtimeSettingsPayload = "";
    private String runtimeProductPayload = "";
    private boolean passiveCaptureRunning;
    private int passiveCaptureNotifications;
    private long passiveCaptureStartedAt;
'''
if field_anchor not in src:
    raise SystemExit('v3.19 field anchor missing')
src = src.replace(field_anchor, field_insert, 1)

ui_anchor = '''        Button protocolMap = button("7. Mostrar próxima etapa OTA — sem transmitir");
        protocolMap.setOnClickListener(v -> logOfficialProtocolMap());
        content.addView(protocolMap, marginLayout(0, 2, 0, 3));

'''
ui_insert = ui_anchor + '''        content.addView(section("Inventário do firmware normal — consultas oficiais"), matchWrap());
        TextView runtimeSurveyNote = text(
                "Estas consultas usam o canal NUS do firmware normal e solicitam somente dados já expostos pelo HryFine: "
                        + "configurações atuais (0x09/0x00) e identificação do produto (0x20/0x00). "
                        + "Não alteram hora, mostrador, RTC, partições ou firmware.",
                12, false);
        content.addView(runtimeSurveyNote, marginLayout(2, 1, 2, 4));

        Button runtimeSettings = button("8. Consultar configurações atuais — NUS 0x09/0x00");
        runtimeSettings.setOnClickListener(v -> confirmRuntimeSettingsQuery());
        content.addView(runtimeSettings, marginLayout(0, 2, 0, 2));

        Button runtimeProduct = button("9. Consultar identificação do produto — NUS 0x20/0x00");
        runtimeProduct.setOnClickListener(v -> confirmRuntimeProductQuery());
        content.addView(runtimeProduct, marginLayout(0, 2, 0, 2));

        Button passiveCapture = button("10. Escutar notificações passivas por 30 s — sem TX");
        passiveCapture.setOnClickListener(v -> startPassiveRuntimeCapture());
        content.addView(passiveCapture, marginLayout(0, 2, 0, 2));

        Button runtimeReport = button("11. Gerar relatório runtime — local");
        runtimeReport.setOnClickListener(v -> appendRuntimeSurveyReport());
        content.addView(runtimeReport, marginLayout(0, 2, 0, 3));

'''
if ui_anchor not in src:
    raise SystemExit('v3.19 UI anchor missing')
src = src.replace(ui_anchor, ui_insert, 1)

method_anchor = '''    private void requestNusOtaInfo() {
'''
methods = '''    private void confirmRuntimeSettingsQuery() {
        if (!ensureNusSession("consultar configurações atuais")) return;
        new AlertDialog.Builder(this)
                .setTitle("Consultar configurações atuais?")
                .setMessage("Será enviado somente GeneralUtils.requsetSettingInfo(): NUS 0x09/0x00, sem payload. "
                        + "É uma solicitação de leitura usada pelo HryFine. Nenhuma configuração, hora, RTC ou firmware será alterado.")
                .setNegativeButton("Cancelar", null)
                .setPositiveButton("CONSULTAR 0x09", (dialog, which) -> requestRuntimeSettings())
                .show();
    }

    private void requestRuntimeSettings() {
        if (!ensureNusSession("consultar configurações atuais")) return;
        runtimeSettingsReceived = false;
        runtimeSettingsPayload = "";
        byte[] frame = buildNusCommand(0x09, 0x00, new byte[0]);
        append("RUNTIME SETTINGS TX: GeneralUtils.requsetSettingInfo() → " + hex(frame));
        sendNusFrame(frame);
        schedule(8_000, () -> {
            if (!runtimeSettingsReceived) append("RUNTIME SETTINGS: janela encerrada sem resposta DF/0x09.");
        });
    }

    private void confirmRuntimeProductQuery() {
        if (!ensureNusSession("consultar identificação do produto")) return;
        new AlertDialog.Builder(this)
                .setTitle("Consultar identificação do produto?")
                .setMessage("Será enviado somente GeneralUtils.requestProductIdentification(): NUS 0x20/0x00, sem payload. "
                        + "É uma solicitação de leitura usada pelo HryFine. Nenhuma configuração ou firmware será alterado.")
                .setNegativeButton("Cancelar", null)
                .setPositiveButton("CONSULTAR 0x20", (dialog, which) -> requestRuntimeProduct())
                .show();
    }

    private void requestRuntimeProduct() {
        if (!ensureNusSession("consultar identificação do produto")) return;
        runtimeProductReceived = false;
        runtimeProductPayload = "";
        byte[] frame = buildNusCommand(0x20, 0x00, new byte[0]);
        append("RUNTIME PRODUCT TX: GeneralUtils.requestProductIdentification() → " + hex(frame));
        sendNusFrame(frame);
        schedule(8_000, () -> {
            if (!runtimeProductReceived) append("RUNTIME PRODUCT: janela encerrada sem resposta DF/0x20.");
        });
    }

    private void startPassiveRuntimeCapture() {
        if (!ensureNusSession("capturar notificações passivas")) return;
        if (passiveCaptureRunning) {
            toast("Captura passiva já está em andamento");
            return;
        }
        passiveCaptureRunning = true;
        passiveCaptureNotifications = 0;
        passiveCaptureStartedAt = System.currentTimeMillis();
        append("===== CAPTURA PASSIVA RUNTIME v3.19 =====");
        append("Janela=30 s; nenhum comando será transmitido. Interaja normalmente com o relógio sem abrir o modo OTA.");
        schedule(30_000, () -> {
            passiveCaptureRunning = false;
            long elapsed = Math.max(0, System.currentTimeMillis() - passiveCaptureStartedAt);
            append("CAPTURA PASSIVA concluída: notificações=" + passiveCaptureNotifications
                    + " duração_ms=" + elapsed + ". Nenhum TX foi realizado pela captura.");
            append("===== FIM CAPTURA PASSIVA =====");
        });
    }

    private void appendRuntimeSurveyReport() {
        append("===== RELATÓRIO RUNTIME G28 v3.19 =====");
        append("baseline_reads=" + preservationReadSuccess + "/" + preservationReadTotal);
        append("battery_uuid=180F/2A19 último baseline=64 (100%)");
        append("device_information=serial 10000004; hw_rev 10000; fw_rev 10000; software_rev binário de 26 bytes");
        append("runtime_transport=NUS 6E400001/2/3; alternativos=FF12/FF13/FF14 e FF00/FF01/FF02");
        append("settings_0x09_recebido=" + runtimeSettingsReceived
                + " payload=" + emptyAsDash(runtimeSettingsPayload));
        append("product_0x20_recebido=" + runtimeProductReceived
                + " payload=" + emptyAsDash(runtimeProductPayload));
        append("passive_notifications_last_window=" + passiveCaptureNotifications);
        append("REQUISITOS IMUTÁVEIS: horas/RTC; BLE de manutenção; saída do Doom; recuperação sem abrir o relógio.");
        append("===== FIM RELATÓRIO RUNTIME =====");
    }

'''
if method_anchor not in src:
    raise SystemExit('v3.19 method anchor missing')
src = src.replace(method_anchor, methods + method_anchor, 1)

notification_anchor = '''        byte[] copy = value == null ? new byte[0] : value.clone();
        append("RX " + characteristic.getUuid() + " " + hex(copy));

'''
notification_insert = '''        byte[] copy = value == null ? new byte[0] : value.clone();
        append("RX " + characteristic.getUuid() + " " + hex(copy));
        if (passiveCaptureRunning) {
            passiveCaptureNotifications++;
            append("  ↳ PASSIVO #" + passiveCaptureNotifications + " canal=" + characteristic.getUuid()
                    + " len=" + copy.length + " ASCII=" + printableAscii(copy));
        }

'''
if notification_anchor not in src:
    raise SystemExit('v3.19 notification anchor missing')
src = src.replace(notification_anchor, notification_insert, 1)

parser_anchor = '''        if (command == 0xF3 && prefix == 0xDF) {
            nusLinkValidated = true;
            setStatus("G28 conectado e validado pelo protocolo NUS");
            append("LINK VALIDADO: resposta completa DEVICE_INFO 0xF3 recebida.");
            return;
        }

        if (command != 0x13 || prefix != 0xDF) return;
'''
parser_insert = '''        if (command == 0xF3 && prefix == 0xDF) {
            nusLinkValidated = true;
            setStatus("G28 conectado e validado pelo protocolo NUS");
            append("LINK VALIDADO: resposta completa DEVICE_INFO 0xF3 recebida.");
            return;
        }

        byte[] genericPayload = frame.length > 9
                ? java.util.Arrays.copyOfRange(frame, 9, frame.length)
                : new byte[0];
        if (command == 0x09) {
            if (prefix == 0xDF) {
                runtimeSettingsReceived = true;
                runtimeSettingsPayload = hex(genericPayload);
                append("RUNTIME SETTINGS RX → key=0x" + String.format(Locale.US, "%02X", key)
                        + " len=" + genericPayload.length
                        + " payload=" + hex(genericPayload)
                        + " ASCII=" + printableAscii(genericPayload));
                append("RUNTIME SETTINGS: dados preservados em formato bruto; nenhum campo será alterado ou adivinhado.");
            } else {
                append("RUNTIME SETTINGS ACK FD → key=0x" + String.format(Locale.US, "%02X", key));
            }
            return;
        }
        if (command == 0x20) {
            if (prefix == 0xDF) {
                runtimeProductReceived = true;
                runtimeProductPayload = hex(genericPayload);
                append("RUNTIME PRODUCT RX → key=0x" + String.format(Locale.US, "%02X", key)
                        + " len=" + genericPayload.length
                        + " payload=" + hex(genericPayload)
                        + " ASCII=" + printableAscii(genericPayload));
            } else {
                append("RUNTIME PRODUCT ACK FD → key=0x" + String.format(Locale.US, "%02X", key));
            }
            return;
        }

        if (command != 0x13 || prefix != 0xDF) return;
'''
if parser_anchor not in src:
    raise SystemExit('v3.19 parser anchor missing')
src = src.replace(parser_anchor, parser_insert, 1)

src = src.replace('Firmware: BLOQUEADO — bootloader e consultas somente leitura',
                  'Firmware: BLOQUEADO — baseline e consultas runtime/bootloader sem dados de firmware')

required = [
    'Orbis Watch OTA 5610 v3.19',
    '8. Consultar configurações atuais — NUS 0x09/0x00',
    '9. Consultar identificação do produto — NUS 0x20/0x00',
    '10. Escutar notificações passivas por 30 s — sem TX',
    '11. Gerar relatório runtime — local',
    'GeneralUtils.requsetSettingInfo()',
    'GeneralUtils.requestProductIdentification()',
    'RUNTIME SETTINGS RX',
    'RUNTIME PRODUCT RX',
    'CAPTURA PASSIVA concluída',
    'RELATÓRIO RUNTIME G28 v3.19',
]
for marker in required:
    if marker not in src:
        raise SystemExit('missing v3.19 marker: ' + marker)

path.write_text(src, encoding='utf-8')
print('v3.19 runtime capability survey patch applied')
