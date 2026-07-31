from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: patch_v315_protocol_handshake.py <MainActivity.java>')

path = Path(sys.argv[1])
src = path.read_text(encoding='utf-8')

src = src.replace('Orbis Watch OTA 5610 v3.14', 'Orbis Watch OTA 5610 v3.15')
src = src.replace('Transporte 18A8 confirmado; consulta 0x01 usando WRITE_NR',
                  'Transporte 18A8 confirmado; handshake oficial 0x0F usando WRITE_NR')

old_connect_guard = '''        if (gattConnectInProgress && targetAddress.equalsIgnoreCase(gattConnectingAddress)) {
            append("CONEXÃO IGNORADA: já existe connectGatt em andamento para " + targetAddress);
            return;
        }
        disconnectGattOnly();
'''
new_connect_guard = '''        if (gattConnectInProgress && targetAddress.equalsIgnoreCase(gattConnectingAddress)) {
            append("CONEXÃO IGNORADA: já existe connectGatt em andamento para " + targetAddress);
            return;
        }
        if (gatt != null && targetAddress.equalsIgnoreCase(safeAddress(gatt.getDevice()))) {
            append("CONEXÃO IGNORADA: já conectado ao dispositivo " + targetAddress);
            return;
        }
        disconnectGattOnly();
'''
if old_connect_guard not in src:
    raise SystemExit('v3.15 connection guard anchor missing')
src = src.replace(old_connect_guard, new_connect_guard, 1)

old_button = '''        Button inspectBootloader = button("4. Consultar bootloader — somente 0x01 via WRITE_NR");
'''
new_button = '''        Button inspectBootloader = button("4. Negociar protocolo — somente 0x0F via WRITE_NR");
'''
if old_button not in src:
    raise SystemExit('v3.15 button anchor missing')
src = src.replace(old_button, new_button, 1)

old_confirm = '''        new AlertDialog.Builder(this)
                .setTitle("Consultar informações OTA com 0x01?")
                .setMessage("Será enviado somente o quadro oficial D6/0x01 por WRITE_NO_RESPONSE, como exige o "
                        + "transporte 18A8 observado. O comando 0x0F ficará bloqueado até analisarmos a resposta. "
                        + "Não serão enviados tabela, blocos, checksum final ou reboot.")
                .setNegativeButton("Cancelar", null)
                .setPositiveButton("ENVIAR 0x01", (dialog, which) -> runOtaInspection())
                .show();
'''
new_confirm = '''        new AlertDialog.Builder(this)
                .setTitle("Executar handshake oficial 0x0F?")
                .setMessage("A implementação extraída do HryFine envia D6/0x0F com payload 10 00 logo após "
                        + "conectar ao bootloader, antes de consultar 0x01. Será enviado somente esse quadro por "
                        + "WRITE_NO_RESPONSE. O 0x01 continuará bloqueado até analisarmos a resposta. "
                        + "Não serão enviados tabela, blocos, checksum final ou reboot.")
                .setNegativeButton("Cancelar", null)
                .setPositiveButton("ENVIAR 0x0F", (dialog, which) -> runOtaInspection())
                .show();
'''
if old_confirm not in src:
    raise SystemExit('v3.15 confirmation anchor missing')
src = src.replace(old_confirm, new_confirm, 1)

old_run = '''        cancelPendingTasks();
        experimentRunning = true;
        otaProbeAwaitingResponse = true;
        append("BOOTLOADER INSPEÇÃO v3.14: somente consulta oficial 0x01 por WRITE_NR; 0x0F permanece bloqueado.");
        sendOtaInfoProbe();
        schedule(5_000, () -> {
            experimentRunning = false;
            if (otaProbeAwaitingResponse) {
                append("BOOTLOADER 0x01: janela de resposta encerrada sem RX D6 registrado.");
            }
            append("BOOTLOADER INSPEÇÃO concluída; nenhum outro comando foi enviado.");
        });
'''
new_run = '''        cancelPendingTasks();
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
if old_run not in src:
    raise SystemExit('v3.15 run sequence anchor missing')
src = src.replace(old_run, new_run, 1)

old_protocol_log = '''        append("OTA PROBE protocolo: " + hex(frame));
'''
new_protocol_log = '''        append("OTA HANDSHAKE protocolo 0x0F: " + hex(frame));
'''
if old_protocol_log not in src:
    raise SystemExit('v3.15 protocol log anchor missing')
src = src.replace(old_protocol_log, new_protocol_log, 1)

old_timeout_message = '''                        append("BOOT 18A8 WRITE_NR callback status=" + status
                                + "; nenhum segundo comando será enviado. Aguardando RX ou desconexão.");
'''
new_timeout_message = '''                        append("BOOT 18A8 WRITE_NR callback status=" + status
                                + "; nenhum segundo comando será enviado. Aguardando RX do handshake ou desconexão.");
'''
if old_timeout_message not in src:
    raise SystemExit('v3.15 callback message anchor missing')
src = src.replace(old_timeout_message, new_timeout_message, 1)

src = src.replace('''                        "Como o servidor autenticou mas não publicou BIN, a v3.11 permite entrar no bootloader " +
                        "mediante confirmação explícita. Ela lista o GATT e envia somente 0x0F e 0x01. " +
                        "Nenhuma tabela ou dado de firmware será transmitido.",
''', '''                        "Como o servidor autenticou mas não publicou BIN, o laboratório permite entrar no bootloader " +
                        "mediante confirmação explícita. A v3.15 envia somente o handshake oficial 0x0F após nova confirmação. " +
                        "Nenhuma tabela ou dado de firmware será transmitido.",
''', 1)

src = src.replace('''                "reconectar ao mesmo MAC ou ao MAC com o último byte XOR 0x55. O teste termina ao encontrar " +
                        "o serviço OTA oficial e executar as consultas 0x0F/0x01; tabela de partições e BIN permanecem bloqueados.",
''', '''                "reconectar ao mesmo MAC ou ao MAC com o último byte XOR 0x55. Ao encontrar o transporte 18A8, " +
                        "somente o handshake 0x0F poderá ser enviado manualmente; 0x01, partições e BIN permanecem bloqueados.",
''', 1)

required = [
    'Orbis Watch OTA 5610 v3.15',
    'somente 0x0F via WRITE_NR',
    'A implementação extraída do HryFine envia D6/0x0F',
    'BOOTLOADER HANDSHAKE v3.15',
    '0x01 permanece bloqueado',
    'OTA HANDSHAKE protocolo 0x0F',
    'já conectado ao dispositivo',
]
for marker in required:
    if marker not in src:
        raise SystemExit('missing v3.15 marker: ' + marker)

path.write_text(src, encoding='utf-8')
print('v3.15 protocol-handshake patch applied')
