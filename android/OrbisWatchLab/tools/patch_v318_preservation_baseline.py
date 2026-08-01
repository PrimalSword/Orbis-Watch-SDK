from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: patch_v318_preservation_baseline.py <MainActivity.java>')

path = Path(sys.argv[1])
src = path.read_text(encoding='utf-8')

src = src.replace('Orbis Watch OTA 5610 v3.17', 'Orbis Watch OTA 5610 v3.18')
src = src.replace('A v3.17 permite o handshake D5/0x0F e, somente após V1.1, a consulta D5/0x01.',
                  'A v3.18 acrescenta um baseline somente leitura e um passaporte de recuperação; handshake e identidade continuam manuais.')

old_queues = '''    private final ArrayDeque<BluetoothGattCharacteristic> notifyQueue = new ArrayDeque<>();
    private final ArrayDeque<TxItem> otaTxQueue = new ArrayDeque<>();
    private final List<FirmwarePart> firmwareParts = new ArrayList<>();
'''
new_queues = '''    private final ArrayDeque<BluetoothGattCharacteristic> notifyQueue = new ArrayDeque<>();
    private final ArrayDeque<TxItem> otaTxQueue = new ArrayDeque<>();
    private final ArrayDeque<BluetoothGattCharacteristic> preservationReadQueue = new ArrayDeque<>();
    private final List<String> preservationReadValues = new ArrayList<>();
    private final List<FirmwarePart> firmwareParts = new ArrayList<>();
'''
if old_queues not in src:
    raise SystemExit('v3.18 queue anchor missing')
src = src.replace(old_queues, new_queues, 1)

old_fields = '''    private String otaUniqueCode = "";
    private String otaVersion = "";
    private String otaProject = "";

    private TransferMode transferMode = TransferMode.NONE;
'''
new_fields = '''    private String otaUniqueCode = "";
    private String otaVersion = "";
    private String otaProject = "";
    private BluetoothGattCharacteristic preservationActiveRead;
    private boolean preservationReadRunning;
    private int preservationReadTotal;
    private int preservationReadSuccess;
    private String preservationNormalAddress = "";
    private String preservationBootAddress = "";

    private TransferMode transferMode = TransferMode.NONE;
'''
if old_fields not in src:
    raise SystemExit('v3.18 field anchor missing')
src = src.replace(old_fields, new_fields, 1)

old_gatt_button = '''        Button gattDump = button("Listar todos os serviços e characteristics");
        gattDump.setOnClickListener(v -> dumpGatt());
        content.addView(gattDump, marginLayout(0, 2, 0, 2));

        Button notifyNus = button("Ativar somente notificações NUS (manual)");
'''
new_gatt_button = '''        Button gattDump = button("Listar todos os serviços e characteristics");
        gattDump.setOnClickListener(v -> dumpGatt());
        content.addView(gattDump, marginLayout(0, 2, 0, 2));

        Button preservationBaseline = button("0. Capturar baseline do relógio/BLE — somente leitura");
        preservationBaseline.setOnClickListener(v -> startPreservationBaseline());
        content.addView(preservationBaseline, marginLayout(0, 2, 0, 2));

        Button notifyNus = button("Ativar somente notificações NUS (manual)");
'''
if old_gatt_button not in src:
    raise SystemExit('v3.18 baseline button anchor missing')
src = src.replace(old_gatt_button, new_gatt_button, 1)

old_identity_button = '''        Button queryOtaIdentity = button("5. Consultar identidade OTA — D5/0x01");
        queryOtaIdentity.setOnClickListener(v -> confirmOtaIdentity());
        content.addView(queryOtaIdentity, marginLayout(0, 2, 0, 3));

        Button scanTransition = button("Buscar novamente o G28/OTA agora");
'''
new_identity_button = '''        Button queryOtaIdentity = button("5. Consultar identidade OTA — D5/0x01");
        queryOtaIdentity.setOnClickListener(v -> confirmOtaIdentity());
        content.addView(queryOtaIdentity, marginLayout(0, 2, 0, 3));

        Button recoveryPassport = button("6. Gerar passaporte de recuperação — local");
        recoveryPassport.setOnClickListener(v -> appendRecoveryPassport("SOLICITADO PELO OPERADOR"));
        content.addView(recoveryPassport, marginLayout(0, 2, 0, 3));

        Button protocolMap = button("7. Mostrar próxima etapa OTA — sem transmitir");
        protocolMap.setOnClickListener(v -> logOfficialProtocolMap());
        content.addView(protocolMap, marginLayout(0, 2, 0, 3));

        Button scanTransition = button("Buscar novamente o G28/OTA agora");
'''
if old_identity_button not in src:
    raise SystemExit('v3.18 recovery button anchor missing')
src = src.replace(old_identity_button, new_identity_button, 1)

