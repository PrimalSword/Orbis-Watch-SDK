from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: patch_v313_observed_transport.py <MainActivity.java>')

path = Path(sys.argv[1])
src = path.read_text(encoding='utf-8')

src = src.replace('Orbis Watch OTA 5610 v3.12', 'Orbis Watch OTA 5610 v3.13')
src = src.replace('Descoberta resiliente do bootloader e inspeção somente leitura',
                  'Transporte 18A8/2AA8/2AA9 confirmado e inspeção controlada')

old_constants = '''    private static final UUID OTA_NOTIFY_5610_UUID = uuid("6e40ff03-b5a3-f393-e0a9-e50e24dcca9e");

    // Proprietary channels actually exposed by this G28 in normal mode.
'''
new_constants = '''    private static final UUID OTA_NOTIFY_5610_UUID = uuid("6e40ff03-b5a3-f393-e0a9-e50e24dcca9e");

    // Transport observed on this G28 after the XOR55/5610 bootloader transition.
    private static final UUID BOOT_SERVICE_18A8_UUID = uuid("000018a8-0000-1000-8000-00805f9b34fb");
    private static final UUID BOOT_NOTIFY_2AA8_UUID = uuid("00002aa8-0000-1000-8000-00805f9b34fb");
    private static final UUID BOOT_WRITE_2AA9_UUID = uuid("00002aa9-0000-1000-8000-00805f9b34fb");

    // Proprietary channels actually exposed by this G28 in normal mode.
'''
if old_constants not in src:
    raise SystemExit('constant anchor missing')
src = src.replace(old_constants, new_constants, 1)

old_fields = '''    private int otaServiceDiscoveryRetries;
    private boolean otaBootCandidateConnected;
    private String otaOriginalAddress = "";
'''
new_fields = '''    private int otaServiceDiscoveryRetries;
    private boolean otaBootCandidateConnected;
    private boolean otaObserved18a8Transport;
    private boolean gattConnectInProgress;
    private String gattConnectingAddress = "";
    private String otaOriginalAddress = "";
'''
if old_fields not in src:
    raise SystemExit('field anchor missing')
src = src.replace(old_fields, new_fields, 1)

old_state = '''            append("Conexão GATT status=" + status + " state=" + newState);
            if (newState == BluetoothProfile.STATE_CONNECTED) {
                gatt = currentGatt;
'''
new_state = '''            append("Conexão GATT status=" + status + " state=" + newState);
            if (newState == BluetoothProfile.STATE_CONNECTED) {
                gattConnectInProgress = false;
                gattConnectingAddress = "";
                gatt = currentGatt;
'''
if old_state not in src:
    raise SystemExit('connection state anchor missing')
src = src.replace(old_state, new_state, 1)

old_disconnect = '''            } else if (newState == BluetoothProfile.STATE_DISCONNECTED) {
                if (status == 19) {
'''
new_disconnect = '''            } else if (newState == BluetoothProfile.STATE_DISCONNECTED) {
                gattConnectInProgress = false;
                gattConnectingAddress = "";
                if (status == 19) {
'''
if old_disconnect not in src:
    raise SystemExit('disconnect anchor missing')
src = src.replace(old_disconnect, new_disconnect, 1)

old_connect = '''        stopScan();
        disconnectGattOnly();
        setStatus("Conectando a " + safeName(selectedDevice) + "...");
        append("Conectando a " + safeAddress(selectedDevice));
        gatt = Build.VERSION.SDK_INT >= 23
                ? selectedDevice.connectGatt(this, false, gattCallback, BluetoothDevice.TRANSPORT_LE)
                : selectedDevice.connectGatt(this, false, gattCallback);
'''
new_connect = '''        stopScan();
        String targetAddress = safeAddress(selectedDevice);
        if (gattConnectInProgress && targetAddress.equalsIgnoreCase(gattConnectingAddress)) {
            append("CONEXÃO IGNORADA: já existe connectGatt em andamento para " + targetAddress);
            return;
        }
        disconnectGattOnly();
        gattConnectInProgress = true;
        gattConnectingAddress = targetAddress;
        setStatus("Conectando a " + safeName(selectedDevice) + "...");
        append("Conectando a " + targetAddress);
        gatt = Build.VERSION.SDK_INT >= 23
                ? selectedDevice.connectGatt(this, false, gattCallback, BluetoothDevice.TRANSPORT_LE)
                : selectedDevice.connectGatt(this, false, gattCallback);
        if (gatt == null) {
            gattConnectInProgress = false;
            gattConnectingAddress = "";
            append("connectGatt retornou null para " + targetAddress);
        }
'''
if old_connect not in src:
    raise SystemExit('connect block missing')
src = src.replace(old_connect, new_connect, 1)

