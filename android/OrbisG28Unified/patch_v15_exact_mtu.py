from pathlib import Path
import sys
root = Path(sys.argv[1])
java = root/'app/src/main/java/com/orbisg28siliconcensus/ActiveLabActivity.java'
main = root/'app/src/main/java/com/orbisg28siliconcensus/MainActivity.java'
gradle = root/'app/build.gradle'
s = java.read_text()
repls = {
    'ORBIS G28 LAB — RESGATE v1.4':'ORBIS G28 LAB — RESGATE v1.5',
    'CORREÇÃO v1.4: WRITE_NR serial temporizado; D6 válido confirma o quadro e callbacks GATT status=1 são informativos.':'CORREÇÃO v1.5: payload 5610 usa exatamente MTU-14; WRITE_NR serial; D6 válido confirma o quadro.',
    'WRITE_NR serial temporizado v1.4':'WRITE_NR serial temporizado v1.5',
    'RESGATE v1.4:':'RESGATE v1.5:',
    'temporizador serial v1.4':'temporizador serial v1.5',
    'return Math.max(1, Math.min(240, negotiatedMtu - 14));':'return Math.max(1, negotiatedMtu - 14);',
}
for a,b in repls.items():
    if a not in s:
        raise SystemExit(f'missing in ActiveLabActivity: {a!r}')
    s=s.replace(a,b)
needle='append("TRANSFER START CONFIRMADO mode=" + mode + " parts=" + firmwareParts.size());'
insert=needle+'\n        append("PAYLOAD 5610 OFICIAL: MTU-14=" + otaPayloadSize() + " bytes; frame máximo=" + otaGattValueLimit());'
if needle not in s:
    raise SystemExit('missing transfer start needle')
s=s.replace(needle,insert,1)
java.write_text(s)
m=main.read_text()
if 'v1.4 — resgate ACK-aware do G28 preso no bootloader .02' not in m:
    raise SystemExit('missing main version string')
m=m.replace('v1.4 — resgate ACK-aware do G28 preso no bootloader .02','v1.5 — resgate com fragmentação oficial MTU−14')
main.write_text(m)
g=gradle.read_text()
if 'versionCode 140' not in g or "versionName '1.4-ack-aware-rescue'" not in g:
    raise SystemExit('missing gradle version')
g=g.replace('versionCode 140','versionCode 150').replace("versionName '1.4-ack-aware-rescue'", "versionName '1.5-exact-mtu-minus-14'")
gradle.write_text(g)