method_anchor = '''    private void confirmOtaInspection() {
'''
methods = r'''    private void startPreservationBaseline() {
        if (emergencyStopped) {
            toast("Emergência ativa");
            return;
        }
        if (gatt == null || !hasConnectPermission()) {
            toast("Conecte primeiro ao G28 em modo normal");
            return;
        }
        if (otaObserved18a8Transport || otaBootCandidateConnected) {
            toast("O baseline deve ser capturado no firmware normal, antes do bootloader");
            append("BASELINE BLOQUEADO: conexão atual é do bootloader OTA.");
            return;
        }
        if (preservationReadRunning) {
            toast("Baseline já está em execução");
            return;
        }

        preservationReadQueue.clear();
        preservationReadValues.clear();
        preservationReadTotal = 0;
        preservationReadSuccess = 0;
        preservationActiveRead = null;
        preservationNormalAddress = safeAddress(gatt.getDevice());
        preservationBootAddress = xor55Address(preservationNormalAddress);

        append("===== BASELINE DE PRESERVAÇÃO G28 v3.18 =====");
        append("NORMAL MAC=" + preservationNormalAddress + " | OTA XOR55=" + preservationBootAddress);
        append("Objetivo: registrar serviços e valores legíveis sem alterar o relógio.");
        for (BluetoothGattService service : gatt.getServices()) {
            append("BASELINE SERVICE " + service.getUuid());
            for (BluetoothGattCharacteristic characteristic : service.getCharacteristics()) {
                int properties = characteristic.getProperties();
                append("  BASELINE CHAR " + characteristic.getUuid() + " props=" + properties(properties));
                if ((properties & BluetoothGattCharacteristic.PROPERTY_READ) != 0) {
                    preservationReadQueue.add(characteristic);
                }
            }
        }
        preservationReadTotal = preservationReadQueue.size();
        preservationReadRunning = true;
        append("BASELINE: characteristics legíveis enfileiradas=" + preservationReadTotal);
        readNextPreservationCharacteristic();
    }

    private void readNextPreservationCharacteristic() {
        if (!preservationReadRunning) return;
        if (gatt == null || !hasConnectPermission()) {
            append("BASELINE interrompido: GATT indisponível.");
            finishPreservationBaseline();
            return;
        }
        BluetoothGattCharacteristic next = preservationReadQueue.poll();
        if (next == null) {
            finishPreservationBaseline();
            return;
        }
        preservationActiveRead = next;
        try {
            boolean queued = gatt.readCharacteristic(next);
            append("BASELINE READ solicitado " + next.getUuid() + " queued=" + queued);
            if (!queued) {
                preservationActiveRead = null;
                schedule(120, this::readNextPreservationCharacteristic);
            }
        } catch (Exception error) {
            append("BASELINE READ falhou " + next.getUuid() + ": " + error.getMessage());
            preservationActiveRead = null;
            schedule(120, this::readNextPreservationCharacteristic);
        }
    }

    private void finishPreservationBaseline() {
        boolean wasRunning = preservationReadRunning;
        preservationReadRunning = false;
        preservationActiveRead = null;
        preservationReadQueue.clear();
        if (wasRunning) {
            append("BASELINE concluído: leituras com sucesso=" + preservationReadSuccess
                    + "/" + preservationReadTotal + ". Nenhuma characteristic foi escrita.");
            appendRecoveryPassport("BASELINE NORMAL CONCLUÍDO");
        }
    }

    private void appendRecoveryPassport(String origin) {
        if (gatt != null) {
            String address = safeAddress(gatt.getDevice());
            if (otaObserved18a8Transport || otaBootCandidateConnected) {
                preservationBootAddress = address;
                if (preservationNormalAddress.isEmpty()) preservationNormalAddress = xor55Address(address);
            } else {
                preservationNormalAddress = address;
                preservationBootAddress = xor55Address(address);
            }
        }
        if (preservationNormalAddress.isEmpty() && !otaOriginalAddress.isEmpty()) {
            preservationNormalAddress = otaOriginalAddress;
        }
        if (preservationBootAddress.isEmpty() && !preservationNormalAddress.isEmpty()) {
            preservationBootAddress = xor55Address(preservationNormalAddress);
        }

        append("===== PASSAPORTE DE RECUPERAÇÃO G28 =====");
        append("origem=" + origin);
        append("normal_mac=" + emptyAsDash(preservationNormalAddress));
        append("bootloader_mac=" + emptyAsDash(preservationBootAddress));
        append("runtime_transport=NUS 6E400001/2/3");
        append("boot_transport=18A8 / RX 2AA8 / TX 2AA9");
        append("boot_protocol=" + emptyAsDash(otaBootProtocolVersion)
                + " negociado=" + otaProtocolNegotiated + " parityStyle=" + parityStyle);
        append("firmware=" + emptyAsDash(otaVersion)
                + " projeto=" + emptyAsDash(otaProject)
                + " unique_code=" + emptyAsDash(otaUniqueCode));
        append("baseline_reads=" + preservationReadSuccess + "/" + preservationReadTotal);
        append("REQUISITOS DO FIRMWARE DOOM: relógio/RTC funcional; BLE de manutenção sempre disponível; "
                + "saída do Doom sem reflashing; caminho de recuperação preservado.");
        append("PRÓXIMA OPERAÇÃO OFICIAL=0x03 distribuição de partições — BLOQUEADA sem manifesto genuíno.");
        append("===== FIM PASSAPORTE =====");
    }

    private void logOfficialProtocolMap() {
        append("===== MAPA OTA 5610 RECUPERADO — NENHUM TX =====");
        append("D5/0x0F: negociar protocolo → confirmado V1.1.");
        append("D5/0x01: consultar identidade → confirmado G28 V1.5.");
        append("D5/0x03: distribuir tabela de partições fornecida pelo servidor → ESCRITA, BLOQUEADA.");
        append("D5/0x02: checksums por blocos de 4 KiB/40 KiB → depende do BIN, BLOQUEADO.");
        append("D5/<part_id>: dados do firmware → BLOQUEADO.");
        append("D5/0x0A: checksum total da partição → BLOQUEADO.");
        append("Conclusão: a próxima etapa segura é obter um manifesto/BIN genuíno ou reconstruir o mapa fora do relógio.");
        append("Nenhum pacote BLE foi transmitido por este botão.");
        append("===== FIM MAPA OTA =====");
    }

'''
if method_anchor not in src:
    raise SystemExit('v3.18 method insertion anchor missing')
