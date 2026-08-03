from pathlib import Path

root = Path('android/OrbisG28V19App')
java = root / 'app/src/main/java/com/orbisg28siliconcensus/ActiveLabActivity.java'
main = root / 'app/src/main/java/com/orbisg28siliconcensus/MainActivity.java'
gradle = root / 'app/build.gradle'

text = java.read_text(encoding='utf-8')

# Deliberately diagnostic: write a 4 KiB all-zero pattern, whose unsigned-byte
# total is unambiguously zero, and stop before D5/0x0E.
old_rescue = '''        allOrNothingPartId = 0x09;
        allOrNothingAddress = 0x003F0000L;
        allOrNothingActive = true;
        allOrNothingFinalize = true;'''
new_rescue = '''        allOrNothingPartId = 0x09;
        allOrNothingAddress = 0x003F0000L;
        allOrNothingActive = true;
        allOrNothingFinalize = false;'''
if old_rescue not in text:
    raise SystemExit('bootloader rescue anchor missing')
text = text.replace(old_rescue, new_rescue, 1)

marker_start = text.index('    private void prepareAllOrNothingMarker() {')
marker_end = text.index('\n    private void advanceAllOrNothing', marker_start)
new_marker = '''    private void prepareAllOrNothingMarker() {
        byte[] marker = new byte[4096];
        java.util.Arrays.fill(marker, (byte) 0x00);
        firmwareParts.clear();
        FirmwarePart part = new FirmwarePart();
        part.name = "orbis_g28_zero_flash_diagnostic_4k.bin";
        part.mapping = allOrNothingPartId;
        part.address = allOrNothingAddress;
        part.length = marker.length;
        part.data = marker;
        firmwareParts.add(part);
        renderPackage();
        append("ZERO-FLASH DIAGNÓSTICO PREPARADO bytes=4096 sum=0x00000000 sha256=" + sha256(marker));
        append("HIPÓTESE: se D6/0x0A aceitar zero, a v1.8 falhou por ausência de erase/estado prévio da NOR; se rejeitar, endereço/partição não é gravável ou está protegido.");
    }
'''
text = text[:marker_start] + new_marker + text[marker_end:]

old_error = '''        if (status != 1 && !official4kCallback) {
            stopTransfer("Relógio respondeu erro cmd=0x" + String.format(Locale.US, "%02X", command) + " status=" + status + " " + otaStatus(status));
            return;
        }'''
new_error = '''        if (status != 1 && !official4kCallback) {
            if (transferStage == TransferStage.WAIT_TOTAL_ACK && command == 0x0A && status == 3) {
                append("RESULTADO ZERO-FLASH: checksum total zero REJEITADO. O problema não é a fórmula; 0x003F0000 não refletiu 4096 bytes zero após a escrita. Suspeitas: área protegida, endereço inválido para part_id 0x09 ou gravação sem erase/commit.");
            }
            stopTransfer("Relógio respondeu erro cmd=0x" + String.format(Locale.US, "%02X", command) + " status=" + status + " " + otaStatus(status));
            return;
        }'''
if old_error not in text:
    raise SystemExit('transfer error anchor missing')
text = text.replace(old_error, new_error, 1)

replacements = {
    'ORBIS G28 LAB — RESGATE v1.8': 'ORBIS G28 LAB — DIAGNÓSTICO ZERO v1.9',
    'RESGATE v1.8:': 'RESGATE v1.9:',
    'callback GATT WRITE_NR v1.8': 'callback GATT WRITE_NR v1.9',
    'preset bloqueado: part_id=0x09 (FUN_DIAL_AREA) address=0x003F0000 length=4096 finalize_0x0E=true':
        'preset diagnóstico: part_id=0x09 (FUN_DIAL_AREA) address=0x003F0000 length=4096 padrão=ZERO finalize_0x0E=false',
    'CORREÇÃO v1.8: comando de dados 0x09 FUN_DIAL_AREA; WRITE_NR avança somente por callback GATT status=0.':
        'DIAGNÓSTICO v1.9: escreve 4096 bytes 0x00, checksum total esperado=0 e NÃO envia 0x0E.',
}
for old, new in replacements.items():
    if old not in text:
        raise SystemExit(f'missing text anchor: {old}')
    text = text.replace(old, new)
java.write_text(text, encoding='utf-8')

m = main.read_text(encoding='utf-8')
old_main = 'v1.8 — comando oficial de mostrador e fila por callback GATT'
if old_main not in m:
    raise SystemExit('MainActivity version anchor missing')
m = m.replace(old_main, 'v1.9 — diagnóstico zero para separar checksum de erase/endereço')
main.write_text(m, encoding='utf-8')

g = gradle.read_text(encoding='utf-8')
if 'versionCode 180' not in g or "versionName '1.8-valid-dial-command'" not in g:
    raise SystemExit('Gradle version anchors missing')
g = g.replace('versionCode 180', 'versionCode 190')
g = g.replace("versionName '1.8-valid-dial-command'", "versionName '1.9-zero-flash-diagnostic'")
gradle.write_text(g, encoding='utf-8')
