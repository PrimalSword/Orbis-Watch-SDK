from pathlib import Path
import re, sys

if len(sys.argv) != 2:
    raise SystemExit('usage: patch_v311_bootloader_entry.py <MainActivity.java>')
p=Path(sys.argv[1]); s=p.read_text(encoding='utf-8')

repls={
'Orbis Watch OTA 5610 v3.10':'Orbis Watch OTA 5610 v3.11',
'Transição oficial NUS para o modo OTA 5610 do G28':'Entrada controlada no bootloader OTA 5610 do G28',
'e esta versão não transmite tabela, BIN ou blocos de firmware.':'e esta versão entra no bootloader, mas continua sem transmitir tabela, BIN ou blocos de firmware.',
'o serviço OTA oficial; tabela de partições e BIN permanecem bloqueados.':'o serviço OTA oficial e executar as consultas 0x0F/0x01; tabela de partições e BIN permanecem bloqueados.',
'Firmware: BLOQUEADO — teste somente de transição para OTA':'Firmware: BLOQUEADO — bootloader e consultas somente leitura',
}
for a,b in repls.items():
    if a not in s: raise SystemExit('missing text: '+a)
    s=s.replace(a,b,1)

s=s.replace('    private boolean otaReconnectInProgress;\n','    private boolean otaReconnectInProgress;\n    private boolean otaBootInspectionScheduled;\n',1)
s=s.replace('                negotiatedMtu = 23;\n                otaNotificationsReady = false;\n','                negotiatedMtu = 23;\n                otaNotificationsReady = false;\n                otaBootInspectionScheduled = false;\n',1)

old='''                append("TRANSIÇÃO OTA: candidato reencontrado " + address + " nome=" + name
                        + " RSSI=" + result.getRssi());
'''
new=old+'''                if (result.getScanRecord() != null) append("TRANSIÇÃO OTA ADV RAW: " + hex(result.getScanRecord().getBytes()));
'''
if old not in s: raise SystemExit('scan block missing')
s=s.replace(old,new,1)

old='''                setStatus("MODO OTA 5610 CONFIRMADO — serviço 6e40ff01 encontrado");
                append("TRANSIÇÃO CONCLUÍDA: serviço oficial OTA 5610, write e notify encontrados.");
                notifyQueue.clear();
'''
new='''                setStatus("MODO OTA 5610 CONFIRMADO — serviço 6e40ff01 encontrado");
                append("TRANSIÇÃO CONCLUÍDA: serviço oficial OTA 5610, write e notify encontrados.");
                append("BOOTLOADER: listando GATT antes de qualquer comando de inspeção.");
                dumpGatt();
                notifyQueue.clear();
'''
if old not in s: raise SystemExit('service block missing')
s=s.replace(old,new,1)

old='''            if (otaNotify != null && otaNotify.getUuid().equals(characteristicUuid)
                    && status == BluetoothGatt.GATT_SUCCESS) {
                otaNotificationsReady = true;
                renderOtaStatus();
            }
'''
new='''            if (otaNotify != null && otaNotify.getUuid().equals(characteristicUuid)
                    && status == BluetoothGatt.GATT_SUCCESS) {
                otaNotificationsReady = true;
                append("BOOTLOADER: notify OTA confirmado. Inspeção 0x0F/0x01 será executada automaticamente.");
                if (!otaBootInspectionScheduled) {
                    otaBootInspectionScheduled = true;
                    schedule(450, MainActivity.this::runOtaInspection);
                }
                renderOtaStatus();
            }
'''
if old not in s: raise SystemExit('descriptor block missing')
s=s.replace(old,new,1)

old='''        TextView transitionNote = text(
                "Fluxo reconstruído do HryFine: primeiro requestOTAInfo no NUS; depois consulta ao servidor; " +
                        "somente então requestStartOTA no NUS. Esta versão apenas tenta colocar o G28 no modo OTA " +
                        "e confirmar o serviço 6e40ff01. Nenhum firmware será gravado.",
                12, false);
'''
new='''        TextView transitionNote = text(
                "Fluxo reconstruído do HryFine: requestOTAInfo no NUS e requestStartOTA 0x13/0x02. " +
                        "Como o servidor autenticou mas não publicou BIN, a v3.11 permite entrar no bootloader " +
                        "mediante confirmação explícita. Ela lista o GATT e envia somente 0x0F e 0x01. " +
                        "Nenhuma tabela ou dado de firmware será transmitido.",
                12, false);
'''
if old not in s: raise SystemExit('transition note missing')
s=s.replace(old,new,1)