old_discover_start = '''    private void discoverCharacteristics(BluetoothGatt currentGatt) {
        clearCharacteristics();
        for (BluetoothGattService service : currentGatt.getServices()) {
'''
new_discover_start = '''    private void discoverCharacteristics(BluetoothGatt currentGatt) {
        clearCharacteristics();
        BluetoothGattCharacteristic observed18a8Write = null;
        BluetoothGattCharacteristic observed18a8Notify = null;
        for (BluetoothGattService service : currentGatt.getServices()) {
'''
if old_discover_start not in src:
    raise SystemExit('discover start missing')
src = src.replace(old_discover_start, new_discover_start, 1)

old_map = '''                if (OTA_WRITE_5610_UUID.equals(u)) otaWrite = c;
                if (OTA_NOTIFY_5610_UUID.equals(u)) otaNotify = c;
                if (WRITE_FF13_UUID.equals(u)) ff13Write = c;
'''
new_map = '''                if (OTA_WRITE_5610_UUID.equals(u)) otaWrite = c;
                if (OTA_NOTIFY_5610_UUID.equals(u)) otaNotify = c;
                if (BOOT_WRITE_2AA9_UUID.equals(u)) observed18a8Write = c;
                if (BOOT_NOTIFY_2AA8_UUID.equals(u)) observed18a8Notify = c;
                if (WRITE_FF13_UUID.equals(u)) ff13Write = c;
'''
if old_map not in src:
    raise SystemExit('characteristic mapping missing')
src = src.replace(old_map, new_map, 1)

old_after_loop = '''        }
        append("NUS write=" + uuidOf(nusWrite) + " notify=" + uuidOf(nusNotify));
        append("OTA5610 service=" + (currentGatt.getService(OTA_SERVICE_5610_UUID) != null)
'''
new_after_loop = '''        }
        otaObserved18a8Transport = currentGatt.getService(BOOT_SERVICE_18A8_UUID) != null
                && observed18a8Write != null && observed18a8Notify != null;
        if (otaWrite == null && otaObserved18a8Transport) otaWrite = observed18a8Write;
        if (otaNotify == null && otaObserved18a8Transport) otaNotify = observed18a8Notify;
        append("NUS write=" + uuidOf(nusWrite) + " notify=" + uuidOf(nusNotify));
        append("OTA5610 service=" + (currentGatt.getService(OTA_SERVICE_5610_UUID) != null)
'''
if old_after_loop not in src:
    raise SystemExit('after loop anchor missing')
src = src.replace(old_after_loop, new_after_loop, 1)

old_logs = '''        append("CANDIDATO FF10 service=" + (currentGatt.getService(SERVICE_FF10_UUID) != null)
                + " write-only=" + uuidOf(fff1Write));
    }
'''
new_logs = '''        append("CANDIDATO FF10 service=" + (currentGatt.getService(SERVICE_FF10_UUID) != null)
                + " write-only=" + uuidOf(fff1Write));
        append("BOOT 18A8 service=" + otaObserved18a8Transport
                + " write=" + (observed18a8Write == null ? "-" : observed18a8Write.getUuid())
                + " read/notify=" + (observed18a8Notify == null ? "-" : observed18a8Notify.getUuid()));
        if (otaObserved18a8Transport) {
            append("BOOTLOADER TRANSPORTE CONFIRMADO: 18A8 / RX 2AA8 / TX 2AA9.");
        }
    }
'''
if old_logs not in src:
    raise SystemExit('discover logs anchor missing')
src = src.replace(old_logs, new_logs, 1)

old_service_gate = '''            if (otaWrite != null && otaNotify != null
                    && currentGatt.getService(OTA_SERVICE_5610_UUID) != null) {
                otaTransitionScanArmed = false;
                otaReconnectInProgress = false;
                otaStartRequested = false;
                setStatus("MODO OTA 5610 CONFIRMADO — serviço 6e40ff01 encontrado");
                append("TRANSIÇÃO CONCLUÍDA: serviço oficial OTA 5610, write e notify encontrados.");
                append("BOOTLOADER: listando GATT antes de qualquer comando de inspeção.");
                dumpGatt();
                notifyQueue.clear();
                notifyQueue.add(otaNotify);
                configureNextNotification();
                return;
            }
'''
new_service_gate = '''            boolean legacy6e40Transport = otaWrite != null && otaNotify != null
                    && currentGatt.getService(OTA_SERVICE_5610_UUID) != null;
            if (legacy6e40Transport || otaObserved18a8Transport) {
                otaTransitionScanArmed = false;
                otaReconnectInProgress = false;
                otaStartRequested = false;
                String transport = otaObserved18a8Transport ? "18A8/2AA8/2AA9" : "6e40ff01/02/03";
                setStatus("MODO OTA 5610 CONFIRMADO — transporte " + transport);
                append("TRANSIÇÃO CONCLUÍDA: transporte OTA confirmado em " + transport + ".");
                append("BOOTLOADER: listando GATT e ativando somente RX/notify; nenhum probe será automático.");
                dumpGatt();
                notifyQueue.clear();
                notifyQueue.add(otaNotify);
                configureNextNotification();
                return;
            }
'''
if old_service_gate not in src:
    raise SystemExit('service gate missing')
