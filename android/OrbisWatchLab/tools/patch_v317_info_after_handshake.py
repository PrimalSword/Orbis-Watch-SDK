from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: patch_v317_info_after_handshake.py <MainActivity.java>')

path = Path(sys.argv[1])
src = path.read_text(encoding='utf-8')

src = src.replace('Orbis Watch OTA 5610 v3.16', 'Orbis Watch OTA 5610 v3.17')
src = src.replace('Transporte 18A8 confirmado; requisição oficial D5/0x0F usando WRITE_NR',
                  'Transporte 18A8 confirmado; handshake D5/0x0F e identidade D5/0x01')

src = src.replace('    private boolean otaProbeAwaitingResponse;\n',
                  '    private boolean otaProbeAwaitingResponse;\n    private boolean otaProtocolNegotiated;\n    private String otaBootProtocolVersion = "";\n', 1)

anchor = '''        Button inspectBootloader = button("4. Negociar protocolo — D5/0x0F via WRITE_NR");
        inspectBootloader.setOnClickListener(v -> confirmOtaInspection());
        content.addView(inspectBootloader, marginLayout(0, 2, 0, 3));

'''
insert = anchor + '''        Button queryOtaIdentity = button("5. Consultar identidade OTA — D5/0x01");
        queryOtaIdentity.setOnClickListener(v -> confirmOtaIdentity());
        content.addView(queryOtaIdentity, marginLayout(0, 2, 0, 3));

'''
if anchor not in src:
    raise SystemExit('v3.17 button anchor missing')
src = src.replace(anchor, insert, 1)

method_anchor = '''    private void runOtaInspection() {
'''
methods = '''    private void confirmOtaIdentity() {
        if (!ensureOtaReady("consulta de identidade OTA")) return;
        if (!otaProtocolNegotiated || !"V1.1".equals(otaBootProtocolVersion)) {
            toast("Primeiro execute o passo 4 e aguarde OTA protocolo/versão: V1.1");
            append("IDENTIDADE OTA BLOQUEADA: handshake D5/0x0F V1.1 ainda não confirmado nesta sessão.");
            return;
        }
        new AlertDialog.Builder(this)
                .setTitle("Consultar identidade OTA com D5/0x01?")
                .setMessage("Será enviado somente o comando oficial D5/0x01, sem payload, após o handshake V1.1. "
                        + "A consulta não envia tabela, dados de firmware, checksum final, finalização ou reboot. "
                        + "Nosso firmware futuro deverá preservar relógio, RTC e um canal BLE de recuperação.")
                .setNegativeButton("Cancelar", null)
                .setPositiveButton("ENVIAR D5/0x01", (dialog, which) -> runOtaIdentityQuery())
                .show();
    }

    private void runOtaIdentityQuery() {
        if (!ensureOtaReady("consulta de identidade OTA")) return;
        if (!otaProtocolNegotiated) {
            append("IDENTIDADE OTA BLOQUEADA: sessão não negociada.");
            return;
        }
        if (experimentRunning) {
            toast("Já existe teste em execução");
            return;
        }
        cancelPendingTasks();
        experimentRunning = true;
        otaProbeAwaitingResponse = true;
        otaRxBuffer = new byte[0];
        otaExpectedLength = 0;
        byte[] frame = buildOfficial5610Request(0x01, 1, 0, 0, new byte[0]);
        int checksum = ((frame[7] & 0xFF) << 8) | (frame[8] & 0xFF);
        append(String.format(Locale.US,
                "BOOTLOADER IDENTIDADE v3.17: D5/0x01 checksum=0x%04X len=%d; nenhuma escrita de firmware.",
                checksum, frame.length));
        append("OTA IDENTIDADE TX: " + hex(frame));
        enqueueOtaBatch(Collections.singletonList(frame), null);
        schedule(10_000, () -> {
            experimentRunning = false;
            if (otaProbeAwaitingResponse) {
                append("BOOTLOADER D5/0x01: janela de resposta encerrada sem RX D6 registrado.");
            }
            append("BOOTLOADER IDENTIDADE concluída; nenhuma operação posterior foi enviada.");
        });
    }

'''
if method_anchor not in src:
    raise SystemExit('v3.17 method anchor missing')
