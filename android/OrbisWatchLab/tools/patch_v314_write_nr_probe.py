from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: patch_v314_write_nr_probe.py <MainActivity.java>')

path = Path(sys.argv[1])
src = path.read_text(encoding='utf-8')

src = src.replace('Orbis Watch OTA 5610 v3.13', 'Orbis Watch OTA 5610 v3.14')
src = src.replace('Transporte 18A8/2AA8/2AA9 confirmado e inspeção controlada',
                  'Transporte 18A8 confirmado; consulta 0x01 usando WRITE_NR')

old_fields = '''    private boolean otaObserved18a8Transport;
    private boolean gattConnectInProgress;
'''
new_fields = '''    private boolean otaObserved18a8Transport;
    private boolean otaLastWriteNoResponse;
    private boolean otaProbeAwaitingResponse;
    private boolean gattConnectInProgress;
'''
if old_fields not in src:
    raise SystemExit('v3.14 field anchor missing')
src = src.replace(old_fields, new_fields, 1)

old_button = '''        Button inspectBootloader = button("4. Inspecionar bootloader agora — 0x0F/0x01");
'''
new_button = '''        Button inspectBootloader = button("4. Consultar bootloader — somente 0x01 via WRITE_NR");
'''
if old_button not in src:
    raise SystemExit('v3.14 button anchor missing')
src = src.replace(old_button, new_button, 1)

old_confirm = '''        new AlertDialog.Builder(this)
                .setTitle("Executar consultas OTA 0x01 e 0x0F?")
                .setMessage("Serão enviados somente dois quadros oficiais de consulta no transporte confirmado. "
                        + "Não serão enviados tabela, blocos, checksum final ou reboot.")
                .setNegativeButton("Cancelar", null)
                .setPositiveButton("CONSULTAR", (dialog, which) -> runOtaInspection())
                .show();
'''
new_confirm = '''        new AlertDialog.Builder(this)
                .setTitle("Consultar informações OTA com 0x01?")
                .setMessage("Será enviado somente o quadro oficial D6/0x01 por WRITE_NO_RESPONSE, como exige o "
                        + "transporte 18A8 observado. O comando 0x0F ficará bloqueado até analisarmos a resposta. "
                        + "Não serão enviados tabela, blocos, checksum final ou reboot.")
                .setNegativeButton("Cancelar", null)
                .setPositiveButton("ENVIAR 0x01", (dialog, which) -> runOtaInspection())
                .show();
'''
if old_confirm not in src:
    raise SystemExit('v3.14 confirm dialog anchor missing')
src = src.replace(old_confirm, new_confirm, 1)

