from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: patch_v312_resilient_discovery.py <MainActivity.java>')

path = Path(sys.argv[1])
src = path.read_text(encoding='utf-8')

src = src.replace('Orbis Watch OTA 5610 v3.11', 'Orbis Watch OTA 5610 v3.12')
src = src.replace('Entrada controlada no bootloader e inspeção somente leitura',
                  'Descoberta resiliente do bootloader e inspeção somente leitura')

old_maps = '''    private final Map<String, DeviceEntry> devices = new LinkedHashMap<>();
    private final ArrayDeque<BluetoothGattCharacteristic> notifyQueue = new ArrayDeque<>();
'''
new_maps = '''    private final Map<String, DeviceEntry> devices = new LinkedHashMap<>();
    private final Map<String, Boolean> bootloaderAdvertisements = new LinkedHashMap<>();
    private final ArrayDeque<BluetoothGattCharacteristic> notifyQueue = new ArrayDeque<>();
'''
if old_maps not in src:
    raise SystemExit('map anchor not found')
src = src.replace(old_maps, new_maps, 1)

old_fields = '''    private boolean otaBootInspectionScheduled;
    private int otaTransitionAttempts;
    private String otaOriginalAddress = "";
'''
new_fields = '''    private boolean otaBootInspectionScheduled;
    private int otaTransitionAttempts;
    private int otaServiceDiscoveryRetries;
    private boolean otaBootCandidateConnected;
    private String otaOriginalAddress = "";
'''
if old_fields not in src:
    raise SystemExit('field anchor not found')
src = src.replace(old_fields, new_fields, 1)

old_scan_address = '''            String address = safeAddress(device);
            devices.put(address, new DeviceEntry(device, name == null ? "(sem nome)" : name, result.getRssi()));
            runOnUiThread(MainActivity.this::renderDevices);
'''
new_scan_address = '''            String address = safeAddress(device);
            byte[] advertisement = result.getScanRecord() == null ? null : result.getScanRecord().getBytes();
            if (is5610BootloaderAdvertisement(advertisement)) {
                if (!Boolean.TRUE.equals(bootloaderAdvertisements.put(address, true))) {
                    append("BOOTLOADER ADV DETECTADO: " + address
                            + " possui assinatura 4C31/MAC/5610 no fabricante.");
                }
            }
            devices.put(address, new DeviceEntry(device, name == null ? "(sem nome)" : name, result.getRssi()));
            runOnUiThread(MainActivity.this::renderDevices);
'''
if old_scan_address not in src:
    raise SystemExit('scan address anchor not found')
src = src.replace(old_scan_address, new_scan_address, 1)

old_connected = '''                setStatus("Link BLE aberto. Descobrindo serviços do G28...");
                if (hasConnectPermission()) {
                    boolean queued = false;
                    try {
                        queued = currentGatt.discoverServices();
                    } catch (Exception error) {
                        append("Falha ao solicitar descoberta de serviços: " + error.getMessage());
                    }
                    append("Descoberta de serviços solicitada queued=" + queued);
                    if (!queued) {
                        schedule(600, () -> {
                            if (gatt == currentGatt && hasConnectPermission() && !emergencyStopped) {
                                try {
                                    boolean retry = currentGatt.discoverServices();
                                    append("Nova tentativa de descoberta queued=" + retry);
                                } catch (Exception error) {
                                    append("Falha na nova tentativa de descoberta: " + error.getMessage());
                                }
                            }
                        });
                    }
                }
'''
new_connected = '''                String connectedAddress = safeAddress(currentGatt.getDevice());
                boolean advertisedBootloader = Boolean.TRUE.equals(bootloaderAdvertisements.get(connectedAddress));
                otaBootCandidateConnected = advertisedBootloader
                        || (otaStartRequested && otaTransitionScanArmed
                        && isOtaTransitionCandidate(connectedAddress, safeName(currentGatt.getDevice())));
                if (otaBootCandidateConnected) {
                    otaServiceDiscoveryRetries = 0;
                    if (!otaTransitionScanArmed) {
                        otaTransitionScanArmed = true;
                        otaStartRequested = true;
                        otaOriginalAddress = xor55Address(connectedAddress);
                        append("BOOTLOADER RECOVERY: estado OTA reconhecido após reinício do app; MAC normal inferido="
                                + otaOriginalAddress);
                    }
                    setStatus("Bootloader G28 conectado. Aguardando o perfil GATT ficar pronto...");
                    append("BOOTLOADER LINK: candidato XOR55 conectado; descoberta será atrasada para evitar cache GATT vazio.");
                    try {
                        boolean high = currentGatt.requestConnectionPriority(BluetoothGatt.CONNECTION_PRIORITY_HIGH);
                        append("BOOTLOADER LINK: prioridade alta queued=" + high);
                    } catch (Exception error) {
                        append("BOOTLOADER LINK: prioridade alta indisponível: " + error.getMessage());
                    }
                    schedule(2_800, () -> requestServiceDiscovery(currentGatt, true));
                } else {
                    setStatus("Link BLE aberto. Descobrindo serviços do G28...");
                    requestServiceDiscovery(currentGatt, false);
                }
'''
if old_connected not in src:
    raise SystemExit('connected discovery block not found')
