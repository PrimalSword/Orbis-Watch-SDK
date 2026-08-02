#!/usr/bin/env python3
from pathlib import Path
import sys

root = Path(sys.argv[1])
active = root / 'app/src/main/java/com/orbisg28siliconcensus/ActiveLabActivity.java'
main = root / 'app/src/main/java/com/orbisg28siliconcensus/MainActivity.java'
gradle = root / 'app/build.gradle'

s = active.read_text(encoding='utf-8')
repls = []

repls.append((
'''        public void onCharacteristicWrite(BluetoothGatt currentGatt, BluetoothGattCharacteristic characteristic, int status) {
            append("Write concluído " + characteristic.getUuid() + " status=" + status);
            if (otaWrite != null && otaWrite.getUuid().equals(characteristic.getUuid())) {
                otaWriteToken++;
                otaWriteBusy = false;
                if (status != BluetoothGatt.GATT_SUCCESS) {
                    retryOrStopOtaWrite("callback GATT status=" + status);
                    return;
                }
                completeOtaWriteSuccess("callback GATT");
            }
        }
''',
'''        public void onCharacteristicWrite(BluetoothGatt currentGatt, BluetoothGattCharacteristic characteristic, int status) {
            append("Write concluído " + characteristic.getUuid() + " status=" + status);
            if (otaWrite != null && otaWrite.getUuid().equals(characteristic.getUuid())) {
                if (otaLastWriteNoResponse) {
                    append("OTA WRITE_NR callback informativo ignorado status=" + status
                            + "; conclusão será feita por D6 correspondente ou pelo temporizador serial v1.4");
                    return;
                }
                otaWriteToken++;
                otaWriteBusy = false;
                if (status != BluetoothGatt.GATT_SUCCESS) {
                    retryOrStopOtaWrite("callback GATT status=" + status);
                    return;
                }
                completeOtaWriteSuccess("callback GATT");
            }
        }
'''))

repls.append((
'''        append(String.format(Locale.US,
                "  ↳ OTA D6 cmd=0x%02X ver=%d status=%d(%s) block=%d frag=%d len=%d payload=%s",
                command, version, status, otaStatus(status), block, fragment, length, hex(payload)));

        if (command == 0x0F && status == 1) {
''',
'''        append(String.format(Locale.US,
                "  ↳ OTA D6 cmd=0x%02X ver=%d status=%d(%s) block=%d frag=%d len=%d payload=%s",
                command, version, status, otaStatus(status), block, fragment, length, hex(payload)));

        if (status == 1) completeMatchingOtaWriteFromD6(command);

        if (command == 0x0F && status == 1) {
'''))

repls.append((
'''        if (command == 0x0F && status == 1) {
            parityStyle = true;
            otaBootProtocolVersion = new String(payload, StandardCharsets.UTF_8).trim();
            otaProtocolNegotiated = "V1.1".equals(otaBootProtocolVersion);
            append("OTA protocolo/versão: " + otaBootProtocolVersion
                    + " | parityStyle=true | negociado=" + otaProtocolNegotiated);
            if (allOrNothingActive) schedule(250, () -> advanceAllOrNothing("OTA_HANDSHAKE"));
        } else if (command == 0x01 && status == 1) {
''',
'''        if (command == 0x0F && status == 1) {
            boolean firstValidHandshake = !otaProtocolNegotiated;
            parityStyle = true;
            otaBootProtocolVersion = new String(payload, StandardCharsets.UTF_8).trim();
            otaProtocolNegotiated = "V1.1".equals(otaBootProtocolVersion);
            append("OTA protocolo/versão: " + otaBootProtocolVersion
                    + " | parityStyle=true | negociado=" + otaProtocolNegotiated);
            if (allOrNothingActive && firstValidHandshake && otaProtocolNegotiated) {
                append("RESGATE v1.4: D6/0x0F válido encerrou o handshake; respostas duplicadas serão ignoradas.");
                schedule(250, () -> advanceAllOrNothing("OTA_HANDSHAKE"));
            }
        } else if (command == 0x01 && status == 1) {
'''))

repls.append((
'''                if (allOrNothingActive) {
                    allOrNothingBootIdentityConfirmed = true;
                    append("TUDO OU NADA GATE: identidade D6/0x01 do bootloader validada.");
                    schedule(250, () -> advanceAllOrNothing("OTA_IDENTITY"));
                }
''',
'''                if (allOrNothingActive && !allOrNothingBootIdentityConfirmed) {
                    allOrNothingBootIdentityConfirmed = true;
                    append("TUDO OU NADA GATE: identidade D6/0x01 do bootloader validada.");
                    append("RESGATE v1.4: D6/0x01 válido encerrou a identidade; respostas duplicadas serão ignoradas.");
                    schedule(250, () -> advanceAllOrNothing("OTA_IDENTITY"));
                }
'''))