src = src.replace(method_anchor, methods + method_anchor, 1)

old_handle = '''        if (status == BluetoothGatt.GATT_SUCCESS && copy.length > 0 && (copy[0] & 0xFF) == 0xD6) {
            append("  ↳ leitura contém cabeçalho D6; encaminhando ao parser FF01.");
            consumeCandidateNotification(copy);
        }
        if (ff14Notify != null && ff14Notify.getUuid().equals(characteristic.getUuid())
'''
new_handle = '''        if (status == BluetoothGatt.GATT_SUCCESS && copy.length > 0 && (copy[0] & 0xFF) == 0xD6) {
            append("  ↳ leitura contém cabeçalho D6; encaminhando ao parser FF01.");
            consumeCandidateNotification(copy);
        }
        if (preservationReadRunning && preservationActiveRead != null
                && preservationActiveRead.getUuid().equals(characteristic.getUuid())) {
            preservationReadValues.add(characteristic.getUuid() + "=" + hex(copy));
            if (status == BluetoothGatt.GATT_SUCCESS) preservationReadSuccess++;
            preservationActiveRead = null;
            schedule(120, this::readNextPreservationCharacteristic);
        }
        if (ff14Notify != null && ff14Notify.getUuid().equals(characteristic.getUuid())
'''
if old_handle not in src:
    raise SystemExit('v3.18 handleRead anchor missing')
src = src.replace(old_handle, new_handle, 1)

old_confirmed = '''            if ("V1.5".equals(otaVersion) && "G28".equals(otaProject)) {
                append("IDENTIDADE OTA CONFIRMADA: G28 V1.5. Próxima etapa continuará somente leitura.");
            }
'''
new_confirmed = '''            if ("V1.5".equals(otaVersion) && "G28".equals(otaProject)) {
                append("IDENTIDADE OTA CONFIRMADA: G28 V1.5. Próxima etapa continuará somente leitura.");
                appendRecoveryPassport("IDENTIDADE OTA CONFIRMADA");
            }
'''
if old_confirmed not in src:
    raise SystemExit('v3.18 identity confirmation anchor missing')
src = src.replace(old_confirmed, new_confirmed, 1)

old_clear = '''        pendingReadCharacteristic = null;
        pendingReadLabel = null;
        nusLinkValidated = false;
'''
new_clear = '''        pendingReadCharacteristic = null;
        pendingReadLabel = null;
        preservationReadRunning = false;
        preservationActiveRead = null;
        preservationReadQueue.clear();
        nusLinkValidated = false;
'''
if old_clear not in src:
    raise SystemExit('v3.18 clear anchor missing')
src = src.replace(old_clear, new_clear, 1)

src = src.replace('o handshake D5/0x0F e a identidade D5/0x01 são manuais; partições e BIN permanecem bloqueados.',
                  'o baseline, o handshake D5/0x0F e a identidade D5/0x01 são manuais; partições e BIN permanecem bloqueados.')

required = [
    'Orbis Watch OTA 5610 v3.18',
    '0. Capturar baseline do relógio/BLE — somente leitura',
    '6. Gerar passaporte de recuperação — local',
    '7. Mostrar próxima etapa OTA — sem transmitir',
    'startPreservationBaseline',
    'PASSAPORTE DE RECUPERAÇÃO G28',
    'PRÓXIMA OPERAÇÃO OFICIAL=0x03',
    'Nenhum pacote BLE foi transmitido por este botão',
    'relógio/RTC funcional; BLE de manutenção sempre disponível',
]
for marker in required:
    if marker not in src:
        raise SystemExit('missing v3.18 marker: ' + marker)

path.write_text(src, encoding='utf-8')
print('v3.18 preservation baseline patch applied')