src = src.replace(old_service_gate, new_service_gate, 1)

old_descriptor = '''            if (otaNotify != null && otaNotify.getUuid().equals(characteristicUuid)
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
new_descriptor = '''            if (otaNotify != null && otaNotify.getUuid().equals(characteristicUuid)
                    && status == BluetoothGatt.GATT_SUCCESS) {
                otaNotificationsReady = true;
                append("BOOTLOADER: RX/notify confirmado. Nenhum comando será enviado automaticamente.");
                if (otaObserved18a8Transport) {
                    schedule(350, () -> readCandidate(otaNotify, "BOOT 2AA8 leitura inicial"));
                }
                renderOtaStatus();
            }
'''
if old_descriptor not in src:
    raise SystemExit('descriptor OTA block missing')
src = src.replace(old_descriptor, new_descriptor, 1)

old_button = '''        inspectBootloader.setOnClickListener(v -> runOtaInspection());
'''
new_button = '''        inspectBootloader.setOnClickListener(v -> confirmOtaInspection());
'''
if old_button not in src:
    raise SystemExit('inspection button missing')
src = src.replace(old_button, new_button, 1)

old_dump = '''            for (BluetoothGattCharacteristic c : service.getCharacteristics()) {
                append("  CHAR " + c.getUuid() + " props=" + properties(c.getProperties()));
            }
'''
new_dump = '''            for (BluetoothGattCharacteristic c : service.getCharacteristics()) {
                append("  CHAR " + c.getUuid() + " props=" + properties(c.getProperties()));
                for (BluetoothGattDescriptor descriptor : c.getDescriptors()) {
                    append("    DESC " + descriptor.getUuid());
                }
            }
'''
if old_dump not in src:
    raise SystemExit('dump GATT block missing')
src = src.replace(old_dump, new_dump, 1)

inspection_anchor = '''    private void runOtaInspection() {
'''
confirm_method = '''    private void confirmOtaInspection() {
        if (!ensureOtaReady("inspeção do bootloader")) return;
        new AlertDialog.Builder(this)
                .setTitle("Executar consultas OTA 0x01 e 0x0F?")
                .setMessage("Serão enviados somente dois quadros oficiais de consulta no transporte confirmado. "
                        + "Não serão enviados tabela, blocos, checksum final ou reboot.")
                .setNegativeButton("Cancelar", null)
                .setPositiveButton("CONSULTAR", (dialog, which) -> runOtaInspection())
                .show();
    }

'''
if inspection_anchor not in src:
    raise SystemExit('inspection method anchor missing')
src = src.replace(inspection_anchor, confirm_method + inspection_anchor, 1)

old_inspection = '''        append("BOOTLOADER INSPEÇÃO: somente consultas oficiais 0x0F e 0x01; nenhuma tabela ou escrita de firmware.");
        sendOtaProtocolProbe();
        schedule(1_300, this::sendOtaInfoProbe);
'''
new_inspection = '''        append("BOOTLOADER INSPEÇÃO: consultas oficiais 0x01 e 0x0F, nesta ordem; nenhum dado de firmware.");
        sendOtaInfoProbe();
        schedule(1_300, this::sendOtaProtocolProbe);
'''
if old_inspection not in src:
    raise SystemExit('inspection sequence missing')
src = src.replace(old_inspection, new_inspection, 1)

old_clear = '''        otaWrite = null;
        otaNotify = null;
'''
new_clear = '''        otaWrite = null;
        otaNotify = null;
        otaObserved18a8Transport = false;
'''
if old_clear not in src:
    raise SystemExit('clear characteristics anchor missing')
src = src.replace(old_clear, new_clear, 1)

required = [
    'Orbis Watch OTA 5610 v3.13',
    'BOOT_SERVICE_18A8_UUID',
    'BOOT_NOTIFY_2AA8_UUID',
    'BOOT_WRITE_2AA9_UUID',
    'BOOTLOADER TRANSPORTE CONFIRMADO',
    'Nenhum comando será enviado automaticamente',
    'confirmOtaInspection',
    'consultas oficiais 0x01 e 0x0F, nesta ordem',
    'CONEXÃO IGNORADA',
]
for marker in required:
    if marker not in src:
        raise SystemExit('missing v3.13 marker: ' + marker)

path.write_text(src, encoding='utf-8')
print('v3.13 observed 18A8 transport patch applied')