src = src.replace(old_connected, new_connected, 1)

old_services_head = '''            append("Serviços descobertos status=" + status);
            if (status != BluetoothGatt.GATT_SUCCESS) {
                setStatus("Falha ao descobrir serviços GATT: " + status);
                return;
            }
            discoverCharacteristics(currentGatt);
            renderOtaStatus();
'''
new_services_head = '''            int serviceCount = currentGatt.getServices() == null ? 0 : currentGatt.getServices().size();
            append("Serviços descobertos status=" + status + " count=" + serviceCount
                    + " retry=" + otaServiceDiscoveryRetries);
            if (status != BluetoothGatt.GATT_SUCCESS) {
                setStatus("Falha ao descobrir serviços GATT: " + status);
                if (otaBootCandidateConnected && otaServiceDiscoveryRetries < 6) {
                    otaServiceDiscoveryRetries++;
                    schedule(1_800, () -> requestServiceDiscovery(currentGatt, true));
                }
                return;
            }
            if (otaBootCandidateConnected && serviceCount == 0) {
                if (otaServiceDiscoveryRetries < 6) {
                    otaServiceDiscoveryRetries++;
                    append("BOOTLOADER GATT VAZIO: limpando cache e repetindo descoberta "
                            + otaServiceDiscoveryRetries + "/6 sem desconectar.");
                    schedule(1_800, () -> requestServiceDiscovery(currentGatt, true));
                    return;
                }
                if (otaTransitionAttempts >= 8) {
                    append("BOOTLOADER GATT VAZIO persistente após 8 conexões. Mantendo o relógio em OTA sem transmitir dados.");
                    setStatus("Bootloader ativo, mas GATT permanece vazio; nenhuma escrita foi realizada.");
                    return;
                }
                append("BOOTLOADER GATT VAZIO persistente: encerrando esta conexão para nova tentativa limpa.");
                setStatus("Bootloader ativo, mas GATT ainda vazio. Reconectando...");
                otaReconnectInProgress = false;
                disconnectGattOnly();
                schedule(2_500, MainActivity.this::startOtaTransitionScan);
                return;
            }
            discoverCharacteristics(currentGatt);
            renderOtaStatus();
'''
if old_services_head not in src:
    raise SystemExit('services head anchor not found')
src = src.replace(old_services_head, new_services_head, 1)

old_transition_no_service = '''            if (otaStartRequested && otaTransitionScanArmed) {
                append("TRANSIÇÃO OTA: reconexão ainda em modo normal; serviço 6e40ff01 não apareceu nesta tentativa.");
                if (otaTransitionAttempts < 3) {
                    setStatus("Reconectou em modo normal. Repetindo a busca OTA...");
                    schedule(650, () -> {
                        disconnectGattOnly();
                        otaReconnectInProgress = false;
                        schedule(1_000, MainActivity.this::startOtaTransitionScan);
                    });
                    return;
                }
                setStatus("Após 3 tentativas, o G28 continua em modo normal; OTA não confirmado.");
            }
'''
new_transition_no_service = '''            if (otaStartRequested && otaTransitionScanArmed) {
                append("TRANSIÇÃO OTA: perfil GATT encontrado, mas o serviço 6e40ff01 ainda não apareceu.");
                append("BOOTLOADER: dumpando todos os serviços antes de reconectar.");
                dumpGatt();
                if (otaTransitionAttempts < 8) {
                    setStatus("Bootloader ativo; repetindo conexão e descoberta GATT...");
                    schedule(900, () -> {
                        otaReconnectInProgress = false;
                        disconnectGattOnly();
                        schedule(2_500, MainActivity.this::startOtaTransitionScan);
                    });
                    return;
                }
                setStatus("Bootloader ativo, mas serviço 6e40ff01 não foi exposto após 8 tentativas.");
            }
'''
if old_transition_no_service not in src:
    raise SystemExit('transition no-service block not found')