anchor='''        content.addView(startOtaMode, marginLayout(0, 2, 0, 3));

'''
insert=anchor+'''        Button inspectBootloader = button("4. Inspecionar bootloader agora — 0x0F/0x01");
        inspectBootloader.setOnClickListener(v -> runOtaInspection());
        content.addView(inspectBootloader, marginLayout(0, 2, 0, 3));

'''
if anchor not in s: raise SystemExit('button anchor missing')
s=s.replace(anchor,insert,1)

pattern=re.compile(r'    private void confirmNusStartOta\(\) \{.*?\n    \}\n\n    private void sendNusStartOta',re.S)
m=pattern.search(s)
if not m: raise SystemExit('confirm method missing')
method='''    private void confirmNusStartOta() {
        if (!ensureNusSession("solicitar o modo OTA")) return;
        if (!nusOtaInfoValidated) {
            toast("Primeiro execute o passo 1 e aguarde OTA INFO NUS validado=true");
            return;
        }
        if (officialUpdateAvailable) {
            new AlertDialog.Builder(this)
                    .setTitle("Colocar o G28 no modo OTA?")
                    .setMessage("Será enviado GeneralUtils.requestStartOTA() 0x13/0x02. Nenhum firmware será gravado.")
                    .setNegativeButton("Cancelar", null)
                    .setPositiveButton("INICIAR TRANSIÇÃO", (d, w) -> sendNusStartOta())
                    .show();
            return;
        }
        final EditText confirmation = new EditText(this);
        confirmation.setHint("Digite: ENTRAR OTA G28");
        confirmation.setSingleLine(true);
        confirmation.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_FLAG_CAP_CHARACTERS);
        new AlertDialog.Builder(this)
                .setTitle("Entrar no bootloader sem pacote oficial?")
                .setMessage("O comando 0x13/0x02 pode deixar o relógio no bootloader ou exigir recuperação manual. " +
                        "A v3.11 não envia tabela nem firmware. Digite a frase exata para assumir o risco.")
                .setView(confirmation)
                .setNegativeButton("Cancelar", null)
                .setPositiveButton("ASSUMIR E ENTRAR", (d, w) -> {
                    if ("ENTRAR OTA G28".equals(confirmation.getText().toString().trim())) {
                        append("RISCO ACEITO: entrada no bootloader autorizada sem bin_list oficial.");
                        sendNusStartOta();
                    } else {
                        append("ENTRADA OTA CANCELADA: frase incorreta.");
                        toast("Frase incorreta; nenhum comando foi enviado");
                    }
                }).show();
    }

    private void sendNusStartOta'''
s=s[:m.start()]+method+s[m.end():]

pattern=re.compile(r'    private void runOtaInspection\(\) \{.*?\n    \}\n\n    private void sendOtaProtocolProbe',re.S)
m=pattern.search(s)
if not m: raise SystemExit('inspection method missing')
method='''    private void runOtaInspection() {
        if (!ensureOtaReady("inspeção do bootloader")) return;
        if (experimentRunning) { toast("Já existe teste em execução"); return; }
        cancelPendingTasks();
        experimentRunning = true;
        append("BOOTLOADER INSPEÇÃO: somente consultas oficiais 0x0F e 0x01; nenhuma tabela ou escrita de firmware.");
        sendOtaProtocolProbe();
        schedule(1_300, this::sendOtaInfoProbe);
        schedule(3_200, () -> {
            experimentRunning = false;
            append("BOOTLOADER INSPEÇÃO concluída; aguardando ação do operador.");
        });
    }

    private void sendOtaProtocolProbe'''
s=s[:m.start()]+method+s[m.end():]

s=s.replace('        otaReconnectInProgress = false;\n        cancelPendingTasks();\n','        otaReconnectInProgress = false;\n        otaBootInspectionScheduled = false;\n        cancelPendingTasks();\n',1)
s=s.replace('                    otaReconnectInProgress = false;\n                    setStatus("Rearmado — procure e conecte o G28");\n','                    otaReconnectInProgress = false;\n                    otaBootInspectionScheduled = false;\n                    setStatus("Rearmado — procure e conecte o G28");\n',1)

for marker in ('Orbis Watch OTA 5610 v3.11','ENTRAR OTA G28','TRANSIÇÃO OTA ADV RAW','BOOTLOADER INSPEÇÃO: somente consultas oficiais 0x0F e 0x01'):
    if marker not in s: raise SystemExit('missing marker: '+marker)
if 'START OTA BLOQUEADO: bin_list oficial ainda não foi confirmado.' in s: raise SystemExit('legacy gate remains')
p.write_text(s,encoding='utf-8')
print('v3.11 bootloader-entry patch applied')
