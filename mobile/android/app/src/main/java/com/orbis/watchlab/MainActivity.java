package com.orbis.watchlab;

import android.Manifest;
import android.annotation.SuppressLint;
import android.app.Activity;
import android.app.AlertDialog;
import android.bluetooth.BluetoothAdapter;
import android.bluetooth.BluetoothDevice;
import android.bluetooth.BluetoothGatt;
import android.bluetooth.BluetoothGattCallback;
import android.bluetooth.BluetoothGattCharacteristic;
import android.bluetooth.BluetoothGattDescriptor;
import android.bluetooth.BluetoothGattService;
import android.bluetooth.BluetoothManager;
import android.bluetooth.BluetoothProfile;
import android.bluetooth.BluetoothStatusCodes;
import android.bluetooth.le.BluetoothLeScanner;
import android.bluetooth.le.ScanCallback;
import android.bluetooth.le.ScanResult;
import android.bluetooth.le.ScanSettings;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.provider.Settings;
import android.text.InputType;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.ArrayAdapter;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ListView;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Date;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;
import java.util.UUID;

public final class MainActivity extends Activity {
    private static final int REQUEST_BLE_PERMISSIONS = 1001;
    private static final String EXPECTED_ADDRESS = "41:42:99:10:58:57";

    private static final UUID NUS_SERVICE_UUID = UUID.fromString("6e400001-b5a3-f393-e0a9-e50e24dcca9f");
    private static final UUID NUS_WRITE_UUID = UUID.fromString("6e400002-b5a3-f393-e0a9-e50e24dcca9f");
    private static final UUID NUS_NOTIFY_UUID = UUID.fromString("6e400003-b5a3-f393-e0a9-e50e24dcca9f");
    private static final UUID CCCD_UUID = UUID.fromString("00002902-0000-1000-8000-00805f9b34fb");
    private static final UUID BATTERY_LEVEL_UUID = UUID.fromString("00002a19-0000-1000-8000-00805f9b34fb");
    private static final UUID FEATURE_BITMAP_UUID = UUID.fromString("00002a28-0000-1000-8000-00805f9b34fb");

    private static final Set<Integer> BLOCKED_COMMANDS = Set.of(
            0x01, // OTA
            0x02, // settings order / potentially mutating
            0x06, // reset
            0x0A, // flash read / vendor-specific side effects unknown
            0x0D, // factory restore
            0x0F, // watchface transfer: only through dedicated guarded probe
            0x13  // alternate OTA
    );

    private final Handler handler = new Handler(Looper.getMainLooper());
    private final List<BluetoothDevice> devices = new ArrayList<>();
    private final Set<String> seenAddresses = new HashSet<>();
    private final StringBuilder logBuffer = new StringBuilder();
    private final SimpleDateFormat clockFormat = new SimpleDateFormat("HH:mm:ss.SSS", Locale.US);

    private BluetoothAdapter bluetoothAdapter;
    private BluetoothLeScanner scanner;
    private BluetoothGatt gatt;
    private BluetoothGattCharacteristic writeCharacteristic;
    private BluetoothGattCharacteristic notifyCharacteristic;
    private BluetoothDevice selectedDevice;
    private boolean scanning;

    private TextView statusView;
    private TextView logView;
    private ListView deviceList;
    private ArrayAdapter<String> deviceAdapter;
    private EditText rawInput;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        BluetoothManager manager = getSystemService(BluetoothManager.class);
        bluetoothAdapter = manager == null ? null : manager.getAdapter();