repls.append((
'''            int properties = c.getProperties();
            int writeType = (properties & BluetoothGattCharacteristic.PROPERTY_WRITE) != 0
                    ? BluetoothGattCharacteristic.WRITE_TYPE_DEFAULT
                    : BluetoothGattCharacteristic.WRITE_TYPE_NO_RESPONSE;
            otaLastWriteNoResponse = writeType == BluetoothGattCharacteristic.WRITE_TYPE_NO_RESPONSE;
            if (shouldLogOtaFrame(item.data)) {
                append("OTA write type=" + (otaLastWriteNoResponse ? "WRITE_NR_FALLBACK" : "WRITE_DEFAULT")
                        + " len=" + item.data.length + "/" + otaGattValueLimit());
            }
''',
'''            int properties = c.getProperties();
            int writeType = BluetoothGattCharacteristic.WRITE_TYPE_NO_RESPONSE;
            otaLastWriteNoResponse = true;
            if (shouldLogOtaFrame(item.data)) {
                append("OTA write type=WRITE_NR_SERIAL_V14"
                        + " len=" + item.data.length + "/" + otaGattValueLimit()
                        + " props=0x" + Integer.toHexString(properties).toUpperCase(Locale.US));
            }
'''))

repls.append((
'''            if (otaLastWriteNoResponse) {
                schedule(120, () -> {
                    if (otaWriteBusy && otaWriteToken == writeToken) {
                        otaWriteToken++;
                        otaWriteBusy = false;
                        completeOtaWriteSuccess("fallback WRITE_NR temporizado");
                    }
                });
''',
'''            if (otaLastWriteNoResponse) {
                schedule(140, () -> {
                    if (otaWriteBusy && otaWriteToken == writeToken) {
                        otaWriteToken++;
                        otaWriteBusy = false;
                        completeOtaWriteSuccess("WRITE_NR serial temporizado v1.4");
                    }
                });
'''))

repls.append((
'''    private void completeOtaWriteSuccess(String source) {
''',
'''    private void completeMatchingOtaWriteFromD6(int responseCommand) {
        TxItem completed = otaInFlight;
        if (completed == null || completed.data == null || completed.data.length < 2) return;
        int requestCommand = completed.data[1] & 0xFF;
        if (requestCommand != responseCommand) return;
        otaWriteToken++;
        otaWriteBusy = false;
        if (!otaTxQueue.isEmpty() && otaTxQueue.peekFirst() == completed) otaTxQueue.removeFirst();
        otaInFlight = null;
        otaInFlightAttempts = 0;
        transferSentFrames++;
        append("RESGATE v1.4: D6/0x" + String.format(Locale.US, "%02X", responseCommand)
                + " confirmou o quadro em voo; callback GATT tardio será ignorado.");
        renderTransferStatus();
        if (otaTxQueue.isEmpty()) {
            Runnable done = otaBatchCompletion;
            otaBatchCompletion = null;
            if (done != null) done.run();
        } else {
            schedule(35, this::pumpOtaQueue);
        }
    }

    private void completeOtaWriteSuccess(String source) {
'''))

repls.append((
'''        schedule(20, this::pumpOtaQueue);
''',
'''        schedule(35, this::pumpOtaQueue);
'''))

repls.append((
'''        TextView title = text("ORBIS G28 LAB — RESGATE v1.3", 27, true);
''',
'''        TextView title = text("ORBIS G28 LAB — RESGATE v1.4", 27, true);
'''))

repls.append((
'''        append("CORREÇÃO v1.3: MTU solicitado=256, payload=MTU-14, frame<=MTU-3, WRITE_DEFAULT serial.");
''',
'''        append("CORREÇÃO v1.4: WRITE_NR serial temporizado; D6 válido confirma o quadro e callbacks GATT status=1 são informativos.");
'''))

for old, new in repls:
    count = s.count(old)
    if count != 1:
        raise SystemExit(f'Expected exactly one match, found {count}: {old[:140]!r}')
    s = s.replace(old, new)

active.write_text(s, encoding='utf-8')

m = main.read_text(encoding='utf-8')
old = '"v1.3 — resgate do G28 preso no bootloader .02",'
new = '"v1.4 — resgate ACK-aware do G28 preso no bootloader .02",'
if m.count(old) != 1:
    raise SystemExit('MainActivity version label not found exactly once')
main.write_text(m.replace(old, new), encoding='utf-8')

g = gradle.read_text(encoding='utf-8')
if g.count('versionCode 130') != 1 or g.count("versionName '1.3-bootloader-rescue'") != 1:
    raise SystemExit('Gradle version markers not found')
g = g.replace('versionCode 130', 'versionCode 140')
g = g.replace("versionName '1.3-bootloader-rescue'", "versionName '1.4-ack-aware-rescue'")
gradle.write_text(g, encoding='utf-8')

print('Applied Orbis G28 Lab v1.4 ACK-aware rescue patch')
