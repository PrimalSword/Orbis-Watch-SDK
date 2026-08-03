from pathlib import Path

root = Path('android/OrbisG28V18App')
java = root / 'app/src/main/java/com/orbisg28siliconcensus/ActiveLabActivity.java'
main = root / 'app/src/main/java/com/orbisg28siliconcensus/MainActivity.java'
gradle = root / 'app/build.gradle'
text = java.read_text(encoding='utf-8')

replacements = {
    'private int allOrNothingPartId = 0x7E;': 'private int allOrNothingPartId = 0x09;',
    'ORBIS G28 LAB — RESGATE v1.7': 'ORBIS G28 LAB — RESGATE v1.8',
    'part_id 0x7E': 'part_id 0x09 (área oficial de mostrador)',
    'partição 0x7E em 0x003F0000': 'partição 0x09 (mostrador) em 0x003F0000',
    'allOrNothingPartId = 0x7E;': 'allOrNothingPartId = 0x09;',
    'preset bloqueado: part_id=0x7E address=0x003F0000 length=4096 finalize_0x0E=true': 'preset bloqueado: part_id=0x09 (FUN_DIAL_AREA) address=0x003F0000 length=4096 finalize_0x0E=true',
    'CORREÇÃO v1.7: semântica oficial do callback 4K; status raw 0x07 não interrompe a fila D5/0x0A.': 'CORREÇÃO v1.8: comando de dados 0x09 FUN_DIAL_AREA; WRITE_NR avança somente por callback GATT status=0.',
    'ORBIS_G28_BT8918C_FLASH_PROBE_V1': 'ORBIS_G28_DIAL_AREA_FLASH_PROBE_V2',
    'RESGATE v1.7:': 'RESGATE v1.8:',
    'WRITE_NR serial temporizado v1.7': 'watchdog WRITE_NR v1.8',
}
for old, new in replacements.items():
    if old not in text:
        raise SystemExit(f'missing replacement anchor: {old}')
    text = text.replace(old, new)

old_callback = '''                if (otaLastWriteNoResponse) {
                    append("OTA WRITE_NR callback informativo ignorado status=" + status
                            + "; conclusão será feita por D6 correspondente ou pelo temporizador serial v1.6");
                    return;
                }'''
new_callback = '''                if (otaLastWriteNoResponse) {
                    if (status == BluetoothGatt.GATT_SUCCESS) {
                        otaWriteToken++;
                        otaWriteBusy = false;
                        completeOtaWriteSuccess("callback GATT WRITE_NR v1.8");
                    } else {
                        TxItem pending = otaInFlight;
                        if (pending != null && isFlashDataFrame(pending.data)) {
                            otaWriteToken++;
                            otaWriteBusy = false;
                            retryOrStopOtaWrite("callback WRITE_NR de dados status=" + status);
                        } else {
                            append("OTA WRITE_NR controle status=" + status
                                    + "; aguardando D6 correspondente antes de repetir.");
                        }
                    }
                    return;
                }'''
if old_callback not in text:
    raise SystemExit('onCharacteristicWrite anchor missing')
text = text.replace(old_callback, new_callback, 1)

old_timer = '''            if (otaLastWriteNoResponse) {
                schedule(140, () -> {
                    if (otaWriteBusy && otaWriteToken == writeToken) {
                        otaWriteToken++;
                        otaWriteBusy = false;
                        completeOtaWriteSuccess("watchdog WRITE_NR v1.8");
                    }
                });
            } else {'''
new_timer = '''            if (otaLastWriteNoResponse) {
                schedule(3_500, () -> {
                    if (otaWriteBusy && otaWriteToken == writeToken) {
                        otaWriteBusy = false;
                        retryOrStopOtaWrite("timeout aguardando callback WRITE_NR status=0");
                    }
                });
            } else {'''
if old_timer not in text:
    raise SystemExit('WRITE_NR timer anchor missing')
text = text.replace(old_timer, new_timer, 1)
java.write_text(text, encoding='utf-8')

m = main.read_text(encoding='utf-8')
old_main = 'v1.7 — resgate com callback 4K idêntico ao HryFine'
if old_main not in m:
    raise SystemExit('MainActivity version anchor missing')
m = m.replace(old_main, 'v1.8 — comando oficial de mostrador e fila por callback GATT')
main.write_text(m, encoding='utf-8')

g = gradle.read_text(encoding='utf-8')
if 'versionCode 170' not in g or "versionName '1.7-official-4k-callback'" not in g:
    raise SystemExit('Gradle version anchors missing')
g = g.replace('versionCode 170', 'versionCode 180')
g = g.replace("versionName '1.7-official-4k-callback'", "versionName '1.8-valid-dial-command'")
gradle.write_text(g, encoding='utf-8')