        buildInterface();
        appendLog("Orbis Watch Lab iniciado. Nenhum comando foi enviado.");
        appendLog("Alvo conhecido: G28 / " + EXPECTED_ADDRESS);
        ensurePermissions();
    }

    private void buildInterface() {
        ScrollView scroll = new ScrollView(this);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(dp(16), dp(16), dp(16), dp(24));
        scroll.addView(root, new ScrollView.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT
        ));

        TextView title = new TextView(this);
        title.setText("Orbis Watch Lab");
        title.setTextSize(26f);
        title.setGravity(Gravity.CENTER_HORIZONTAL);
        root.addView(title, matchWrap());

        TextView subtitle = new TextView(this);
        subtitle.setText("Laboratório BLE para o G28 — leitura, captura e experimentos controlados");
        subtitle.setTextSize(14f);
        subtitle.setPadding(0, dp(6), 0, dp(12));
        root.addView(subtitle, matchWrap());

        statusView = new TextView(this);
        statusView.setText("Status: desconectado");
        statusView.setTextSize(16f);
        statusView.setPadding(dp(12), dp(10), dp(12), dp(10));
        root.addView(statusView, matchWrap());

        root.addView(button("1. Permitir Bluetooth", view -> ensurePermissions()), matchWrap());
        root.addView(button("2. Procurar relógio", view -> startScan()), matchWrap());

        deviceAdapter = new ArrayAdapter<>(this, android.R.layout.simple_list_item_single_choice, new ArrayList<>());
        deviceList = new ListView(this);
        deviceList.setChoiceMode(ListView.CHOICE_MODE_SINGLE);
        deviceList.setAdapter(deviceAdapter);
        deviceList.setOnItemClickListener((parent, view, position, id) -> {
            selectedDevice = devices.get(position);
            appendLog("Selecionado: " + describeDevice(selectedDevice));
        });
        LinearLayout.LayoutParams listParams = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                dp(170)
        );
        listParams.setMargins(0, dp(8), 0, dp(8));
        root.addView(deviceList, listParams);

        root.addView(button("3. Conectar ao selecionado", view -> connectSelected()), matchWrap());
        root.addView(button("Ler diagnóstico completo", view -> readSnapshot()), matchWrap());
        root.addView(button("Teste expandido 0x18 (subcomandos 0–3)", view -> runExpandedProbe()), matchWrap());
        root.addView(button("Handshake experimental de watchface 0x0F", view -> confirmWatchfaceProbe()), matchWrap());

        TextView warning = new TextView(this);
        warning.setText(
                "O handshake 0x0F envia apenas um quadro vazio e depois verifica se o relógio continua respondendo. " +
                "Não envia imagem, firmware ou comando de finalização. Mesmo assim, o comportamento do fabricante ainda é desconhecido."
        );
        warning.setTextSize(13f);
        warning.setPadding(dp(8), dp(10), dp(8), dp(10));
        root.addView(warning, matchWrap());

        rawInput = new EditText(this);
        rawInput.setHint("Quadro hexadecimal, por exemplo: DF 00 05 D8 F3 01 00 00 00");
        rawInput.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_FLAG_NO_SUGGESTIONS);
        root.addView(rawInput, matchWrap());
        root.addView(button("Enviar quadro bruto permitido", view -> confirmRawSend()), matchWrap());

        LinearLayout logButtons = new LinearLayout(this);
        logButtons.setOrientation(LinearLayout.HORIZONTAL);
        Button copy = button("Copiar log", view -> copyLog());
        Button clear = button("Limpar log", view -> {
            logBuffer.setLength(0);
            logView.setText("");
        });
        logButtons.addView(copy, weighted());
        logButtons.addView(clear, weighted());
        root.addView(logButtons, matchWrap());

        logView = new TextView(this);
        logView.setTextSize(12f);
        logView.setTextIsSelectable(true);
        logView.setPadding(dp(8), dp(8), dp(8), dp(8));
        root.addView(logView, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                dp(420)
        ));

        setContentView(scroll);
    }

    private Button button(String text, View.OnClickListener listener) {
        Button button = new Button(this);
        button.setText(text);
        button.setAllCaps(false);
        button.setOnClickListener(listener);
        return button;
    }

    private LinearLayout.LayoutParams matchWrap() {
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT
        );
        params.setMargins(0, dp(4), 0, dp(4));
        return params;
    }

    private LinearLayout.LayoutParams weighted() {
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f);
        params.setMargins(dp(2), dp(4), dp(2), dp(4));
        return params;
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }

    private boolean hasPermissions() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            return checkSelfPermission(Manifest.permission.BLUETOOTH_SCAN) == PackageManager.PERMISSION_GRANTED
                    && checkSelfPermission(Manifest.permission.BLUETOOTH_CONNECT) == PackageManager.PERMISSION_GRANTED;
        }
        return checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED;
    }

    private void ensurePermissions() {
        if (hasPermissions()) {
            appendLog("Permissões Bluetooth concedidas.");
            return;
        }

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            requestPermissions(new String[]{
                    Manifest.permission.BLUETOOTH_SCAN,
                    Manifest.permission.BLUETOOTH_CONNECT
            }, REQUEST_BLE_PERMISSIONS);
        } else {
            requestPermissions(new String[]{Manifest.permission.ACCESS_FINE_LOCATION}, REQUEST_BLE_PERMISSIONS);
        }
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode != REQUEST_BLE_PERMISSIONS) {
            return;
        }
        appendLog(hasPermissions() ? "Permissões autorizadas." : "Permissões negadas; BLE indisponível.");
    }

    @SuppressLint("MissingPermission")
    private void startScan() {
        if (!hasPermissions()) {
            ensurePermissions();
            return;
        }
        if (bluetoothAdapter == null) {
            appendLog("Este celular não possui adaptador Bluetooth.");
            return;
        }
        if (!bluetoothAdapter.isEnabled()) {
            appendLog("Bluetooth desligado; solicitando ativação.");
            startActivity(new Intent(BluetoothAdapter.ACTION_REQUEST_ENABLE));
            return;
        }

        stopScan();
        scanner = bluetoothAdapter.getBluetoothLeScanner();
        if (scanner == null) {
            appendLog("Scanner BLE indisponível.");
            return;
        }

        devices.clear();
        seenAddresses.clear();
        deviceAdapter.clear();
        selectedDevice = null;

        ScanSettings settings = new ScanSettings.Builder()
                .setScanMode(ScanSettings.SCAN_MODE_LOW_LATENCY)
                .build();
        scanner.startScan(null, settings, scanCallback);
        scanning = true;
        setStatus("procurando dispositivos por 12 segundos");
        appendLog("SCAN iniciado. Feche ou force a parada do HryFine durante o teste.");
        handler.postDelayed(this::stopScan, 12_000L);
    }

    @SuppressLint("MissingPermission")
    private void stopScan() {
        if (scanning && scanner != null && hasPermissions()) {
            try {
                scanner.stopScan(scanCallback);
            } catch (RuntimeException error) {
                appendLog("Falha ao encerrar scan: " + error.getMessage());
            }
        }
        if (scanning) {
            appendLog("SCAN encerrado; encontrados: " + devices.size());
        }
        scanning = false;
    }

    private final ScanCallback scanCallback = new ScanCallback() {
        @Override
        public void onScanResult(int callbackType, ScanResult result) {
            addScanResult(result);
        }

        @Override
        public void onBatchScanResults(List<ScanResult> results) {
            for (ScanResult result : results) {
                addScanResult(result);
            }
        }

        @Override
        public void onScanFailed(int errorCode) {
            appendLog("SCAN falhou, código: " + errorCode);
            setStatus("falha no scan BLE");
        }
    };

    @SuppressLint("MissingPermission")
    private void addScanResult(ScanResult result) {
        BluetoothDevice device = result.getDevice();
        String address = device.getAddress();
        if (!seenAddresses.add(address)) {
            return;
        }
        runOnUiThread(() -> {
            devices.add(device);
            deviceAdapter.add(describeDevice(device) + "  RSSI=" + result.getRssi());
            deviceAdapter.notifyDataSetChanged();
            if (EXPECTED_ADDRESS.equalsIgnoreCase(address) || safeName(device).toUpperCase(Locale.ROOT).contains("G28")) {
                int position = devices.size() - 1;
                selectedDevice = device;
                deviceList.setItemChecked(position, true);
                appendLog("G28 provável selecionado automaticamente: " + describeDevice(device));
            }
        });
    }

    @SuppressLint("MissingPermission")
    private String safeName(BluetoothDevice device) {
        try {
            String name = device.getName();
            return name == null || name.isBlank() ? "(sem nome)" : name;
        } catch (SecurityException ignored) {
            return "(nome bloqueado)";
        }
    }

    @SuppressLint("MissingPermission")
    private String describeDevice(BluetoothDevice device) {
        return safeName(device) + " / " + device.getAddress();
    }

    @SuppressLint("MissingPermission")
    private void connectSelected() {
        if (!hasPermissions()) {
            ensurePermissions();
            return;
        }
        if (selectedDevice == null) {
            appendLog("Selecione um dispositivo antes de conectar.");
            return;
        }

        stopScan();
        closeGatt();
        setStatus("conectando a " + describeDevice(selectedDevice));
        appendLog("CONNECT → " + describeDevice(selectedDevice));
        gatt = selectedDevice.connectGatt(this, false, gattCallback, BluetoothDevice.TRANSPORT_LE);
    }

    private final BluetoothGattCallback gattCallback = new BluetoothGattCallback() {
        @Override
        @SuppressLint("MissingPermission")
        public void onConnectionStateChange(BluetoothGatt callbackGatt, int status, int newState) {
            appendLog("GATT state status=" + status + " newState=" + newState);
            if (newState == BluetoothProfile.STATE_CONNECTED) {
                setStatus("conectado; descobrindo serviços");
                callbackGatt.requestMtu(247);
                callbackGatt.discoverServices();
            } else if (newState == BluetoothProfile.STATE_DISCONNECTED) {
                writeCharacteristic = null;
                notifyCharacteristic = null;
                setStatus("desconectado");
            }
        }

        @Override
        @SuppressLint("MissingPermission")
        public void onServicesDiscovered(BluetoothGatt callbackGatt, int status) {
            appendLog("Serviços descobertos, status=" + status);
            BluetoothGattService service = callbackGatt.getService(NUS_SERVICE_UUID);
            if (service == null) {
                setStatus("conectado, mas Nordic UART não encontrado");
                appendLog("NUS ausente. Serviços disponíveis:");
                for (BluetoothGattService item : callbackGatt.getServices()) {
                    appendLog("  SERVICE " + item.getUuid());
                }
                return;
            }

            writeCharacteristic = service.getCharacteristic(NUS_WRITE_UUID);
            notifyCharacteristic = service.getCharacteristic(NUS_NOTIFY_UUID);
            if (writeCharacteristic == null || notifyCharacteristic == null) {
                setStatus("NUS incompleto");
                appendLog("Características RX/TX esperadas não foram encontradas.");
                return;
            }

            callbackGatt.setCharacteristicNotification(notifyCharacteristic, true);
            BluetoothGattDescriptor cccd = notifyCharacteristic.getDescriptor(CCCD_UUID);
            if (cccd != null) {
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                    int result = callbackGatt.writeDescriptor(cccd, BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE);
                    appendLog("Ativação de notify solicitada, resultado=" + result);
                } else {
                    cccd.setValue(BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE);
                    boolean queued = callbackGatt.writeDescriptor(cccd);
                    appendLog("Ativação de notify enfileirada=" + queued);
                }
            }
            setStatus("G28 conectado e pronto");
            appendLog("NUS pronto: write=" + NUS_WRITE_UUID + " notify=" + NUS_NOTIFY_UUID);
        }

        @Override
        public void onMtuChanged(BluetoothGatt callbackGatt, int mtu, int status) {
            appendLog("MTU negociado=" + mtu + " status=" + status);
        }

        @Override
        public void onDescriptorWrite(BluetoothGatt callbackGatt, BluetoothGattDescriptor descriptor, int status) {
            appendLog("Descriptor write " + descriptor.getUuid() + " status=" + status);
        }

        @Override
        public void onCharacteristicWrite(BluetoothGatt callbackGatt, BluetoothGattCharacteristic characteristic, int status) {
            appendLog("Write concluído " + characteristic.getUuid() + " status=" + status);
        }

        @Override
        public void onCharacteristicChanged(BluetoothGatt callbackGatt, BluetoothGattCharacteristic characteristic, byte[] value) {
            handleIncoming(characteristic.getUuid(), value);
        }

        @Override
        @SuppressWarnings("deprecation")
        public void onCharacteristicChanged(BluetoothGatt callbackGatt, BluetoothGattCharacteristic characteristic) {
            handleIncoming(characteristic.getUuid(), characteristic.getValue());
        }

        @Override
        public void onCharacteristicRead(
                BluetoothGatt callbackGatt,
                BluetoothGattCharacteristic characteristic,
                byte[] value,
                int status
        ) {
            handleRead(characteristic.getUuid(), value, status);
        }

        @Override
        @SuppressWarnings("deprecation")
        public void onCharacteristicRead(
                BluetoothGatt callbackGatt,
                BluetoothGattCharacteristic characteristic,
                int status
        ) {
            handleRead(characteristic.getUuid(), characteristic.getValue(), status);
        }
    };

    private void handleIncoming(UUID uuid, byte[] value) {
        byte[] safe = value == null ? new byte[0] : value.clone();
        appendLog("RX " + uuid + "  " + hex(safe));
        if (safe.length >= 5 && (safe[0] & 0xFF) == 0xFD) {
            int command = safe[4] & 0xFF;
            appendLog("  ↳ quadro FD, comando 0x" + String.format(Locale.US, "%02X", command)
                    + ", ASCII=\"" + printableAscii(safe) + "\"");
        }
    }

    private void handleRead(UUID uuid, byte[] value, int status) {
        byte[] safe = value == null ? new byte[0] : value.clone();
        appendLog("READ " + uuid + " status=" + status + " data=" + hex(safe));
        if (BATTERY_LEVEL_UUID.equals(uuid) && safe.length == 1) {
            appendLog("  ↳ bateria=" + (safe[0] & 0xFF) + "%");
        } else if (FEATURE_BITMAP_UUID.equals(uuid)) {
            appendLog("  ↳ feature bitmap, " + safe.length + " bytes");
        }
    }

    private void readSnapshot() {
        if (!isReady()) {
            return;
        }
        appendLog("Iniciando diagnóstico: F3 → 19 → 1A → GATT battery/features");
        sendProtocol(0xF3, 0x00, new byte[0]);
        handler.postDelayed(() -> sendProtocol(0x19, 0x00, new byte[0]), 350L);
        handler.postDelayed(() -> sendProtocol(0x1A, 0x00, new byte[0]), 700L);
        handler.postDelayed(() -> readGatt(BATTERY_LEVEL_UUID), 1_050L);
        handler.postDelayed(() -> readGatt(FEATURE_BITMAP_UUID), 1_400L);
    }

    private void runExpandedProbe() {
        if (!isReady()) {
            return;
        }
        appendLog("Teste expandido: comando 0x18, subcomandos 0–3, um quadro por vez.");
        for (int sub = 0; sub <= 3; sub++) {
            final int current = sub;
            handler.postDelayed(
                    () -> sendProtocol(0x18, current, new byte[0]),
                    sub * 350L
            );
        }
    }

    private void confirmWatchfaceProbe() {
        if (!isReady()) {
            return;
        }

        EditText confirmation = new EditText(this);
        confirmation.setHint("Digite ARRISCAR");
        confirmation.setSingleLine(true);

        new AlertDialog.Builder(this)
                .setTitle("Handshake experimental 0x0F")
                .setMessage(
                        "Será enviado somente um quadro 0x0F vazio, sem conteúdo, sem bloco de dados e sem finalização. " +
                        "Depois de 2,5 segundos o app consultará DEVICE_INFO para verificar se o relógio continua vivo. " +
                        "O efeito do quadro vazio ainda não é conhecido."
                )
                .setView(confirmation)
                .setNegativeButton("Cancelar", null)
                .setPositiveButton("Enviar uma vez", (dialog, which) -> {
                    if (!"ARRISCAR".equals(confirmation.getText().toString().trim())) {
                        toast("Confirmação incorreta; nada foi enviado.");
                        appendLog("Handshake 0x0F cancelado: confirmação incorreta.");
                        return;
                    }
                    appendLog("EXPERIMENTO → enviando um único handshake vazio 0x0F.");
                    sendProtocol(0x0F, 0x00, new byte[0]);
                    handler.postDelayed(() -> {
                        appendLog("Verificação pós-experimento → DEVICE_INFO 0xF3.");
                        sendProtocol(0xF3, 0x00, new byte[0]);
                    }, 2_500L);
                })
                .show();
    }

    private void confirmRawSend() {
        if (!isReady()) {
            return;
        }

        final byte[] data;
        try {
            data = parseHex(rawInput.getText().toString());
        } catch (IllegalArgumentException error) {
            toast(error.getMessage());
            return;
        }

        if (data.length > 244) {
            toast("Quadro maior que 244 bytes; o MVP não fragmenta envios brutos.");
            return;
        }

        Integer command = protocolCommand(data);
        if (command != null && BLOCKED_COMMANDS.contains(command)) {
            appendLog("TX bloqueado: comando 0x" + String.format(Locale.US, "%02X", command));
            toast("Comando bloqueado neste MVP. O 0x0F possui botão experimental próprio.");
            return;
        }

        String commandText = command == null
                ? "quadro não reconhecido como pacote Orbis"
                : "comando 0x" + String.format(Locale.US, "%02X", command);

        new AlertDialog.Builder(this)
                .setTitle("Enviar quadro bruto?")
                .setMessage(commandText + "\n\n" + hex(data))
                .setNegativeButton("Cancelar", null)
                .setPositiveButton("Enviar", (dialog, which) -> sendRaw(data))
                .show();
    }

    private Integer protocolCommand(byte[] data) {
        if (data.length >= 5 && (data[0] & 0xFF) == 0xDF) {
            return data[4] & 0xFF;
        }
        return null;
    }

    private void sendProtocol(int command, int subcommand, byte[] payload) {
        sendRaw(buildPacket(command, subcommand, payload));
    }

    private byte[] buildPacket(int command, int subcommand, byte[] payload) {
        byte[] safePayload = payload == null ? new byte[0] : payload;
        int bodyLength = 5 + safePayload.length;
        byte[] packet = new byte[9 + safePayload.length];
        packet[0] = (byte) 0xDF;
        packet[1] = (byte) ((bodyLength >>> 8) & 0xFF);
        packet[2] = (byte) (bodyLength & 0xFF);
        packet[3] = 0;
        packet[4] = (byte) command;
        packet[5] = 0x01;
        packet[6] = (byte) subcommand;
        packet[7] = (byte) ((safePayload.length >>> 8) & 0xFF);
        packet[8] = (byte) (safePayload.length & 0xFF);
        System.arraycopy(safePayload, 0, packet, 9, safePayload.length);

        int checksum = 0;
        for (int index = 0; index < packet.length; index++) {
            if (index != 3) {
                checksum = (checksum + (packet[index] & 0xFF)) & 0xFF;
            }
        }
        packet[3] = (byte) checksum;
        return packet;
    }

    @SuppressLint("MissingPermission")
    private void sendRaw(byte[] data) {
        if (!isReady()) {
            return;
        }
        appendLog("TX " + hex(data));

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            int result = gatt.writeCharacteristic(
                    writeCharacteristic,
                    data,
                    BluetoothGattCharacteristic.WRITE_TYPE_NO_RESPONSE
            );
            if (result != BluetoothStatusCodes.SUCCESS) {
                appendLog("Falha imediata no write, status=" + result);
            }
        } else {
            writeCharacteristic.setWriteType(BluetoothGattCharacteristic.WRITE_TYPE_NO_RESPONSE);
            writeCharacteristic.setValue(data);
            boolean queued = gatt.writeCharacteristic(writeCharacteristic);
            if (!queued) {
                appendLog("Falha ao enfileirar write BLE.");
            }
        }
    }

    @SuppressLint("MissingPermission")
    private void readGatt(UUID characteristicUuid) {
        if (gatt == null) {
            appendLog("READ cancelado: GATT ausente.");
            return;
        }
        for (BluetoothGattService service : gatt.getServices()) {
            BluetoothGattCharacteristic characteristic = service.getCharacteristic(characteristicUuid);
            if (characteristic != null) {
                boolean queued = gatt.readCharacteristic(characteristic);
                appendLog("READ solicitado " + characteristicUuid + " queued=" + queued);
                return;
            }
        }
        appendLog("Característica não encontrada: " + characteristicUuid);
    }

    private boolean isReady() {
        if (gatt == null || writeCharacteristic == null) {
            appendLog("Relógio ainda não está conectado/pronto.");
            toast("Conecte ao G28 primeiro.");
            return false;
        }
        return true;
    }

    private byte[] parseHex(String input) {
        String cleaned = input == null ? "" : input.replace("0x", "")
                .replaceAll("[^0-9A-Fa-f]", "");
        if (cleaned.isEmpty()) {
            throw new IllegalArgumentException("Digite um quadro hexadecimal.");
        }
        if ((cleaned.length() & 1) != 0) {
            throw new IllegalArgumentException("Quantidade ímpar de dígitos hexadecimais.");
        }

        byte[] result = new byte[cleaned.length() / 2];
        for (int index = 0; index < result.length; index++) {
            int high = Character.digit(cleaned.charAt(index * 2), 16);
            int low = Character.digit(cleaned.charAt(index * 2 + 1), 16);
            if (high < 0 || low < 0) {
                throw new IllegalArgumentException("Hexadecimal inválido.");
            }
            result[index] = (byte) ((high << 4) | low);
        }
        return result;
    }

    private String hex(byte[] data) {
        if (data == null || data.length == 0) {
            return "<vazio>";
        }
        StringBuilder output = new StringBuilder(data.length * 3);
        for (int index = 0; index < data.length; index++) {
            if (index > 0) {
                output.append(' ');
            }
            output.append(String.format(Locale.US, "%02X", data[index] & 0xFF));
        }
        return output.toString();
    }

    private String printableAscii(byte[] data) {
        StringBuilder output = new StringBuilder(data.length);
        for (byte item : data) {
            int value = item & 0xFF;
            output.append(value >= 32 && value <= 126 ? (char) value : '.');
        }
        return output.toString();
    }

    private void setStatus(String status) {
        runOnUiThread(() -> statusView.setText("Status: " + status));
    }

    private void appendLog(String message) {
        runOnUiThread(() -> {
            String line = clockFormat.format(new Date()) + "  " + message + "\n";
            logBuffer.append(line);
            if (logBuffer.length() > 60_000) {
                logBuffer.delete(0, logBuffer.length() - 50_000);
            }
            if (logView != null) {
                logView.setText(logBuffer.toString());
            }
        });
    }

    private void copyLog() {
        ClipboardManager clipboard = (ClipboardManager) getSystemService(Context.CLIPBOARD_SERVICE);
        clipboard.setPrimaryClip(ClipData.newPlainText("Orbis Watch Lab", logBuffer.toString()));
        toast("Log copiado.");
    }

    private void toast(String text) {
        Toast.makeText(this, text, Toast.LENGTH_SHORT).show();
    }

    @SuppressLint("MissingPermission")
    private void closeGatt() {
        if (gatt != null) {
            try {
                gatt.disconnect();
            } catch (RuntimeException ignored) {
                // Closing below is still attempted.
            }
            gatt.close();
        }
        gatt = null;
        writeCharacteristic = null;
        notifyCharacteristic = null;
    }

    @Override
    protected void onDestroy() {
        stopScan();
        closeGatt();
        handler.removeCallbacksAndMessages(null);
        super.onDestroy();
    }
}