src = src.replace(method_anchor, methods + method_anchor, 1)

old_protocol = '''                    if (command == 0x0F && payloadLength > 0) {
                        String version = new String(payload, StandardCharsets.UTF_8).trim();
                        append("OTA protocolo/versão: " + version + " | parityStyle=" + otaParityStyle);
                    }
'''
new_protocol = '''                    if (command == 0x0F && payloadLength > 0) {
                        String version = new String(payload, StandardCharsets.UTF_8).trim();
                        otaBootProtocolVersion = version;
                        otaProtocolNegotiated = status == 1 && "V1.1".equals(version);
                        append("OTA protocolo/versão: " + version + " | parityStyle=" + otaParityStyle
                                + " | negociado=" + otaProtocolNegotiated);
                    }
                    if (command == 0x01 && status == 1) {
                        parseOtaIdentityPayload(payload);
                    }
'''
if old_protocol not in src:
    raise SystemExit('v3.17 D6 parser anchor missing')
src = src.replace(old_protocol, new_protocol, 1)

parser_anchor = '''    private byte[] buildOfficial5610Request(int command, int version, int blockIndex, int fragmentIndex, byte[] payload) {
'''
parser = '''    private void parseOtaIdentityPayload(byte[] payload) {
        if (payload == null || payload.length < 6) {
            append("OTA IDENTIDADE RX: payload curto=" + hex(payload == null ? new byte[0] : payload));
            return;
        }
        int p = 0;
        String uniquePrefix = "";
        if (payload.length >= 4) {
            uniquePrefix = hex(Arrays.copyOfRange(payload, 0, 4)).replace(" ", "");
            p = 4;
        }
        String version = "";
        String project = "";
        if (p < payload.length) {
            int versionLength = payload[p++] & 0xFF;
            if (versionLength <= payload.length - p) {
                version = new String(payload, p, versionLength, StandardCharsets.UTF_8);
                p += versionLength;
            }
        }
        if (p < payload.length) {
            int projectLength = payload[p++] & 0xFF;
            if (projectLength <= payload.length - p) {
                project = new String(payload, p, projectLength, StandardCharsets.UTF_8);
            }
        }
        append("OTA IDENTIDADE RX → prefixo=" + uniquePrefix
                + " versão=" + version + " projeto=" + project
                + " payload=" + hex(payload));
        if ("V1.5".equals(version) && "G28".equals(project)) {
            append("IDENTIDADE OTA CONFIRMADA: G28 V1.5. Próxima etapa continuará somente leitura.");
        }
    }

'''
if parser_anchor not in src:
    raise SystemExit('v3.17 parser insertion anchor missing')
src = src.replace(parser_anchor, parser + parser_anchor, 1)

src = src.replace('        otaBootInspectionScheduled = false;\n        cancelPendingTasks();\n',
                  '        otaBootInspectionScheduled = false;\n        otaProtocolNegotiated = false;\n        otaBootProtocolVersion = "";\n        cancelPendingTasks();\n', 1)

src = src.replace('A v3.16 envia somente a requisição oficial D5/0x0F após nova confirmação.',
                  'A v3.17 permite o handshake D5/0x0F e, somente após V1.1, a consulta D5/0x01.')
src = src.replace('somente a requisição D5/0x0F poderá ser enviada manualmente; 0x01, partições e BIN permanecem bloqueados.',
                  'o handshake D5/0x0F e a identidade D5/0x01 são manuais; partições e BIN permanecem bloqueados.')

required = [
    'Orbis Watch OTA 5610 v3.17',
    '5. Consultar identidade OTA — D5/0x01',
    'confirmOtaIdentity',
    'runOtaIdentityQuery',
    'buildOfficial5610Request(0x01',
    'IDENTIDADE OTA BLOQUEADA',
    'OTA IDENTIDADE RX',
    'IDENTIDADE OTA CONFIRMADA',
    'preservar relógio, RTC e um canal BLE de recuperação',
]
for marker in required:
    if marker not in src:
        raise SystemExit('missing v3.17 marker: ' + marker)

path.write_text(src, encoding='utf-8')
print('v3.17 identity-after-handshake patch applied')
