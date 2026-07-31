from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: patch_v316_official_d5_handshake.py <MainActivity.java>')

path = Path(sys.argv[1])
src = path.read_text(encoding='utf-8')

src = src.replace('Orbis Watch OTA 5610 v3.15', 'Orbis Watch OTA 5610 v3.16')
src = src.replace('Transporte 18A8 confirmado; handshake oficial 0x0F usando WRITE_NR',
                  'Transporte 18A8 confirmado; requisição oficial D5/0x0F usando WRITE_NR')
src = src.replace('Button inspectBootloader = button("4. Negociar protocolo — somente 0x0F via WRITE_NR");',
                  'Button inspectBootloader = button("4. Negociar protocolo — D5/0x0F via WRITE_NR");')

old_confirm = '''        new AlertDialog.Builder(this)
                .setTitle("Executar handshake oficial 0x0F?")
                .setMessage("A implementação extraída do HryFine envia D6/0x0F com payload 10 00 logo após "
                        + "conectar ao bootloader, antes de consultar 0x01. Será enviado somente esse quadro por "
                        + "WRITE_NO_RESPONSE. O 0x01 continuará bloqueado até analisarmos a resposta. "
                        + "Não serão enviados tabela, blocos, checksum final ou reboot.")
                .setNegativeButton("Cancelar", null)
                .setPositiveButton("ENVIAR 0x0F", (dialog, which) -> runOtaInspection())
                .show();
'''
new_confirm = '''        new AlertDialog.Builder(this)
                .setTitle("Executar requisição oficial D5/0x0F?")
                .setMessage("A extração do HryFine confirma que o telefone transmite requisições com cabeçalho D5, "
                        + "checksum de 16 bits e comprimento de 16 bits; o bootloader responde com D6. "
                        + "Será enviado somente D5/0x0F com payload 10 00 por WRITE_NO_RESPONSE. "
                        + "O 0x01, tabela, blocos, checksum final e reboot continuarão bloqueados.")
                .setNegativeButton("Cancelar", null)
                .setPositiveButton("ENVIAR D5/0x0F", (dialog, which) -> runOtaInspection())
                .show();
'''
if old_confirm not in src:
    raise SystemExit('v3.16 confirmation anchor missing')
src = src.replace(old_confirm, new_confirm, 1)

old_run = '''        cancelPendingTasks();
        experimentRunning = true;
        otaProbeAwaitingResponse = true;
        append("BOOTLOADER HANDSHAKE v3.15: somente comando oficial 0x0F/payload 10 00 por WRITE_NR; 0x01 permanece bloqueado.");
        sendOtaProtocolProbe();
        schedule(8_000, () -> {
            experimentRunning = false;
            if (otaProbeAwaitingResponse) {
                append("BOOTLOADER 0x0F: janela de resposta encerrada sem RX registrado.");
            }
            append("BOOTLOADER HANDSHAKE concluído; nenhum outro comando foi enviado.");
        });
'''
new_run = '''        cancelPendingTasks();
        experimentRunning = true;
        otaProbeAwaitingResponse = true;
        append("BOOTLOADER HANDSHAKE v3.16: requisição oficial D5/0x0F, payload 10 00, checksum 16-bit e WRITE_NR; 0x01 permanece bloqueado.");
        sendOtaProtocolProbe();
        schedule(10_000, () -> {
            experimentRunning = false;
            if (otaProbeAwaitingResponse) {
                append("BOOTLOADER D5/0x0F: janela de resposta encerrada sem RX D6 registrado.");
            }
            append("BOOTLOADER HANDSHAKE concluído; nenhum outro comando foi enviado.");
        });
'''
if old_run not in src:
    raise SystemExit('v3.16 run sequence anchor missing')
src = src.replace(old_run, new_run, 1)

old_protocol = '''    private void sendOtaProtocolProbe() {
        if (!ensureOtaReady("protocolo OTA")) return;
        byte[] frame = buildOta5610(0x0F, 1, 0, 0, new byte[]{0x10, 0x00});
        append("OTA HANDSHAKE protocolo 0x0F: " + hex(frame));
        enqueueOtaBatch(Collections.singletonList(frame), null);
    }
'''
new_protocol = '''    private void sendOtaProtocolProbe() {
        if (!ensureOtaReady("protocolo OTA")) return;
        byte[] frame = buildOfficial5610Request(0x0F, 1, 0, 0, new byte[]{0x10, 0x00});
        otaRxBuffer = new byte[0];
        otaExpectedLength = 0;
        int checksum = ((frame[7] & 0xFF) << 8) | (frame[8] & 0xFF);
        append(String.format(Locale.US,
                "OTA HANDSHAKE requisição D5/0x0F checksum=0x%04X len=%d: %s",
                checksum, frame.length, hex(frame)));
        enqueueOtaBatch(Collections.singletonList(frame), null);
    }
'''
if old_protocol not in src:
    raise SystemExit('v3.16 protocol method anchor missing')
src = src.replace(old_protocol, new_protocol, 1)

src = src.replace('A v3.15 envia somente o handshake oficial 0x0F após nova confirmação.',
                  'A v3.16 envia somente a requisição oficial D5/0x0F após nova confirmação.')
src = src.replace('somente o handshake 0x0F poderá ser enviado manualmente; 0x01, partições e BIN permanecem bloqueados.',
                  'somente a requisição D5/0x0F poderá ser enviada manualmente; 0x01, partições e BIN permanecem bloqueados.')

required = [
    'Orbis Watch OTA 5610 v3.16',
    'D5/0x0F via WRITE_NR',
    'BOOTLOADER HANDSHAKE v3.16',
    'buildOfficial5610Request(0x0F',
    'OTA HANDSHAKE requisição D5/0x0F',
    'checksum 16-bit',
    'sem RX D6 registrado',
]
for marker in required:
    if marker not in src:
        raise SystemExit('missing v3.16 marker: ' + marker)

if 'byte[] frame = buildOta5610(0x0F' in src:
    raise SystemExit('legacy D6 request builder still used for 0x0F')

path.write_text(src, encoding='utf-8')
print('v3.16 official D5 handshake patch applied')