old_run = '''        cancelPendingTasks();
        experimentRunning = true;
        append("BOOTLOADER INSPEÇÃO: consultas oficiais 0x01 e 0x0F, nesta ordem; nenhum dado de firmware.");
        sendOtaInfoProbe();
        schedule(1_300, this::sendOtaProtocolProbe);
        schedule(3_200, () -> {
            experimentRunning = false;
            append("BOOTLOADER INSPEÇÃO concluída; aguardando ação do operador.");
        });
'''
new_run = '''        cancelPendingTasks();
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
if old_run not in src:
    raise SystemExit('v3.14 inspection sequence anchor missing')
src = src.replace(old_run, new_run, 1)

old_write_type = '''            int writeType = (c.getProperties() & BluetoothGattCharacteristic.PROPERTY_WRITE) != 0
                    ? BluetoothGattCharacteristic.WRITE_TYPE_DEFAULT
                    : BluetoothGattCharacteristic.WRITE_TYPE_NO_RESPONSE;
            if (Build.VERSION.SDK_INT >= 33) {
                int result = currentGatt.writeCharacteristic(c, item.data, writeType);
                append("OTA write solicitado result=" + result);
                if (result != BluetoothGatt.GATT_SUCCESS) otaWriteBusy = false;
'''
new_write_type = '''            boolean forceWriteNoResponse = otaObserved18a8Transport;
            int writeType = forceWriteNoResponse
                    ? BluetoothGattCharacteristic.WRITE_TYPE_NO_RESPONSE
                    : ((c.getProperties() & BluetoothGattCharacteristic.PROPERTY_WRITE) != 0
                    ? BluetoothGattCharacteristic.WRITE_TYPE_DEFAULT
                    : BluetoothGattCharacteristic.WRITE_TYPE_NO_RESPONSE);
            otaLastWriteNoResponse = writeType == BluetoothGattCharacteristic.WRITE_TYPE_NO_RESPONSE;
            append("OTA write type=" + (otaLastWriteNoResponse ? "WRITE_NR" : "WRITE_DEFAULT")
                    + " transport18A8=" + otaObserved18a8Transport);
            if (Build.VERSION.SDK_INT >= 33) {
                int result = currentGatt.writeCharacteristic(c, item.data, writeType);
                append("OTA write solicitado result=" + result);
                if (result != BluetoothGatt.GATT_SUCCESS) otaWriteBusy = false;
                else if (otaLastWriteNoResponse) {
                    schedule(140, () -> {
                        if (otaWriteBusy && otaWriteToken == writeToken) {
                            append("WRITE_NR aceito pela pilha Android; liberando fila sem aguardar ACK GATT.");
                            otaWriteToken++;
                            otaWriteBusy = false;
                            pumpOtaQueue();
                        }
                    });
                }
'''
if old_write_type not in src:
    raise SystemExit('v3.14 write-type anchor missing')
src = src.replace(old_write_type, new_write_type, 1)

old_callback = '''                if (status != BluetoothGatt.GATT_SUCCESS) {
                    stopTransfer("Falha de escrita OTA status=" + status);
                    otaTxQueue.clear();
                    return;
                }
'''
new_callback = '''                if (status != BluetoothGatt.GATT_SUCCESS) {
                    if (otaObserved18a8Transport && otaLastWriteNoResponse && otaProbeAwaitingResponse) {
                        append("BOOT 18A8 WRITE_NR callback status=" + status
                                + "; nenhum segundo comando será enviado. Aguardando RX ou desconexão.");
                        otaTxQueue.clear();
                        return;
                    }
                    stopTransfer("Falha de escrita OTA status=" + status);
                    otaTxQueue.clear();
                    return;
                }
'''
if old_callback not in src:
    raise SystemExit('v3.14 write callback anchor missing')
src = src.replace(old_callback, new_callback, 1)

old_direct = '''        if (directOta) {
            if (copy.length > 0 && ((copy[0] & 0xFF) == 0xD6 || otaRxBuffer.length > 0)) {
                consumeOtaNotification(copy);
'''
new_direct = '''        if (directOta) {
            if (copy.length > 0) otaProbeAwaitingResponse = false;
            if (copy.length > 0 && ((copy[0] & 0xFF) == 0xD6 || otaRxBuffer.length > 0)) {
                consumeOtaNotification(copy);
'''
if old_direct not in src:
    raise SystemExit('v3.14 direct OTA notification anchor missing')
src = src.replace(old_direct, new_direct, 1)

old_clear = '''        otaWrite = null;
        otaNotify = null;
        otaObserved18a8Transport = false;
'''
new_clear = '''        otaWrite = null;
        otaNotify = null;
        otaObserved18a8Transport = false;
        otaLastWriteNoResponse = false;
        otaProbeAwaitingResponse = false;
'''
if old_clear not in src:
    raise SystemExit('v3.14 clear anchor missing')
src = src.replace(old_clear, new_clear, 1)

required = [
    'Orbis Watch OTA 5610 v3.14',
    'somente 0x01 via WRITE_NR',
    'forceWriteNoResponse',
    'OTA write type=',
    'WRITE_NR aceito pela pilha Android',
    '0x0F permanece bloqueado',
    'nenhum segundo comando será enviado',
]
for marker in required:
    if marker not in src:
        raise SystemExit('missing v3.14 marker: ' + marker)

path.write_text(src, encoding='utf-8')
print('v3.14 WRITE_NR single-probe patch applied')
