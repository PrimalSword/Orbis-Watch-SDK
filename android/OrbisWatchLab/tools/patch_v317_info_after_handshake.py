from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: patch_v317_info_after_handshake.py <MainActivity.java>')

path = Path(sys.argv[1])
src = path.read_text(encoding='utf-8')

src = src.replace('Orbis Watch OTA 5610 v3.16', 'Orbis Watch OTA 5610 v3.17')
src = src.replace('Transporte 18A8 confirmado; requisição oficial D5/0x0F usando WRITE_NR',
                  'Transporte 18A8 confirmado; handshake D5/0x0F e identidade D5/0x01')

old_fields = '''    private boolean otaProbeAwaitingResponse;
    private boolean gattConnectInProgress;
'''
new_fields = '''    private boolean otaProbeAwaitingResponse;
    private boolean otaProtocolNegotiated;
    private String otaBootProtocolVersion = "";
    private boolean gattConnectInProgress;
'''
if old_fields not in src:
    raise SystemExit('v3.17 field anchor missing')
src = src.replace(old_fields, new_fields, 1)

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

old_parser = '''        if (command == 0x0F && status == 1) {
            parityStyle = true;
            otaVersion = new String(payload, StandardCharsets.UTF_8).trim();
            append("OTA protocolo/versão: " + otaVersion + " | parityStyle=true");
        } else if (command == 0x01 && status == 1) {
            parseOtaInfoPayload(payload);
        }
'''
new_parser = '''        if (command == 0x0F && status == 1) {
            parityStyle = true;
            otaBootProtocolVersion = new String(payload, StandardCharsets.UTF_8).trim();
            otaProtocolNegotiated = "V1.1".equals(otaBootProtocolVersion);
            append("OTA protocolo/versão: " + otaBootProtocolVersion
                    + " | parityStyle=true | negociado=" + otaProtocolNegotiated);
        } else if (command == 0x01 && status == 1) {
            parseOtaInfoPayload(payload);
            append("OTA IDENTIDADE RX → versão=" + otaVersion
                    + " projeto=" + otaProject + " unique_code=" + otaUniqueCode);
            if ("V1.5".equals(otaVersion) && "G28".equals(otaProject)) {
                append("IDENTIDADE OTA CONFIRMADA: G28 V1.5. Próxima etapa continuará somente leitura.");
            }
        }
'''
if old_parser not in src:
    raise SystemExit('v3.17 D6 parser anchor missing')
src = src.replace(old_parser, new_parser, 1)

old_disconnect = '''        otaBootInspectionScheduled = false;
        cancelPendingTasks();
'''
new_disconnect = '''        otaBootInspectionScheduled = false;
        otaProtocolNegotiated = false;
        otaBootProtocolVersion = "";
        cancelPendingTasks();
'''
if old_disconnect not in src:
    raise SystemExit('v3.17 disconnect reset anchor missing')
src = src.replace(old_disconnect, new_disconnect, 1)

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