src = src.replace(old_transition_no_service, new_transition_no_service, 1)

old_send_reset = '''        otaReconnectInProgress = false;
        otaTransitionAttempts = 0;
        byte[] frame = buildNusCommand(0x13, 0x02, new byte[]{0x01});
'''
new_send_reset = '''        otaReconnectInProgress = false;
        otaTransitionAttempts = 0;
        otaServiceDiscoveryRetries = 0;
        otaBootCandidateConnected = false;
        byte[] frame = buildNusCommand(0x13, 0x02, new byte[]{0x01});
'''
if old_send_reset not in src:
    raise SystemExit('send reset anchor not found')
src = src.replace(old_send_reset, new_send_reset, 1)

connect_anchor = '''    private void discoverCharacteristics(BluetoothGatt currentGatt) {
'''
helper = '''    private void requestServiceDiscovery(BluetoothGatt currentGatt, boolean bootloader) {
        if (gatt != currentGatt || emergencyStopped || !hasConnectPermission()) return;
        if (bootloader) {
            boolean refreshed = refreshGattCache(currentGatt);
            append("BOOTLOADER GATT: refresh cache=" + refreshed
                    + "; aguardando antes de discoverServices().");
        }
        schedule(bootloader ? 900 : 0, () -> {
            if (gatt != currentGatt || emergencyStopped || !hasConnectPermission()) return;
            try {
                boolean queued = currentGatt.discoverServices();
                append((bootloader ? "BOOTLOADER " : "")
                        + "Descoberta de serviços solicitada queued=" + queued);
                if (!queued && bootloader && otaServiceDiscoveryRetries < 6) {
                    otaServiceDiscoveryRetries++;
                    schedule(1_800, () -> requestServiceDiscovery(currentGatt, true));
                }
            } catch (Exception error) {
                append("Falha ao solicitar descoberta de serviços: " + error.getMessage());
                if (bootloader && otaServiceDiscoveryRetries < 6) {
                    otaServiceDiscoveryRetries++;
                    schedule(1_800, () -> requestServiceDiscovery(currentGatt, true));
                }
            }
        });
    }

    private boolean refreshGattCache(BluetoothGatt currentGatt) {
        try {
            java.lang.reflect.Method refresh = currentGatt.getClass().getMethod("refresh");
            Object result = refresh.invoke(currentGatt);
            return result instanceof Boolean && (Boolean) result;
        } catch (Exception error) {
            append("BOOTLOADER GATT: refresh() não disponível: " + error.getClass().getSimpleName());
            return false;
        }
    }

    private boolean is5610BootloaderAdvertisement(byte[] value) {
        if (value == null || value.length < 12) return false;
        for (int i = 0; i <= value.length - 12; i++) {
            if ((value[i] & 0xFF) == 0x0B
                    && (value[i + 1] & 0xFF) == 0xFF
                    && (value[i + 2] & 0xFF) == 0x4C
                    && (value[i + 3] & 0xFF) == 0x31
                    && (value[i + 10] & 0xFF) == 0x56
                    && (value[i + 11] & 0xFF) == 0x10) {
                return true;
            }
        }
        return false;
    }

'''
if connect_anchor not in src:
    raise SystemExit('helper insertion anchor not found')
src = src.replace(connect_anchor, helper + connect_anchor, 1)

scan_guard = '''    private void startOtaTransitionScan() {
        if (emergencyStopped || !otaTransitionScanArmed) return;
'''
scan_guard_new = '''    private void startOtaTransitionScan() {
        if (emergencyStopped || !otaTransitionScanArmed || otaReconnectInProgress) return;
        if (scanning) {
            append("BUSCA TRANSIÇÃO OTA ignorada: já existe uma busca ativa.");
            return;
        }
'''
if scan_guard not in src:
    raise SystemExit('transition scan guard not found')
src = src.replace(scan_guard, scan_guard_new, 1)

src = src.replace('''        schedule(15_000, () -> {
''', '''        schedule(22_000, () -> {
''', 1)

required = [
    'Orbis Watch OTA 5610 v3.12',
    'BOOTLOADER ADV DETECTADO',
    'BOOTLOADER RECOVERY',
    'BOOTLOADER GATT VAZIO',
    'requestServiceDiscovery',
    'refreshGattCache',
    'is5610BootloaderAdvertisement',
    'otaServiceDiscoveryRetries',
    'perfil GATT encontrado',
]
for marker in required:
    if marker not in src:
        raise SystemExit('missing v3.12 marker: ' + marker)

path.write_text(src, encoding='utf-8')
print('v3.12 resilient bootloader discovery patch applied')
