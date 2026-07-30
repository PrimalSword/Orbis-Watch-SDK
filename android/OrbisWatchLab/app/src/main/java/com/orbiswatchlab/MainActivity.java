package com.orbiswatchlab;

import android.Manifest;
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
import android.bluetooth.le.BluetoothLeScanner;
import android.bluetooth.le.ScanCallback;
import android.bluetooth.le.ScanResult;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Context;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.graphics.Typeface;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.text.InputType;
import android.view.Gravity;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.RadioButton;
import android.widget.RadioGroup;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Date;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.UUID;

public final class MainActivity extends Activity {
    private static final int REQUEST_PERMISSIONS = 1001;

    private static final UUID NUS_SERVICE_UUID = UUID.fromString("6e400001-b5a3-f393-e0a9-e50e24dcca9f");
    private static final UUID NUS_WRITE_UUID = UUID.fromString("6e400002-b5a3-f393-e0a9-e50e24dcca9f");
    private static final UUID NUS_NOTIFY_UUID = UUID.fromString("6e400003-b5a3-f393-e0a9-e50e24dcca9f");
    private static final UUID CCCD_UUID = UUID.fromString("00002902-0000-1000-8000-00805f9b34fb");
    private static final UUID BATTERY_UUID = UUID.fromString("00002a19-0000-1000-8000-00805f9b34fb");
    private static final UUID FEATURE_UUID = UUID.fromString("00002a28-0000-1000-8000-00805f9b34fb");

    private final Handler handler = new Handler(Looper.getMainLooper());
    private final List<Runnable> pendingTasks = new ArrayList<>();
    private final Map<String, DeviceEntry> devices = new LinkedHashMap<>();
    private final SimpleDateFormat clock = new SimpleDateFormat("HH:mm:ss.SSS", Locale.US);

    private BluetoothAdapter adapter;
    private BluetoothLeScanner scanner;
    private BluetoothGatt gatt;
    private BluetoothGattCharacteristic writeCharacteristic;
    private BluetoothGattCharacteristic notifyCharacteristic;
    private BluetoothGattCharacteristic batteryCharacteristic;
    private BluetoothGattCharacteristic featureCharacteristic;
    private BluetoothDevice selectedDevice;

    private TextView statusView;
    private TextView logView;
    private RadioGroup deviceGroup;

    private boolean scanning;
    private boolean emergencyStopped;
    private boolean experimentRunning;

    private final ScanCallback scanCallback = new ScanCallback() {
        @Override
        public void onScanResult(int callbackType, ScanResult result) {
            BluetoothDevice device = result.getDevice();
            String name = safeName(device);
            if ((name == null || name.equals("(sem nome)")) && result.getScanRecord() != null) {
                String advertised = result.getScanRecord().getDeviceName();
                if (advertised != null && !advertised.isBlank()) {
                    name = advertised;
                }
            }
            DeviceEntry entry = new DeviceEntry(device, name == null ? "(sem nome)" : name, result.getRssi());
            devices.put(safeAddress(device), entry);
            runOnUiThread(MainActivity.this::renderDevices);
        }

        @Override
        public void onScanFailed(int errorCode) {
            scanning = false;
            append("SCAN FAILED: " + errorCode);
            setStatus("Falha ao procurar dispositivos: " + errorCode);
        }
    };

    private final BluetoothGattCallback gattCallback = new BluetoothGattCallback() {
        @Override
        public void onConnectionStateChange(BluetoothGatt currentGatt, int status, int newState) {
            append("Conexão GATT status=" + status + " state=" + newState);
            if (newState == BluetoothProfile.STATE_CONNECTED) {
                gatt = currentGatt;
                setStatus("G28 conectado. Descobrindo serviços...");
                if (hasConnectPermission()) {
                    currentGatt.discoverServices();
                }
            } else if (newState == BluetoothProfile.STATE_DISCONNECTED) {
                writeCharacteristic = null;
                notifyCharacteristic = null;
                batteryCharacteristic = null;
                featureCharacteristic = null;
                experimentRunning = false;
                setStatus(emergencyStopped
                        ? "PARADA DE EMERGÊNCIA ATIVA — desconectado"
                        : "Relógio desconectado");
            }
        }

        @Override
        public void onServicesDiscovered(BluetoothGatt currentGatt, int status) {
            append("Serviços descobertos status=" + status);
            BluetoothGattService nus = currentGatt.getService(NUS_SERVICE_UUID);
            if (nus != null) {
                writeCharacteristic = nus.getCharacteristic(NUS_WRITE_UUID);
                notifyCharacteristic = nus.getCharacteristic(NUS_NOTIFY_UUID);
            }

            for (BluetoothGattService service : currentGatt.getServices()) {
                for (BluetoothGattCharacteristic characteristic : service.getCharacteristics()) {
                    if (BATTERY_UUID.equals(characteristic.getUuid())) {
                        batteryCharacteristic = characteristic;
                    }
                    if (FEATURE_UUID.equals(characteristic.getUuid())) {
                        featureCharacteristic = characteristic;
                    }
                }
            }

            if (notifyCharacteristic != null) {
                enableNotifications(currentGatt, notifyCharacteristic);
            }

            if (writeCharacteristic == null || notifyCharacteristic == null) {
                setStatus("Conectado, mas o serviço Nordic UART não foi encontrado");
                append("NUS incompleto: write=" + (writeCharacteristic != null)
                        + " notify=" + (notifyCharacteristic != null));
                return;
            }

            setStatus("G28 conectado e pronto");
            append("NUS pronto: TX=" + writeCharacteristic.getUuid()
                    + " RX=" + notifyCharacteristic.getUuid());
        }

        @Override
        public void onCharacteristicWrite(BluetoothGatt currentGatt,
                                          BluetoothGattCharacteristic characteristic,
                                          int status) {
            append("Write concluído " + characteristic.getUuid() + " status=" + status);
        }

        @Override
        public void onCharacteristicRead(BluetoothGatt currentGatt,
                                         BluetoothGattCharacteristic characteristic,
                                         int status) {
            handleRead(characteristic, characteristic.getValue(), status);
        }

        @Override
        public void onCharacteristicRead(BluetoothGatt currentGatt,
                                         BluetoothGattCharacteristic characteristic,
                                         byte[] value,
                                         int status) {
            handleRead(characteristic, value, status);
        }

        @Override
        public void onCharacteristicChanged(BluetoothGatt currentGatt,
                                            BluetoothGattCharacteristic characteristic) {
            handleNotification(characteristic, characteristic.getValue());
        }

        @Override
        public void onCharacteristicChanged(BluetoothGatt currentGatt,
                                            BluetoothGattCharacteristic characteristic,
                                            byte[] value) {
            handleNotification(characteristic, value);
        }

        @Override
        public void onDescriptorWrite(BluetoothGatt currentGatt,
                                      BluetoothGattDescriptor descriptor,
                                      int status) {
            append("NOTIFY configurado " + descriptor.getCharacteristic().getUuid()
                    + " status=" + status);
        }
    };

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        buildUi();
        initialiseBluetooth();
    }

    private void buildUi() {
        LinearLayout outer = new LinearLayout(this);
        outer.setOrientation(LinearLayout.VERTICAL);
        outer.setPadding(dp(14), dp(12), dp(14), dp(10));

        TextView title = text("Orbis Watch Lab", 31, false);
        title.setGravity(Gravity.CENTER_HORIZONTAL);
        outer.addView(title, matchWrap());

        TextView subtitle = text(
                "Laboratório BLE para o G28 — testes controlados de protocolo",
                16,
                false
        );
        subtitle.setPadding(0, dp(8), 0, dp(12));
        outer.addView(subtitle, matchWrap());

        statusView = text("Inicializando Bluetooth...", 17, false);
        statusView.setPadding(dp(8), dp(8), dp(8), dp(8));
        outer.addView(statusView, matchWrap());

        Button emergencyButton = button("EMERGÊNCIA — PARAR E DESCONECTAR");
        emergencyButton.setTextColor(Color.WHITE);
        emergencyButton.setBackgroundColor(Color.rgb(170, 25, 25));
        emergencyButton.setOnClickListener(v -> emergencyStop());
        outer.addView(emergencyButton, marginLayout(0, 8, 0, 8));

        TextView emergencyNote = text(
                "A emergência cancela tarefas ainda não enviadas, bloqueia novas transmissões "
                        + "e encerra o GATT. Ela não consegue desfazer um quadro que já chegou ao relógio.",
                13,
                false
        );
        emergencyNote.setPadding(dp(4), 0, dp(4), dp(8));
        outer.addView(emergencyNote, matchWrap());

        ScrollView scrollView = new ScrollView(this);
        LinearLayout content = new LinearLayout(this);
        content.setOrientation(LinearLayout.VERTICAL);
        scrollView.addView(content);
        outer.addView(scrollView, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                0,
                1f
        ));

        Button permissionButton = button("1. Permitir Bluetooth");
        permissionButton.setOnClickListener(v -> requestBluetoothPermissions());
        content.addView(permissionButton, marginLayout(0, 6, 0, 6));

        Button scanButton = button("2. Procurar relógio");
        scanButton.setOnClickListener(v -> startScan());
        content.addView(scanButton, marginLayout(0, 6, 0, 6));

        deviceGroup = new RadioGroup(this);
        deviceGroup.setOrientation(RadioGroup.VERTICAL);
        content.addView(deviceGroup, matchWrap());

        Button connectButton = button("3. Conectar ao selecionado");
        connectButton.setOnClickListener(v -> connectSelected());
        content.addView(connectButton, marginLayout(0, 6, 0, 6));

        LinearLayout connectionRow = new LinearLayout(this);
        connectionRow.setOrientation(LinearLayout.HORIZONTAL);
        Button disconnectButton = button("Desconectar");
        disconnectButton.setOnClickListener(v -> disconnect(false));
        Button rearmButton = button("Rearmar testes");
        rearmButton.setOnClickListener(v -> rearmLaboratory());
        connectionRow.addView(disconnectButton, weightedButton());
        connectionRow.addView(rearmButton, weightedButton());
        content.addView(connectionRow, marginLayout(0, 2, 0, 10));

        Button diagnosticButton = button("Ler diagnóstico completo");
        diagnosticButton.setOnClickListener(v -> runDiagnostic());
        content.addView(diagnosticButton, marginLayout(0, 6, 0, 6));

        Button expandedButton = button("Teste expandido 0x18 (subcomandos 0–3)");
        expandedButton.setOnClickListener(v -> runExpanded18());
        content.addView(expandedButton, marginLayout(0, 6, 0, 6));

        TextView watchfaceHeading = text("Watchface 0x0F — um subcomando por vez", 18, true);
        watchfaceHeading.setPadding(0, dp(14), 0, dp(4));
        content.addView(watchfaceHeading, matchWrap());

        TextView watchfaceNote = text(
                "O subcomando 0 já respondeu sem efeito visível. Os botões abaixo enviam somente "
                        + "DF 00 05 [checksum] 0F 01 [sub] 00 00 e consultam DEVICE_INFO depois. "
                        + "Não há imagem, firmware, finalização ou repetição automática.",
                14,
                false
        );
        content.addView(watchfaceNote, matchWrap());

        LinearLayout subRowOne = new LinearLayout(this);
        subRowOne.setOrientation(LinearLayout.HORIZONTAL);
        subRowOne.addView(watchfaceButton(0), weightedButton());
        subRowOne.addView(watchfaceButton(1), weightedButton());
        content.addView(subRowOne, marginLayout(0, 6, 0, 2));

        LinearLayout subRowTwo = new LinearLayout(this);
        subRowTwo.setOrientation(LinearLayout.HORIZONTAL);
        subRowTwo.addView(watchfaceButton(2), weightedButton());
        subRowTwo.addView(watchfaceButton(3), weightedButton());
        content.addView(subRowTwo, marginLayout(0, 2, 0, 8));

        EditText rawInput = new EditText(this);
        rawInput.setHint("Quadro hexadecimal seguro, por exemplo: DF 00 05 D8 F3 01 00 00 00");
        rawInput.setSingleLine(false);
        rawInput.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_FLAG_CAP_CHARACTERS);
        content.addView(rawInput, marginLayout(0, 8, 0, 2));

        Button rawButton = button("Enviar quadro bruto permitido");
        rawButton.setOnClickListener(v -> sendRawAllowed(rawInput.getText().toString()));
        content.addView(rawButton, marginLayout(0, 2, 0, 8));

        LinearLayout logRow = new LinearLayout(this);
        logRow.setOrientation(LinearLayout.HORIZONTAL);
        Button copyButton = button("Copiar log");
        copyButton.setOnClickListener(v -> copyLog());
        Button clearButton = button("Limpar log");
        clearButton.setOnClickListener(v -> logView.setText(""));
        logRow.addView(copyButton, weightedButton());
        logRow.addView(clearButton, weightedButton());
        content.addView(logRow, marginLayout(0, 4, 0, 6));

        logView = text("", 13, false);
        logView.setTypeface(Typeface.MONOSPACE);
        logView.setTextIsSelectable(true);
        logView.setPadding(dp(4), dp(8), dp(4), dp(40));
        content.addView(logView, matchWrap());

        setContentView(outer);
    }

    private Button watchfaceButton(int subcommand) {
        Button button = button("0x0F / sub " + subcommand);
        button.setOnClickListener(v -> confirmWatchfaceSubcommand(subcommand));
        return button;
    }

    private void initialiseBluetooth() {
        BluetoothManager manager = (BluetoothManager) getSystemService(Context.BLUETOOTH_SERVICE);
        if (manager == null) {
            setStatus("BluetoothManager indisponível");
            return;
        }
        adapter = manager.getAdapter();
        if (adapter == null) {
            setStatus("Este celular não possui Bluetooth");
            return;
        }
        if (!adapter.isEnabled()) {
            setStatus("Ative o Bluetooth do celular");
            return;
        }
        scanner = adapter.getBluetoothLeScanner();
        setStatus("Pronto para procurar o G28");
        requestBluetoothPermissions();
    }

    private void requestBluetoothPermissions() {
        if (Build.VERSION.SDK_INT >= 31) {
            if (!hasScanPermission() || !hasConnectPermission()) {
                requestPermissions(new String[]{
                        Manifest.permission.BLUETOOTH_SCAN,
                        Manifest.permission.BLUETOOTH_CONNECT
                }, REQUEST_PERMISSIONS);
                return;
            }
        } else if (Build.VERSION.SDK_INT >= 23
                && checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION)
                != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{Manifest.permission.ACCESS_FINE_LOCATION}, REQUEST_PERMISSIONS);
            return;
        }
        toast("Permissões Bluetooth prontas");
    }

    private boolean hasScanPermission() {
        return Build.VERSION.SDK_INT < 31
                || checkSelfPermission(Manifest.permission.BLUETOOTH_SCAN)
                == PackageManager.PERMISSION_GRANTED;
    }

    private boolean hasConnectPermission() {
        return Build.VERSION.SDK_INT < 31
                || checkSelfPermission(Manifest.permission.BLUETOOTH_CONNECT)
                == PackageManager.PERMISSION_GRANTED;
    }

    private void startScan() {
        if (emergencyStopped) {
            toast("Rearme o laboratório antes de procurar ou conectar");
            return;
        }
        if (!hasScanPermission()) {
            requestBluetoothPermissions();
            return;
        }
        if (adapter == null || !adapter.isEnabled()) {
            setStatus("Ative o Bluetooth do celular");
            return;
        }
        scanner = adapter.getBluetoothLeScanner();
        if (scanner == null) {
            setStatus("Scanner BLE indisponível");
            return;
        }

        stopScan();
        devices.clear();
        renderDevices();
        scanning = true;
        scanner.startScan(scanCallback);
        setStatus("Procurando dispositivos BLE...");
        append("Busca BLE iniciada");
        schedule(12_000, () -> {
            stopScan();
            if (gatt == null) {
                setStatus(devices.isEmpty()
                        ? "Nenhum dispositivo encontrado"
                        : "Selecione o G28 e toque em conectar");
            }
        });
    }

    private void stopScan() {
        if (scanner != null && scanning && hasScanPermission()) {
            try {
                scanner.stopScan(scanCallback);
            } catch (Exception ignored) {
            }
        }
        scanning = false;
    }

    private void renderDevices() {
        deviceGroup.removeAllViews();
        List<DeviceEntry> entries = new ArrayList<>(devices.values());
        entries.sort((left, right) -> {
            boolean leftG28 = left.name.toUpperCase(Locale.US).contains("G28");
            boolean rightG28 = right.name.toUpperCase(Locale.US).contains("G28");
            if (leftG28 != rightG28) {
                return leftG28 ? -1 : 1;
            }
            return Integer.compare(right.rssi, left.rssi);
        });

        for (DeviceEntry entry : entries) {
            RadioButton item = new RadioButton(this);
            item.setText(entry.name + " / " + safeAddress(entry.device) + "  RSSI=" + entry.rssi);
            item.setTextSize(16);
            item.setTag(entry.device);
            item.setPadding(dp(8), dp(4), dp(4), dp(4));
            item.setOnCheckedChangeListener((buttonView, isChecked) -> {
                if (isChecked) {
                    selectedDevice = (BluetoothDevice) buttonView.getTag();
                }
            });
            deviceGroup.addView(item, matchWrap());

            if (entry.name.toUpperCase(Locale.US).contains("G28")
                    || "41:42:99:10:58:57".equalsIgnoreCase(safeAddress(entry.device))) {
                item.setChecked(true);
            }
        }
    }

    private void connectSelected() {
        if (emergencyStopped) {
            toast("Parada de emergência ativa. Toque em Rearmar testes.");
            return;
        }
        if (!hasConnectPermission()) {
            requestBluetoothPermissions();
            return;
        }
        if (selectedDevice == null) {
            toast("Selecione o G28 na lista");
            return;
        }
        stopScan();
        disconnectGattOnly();
        setStatus("Conectando a " + safeName(selectedDevice) + "...");
        append("Conectando a " + safeName(selectedDevice) + " / " + safeAddress(selectedDevice));
        if (Build.VERSION.SDK_INT >= 23) {
            gatt = selectedDevice.connectGatt(this, false, gattCallback, BluetoothDevice.TRANSPORT_LE);
        } else {
            gatt = selectedDevice.connectGatt(this, false, gattCallback);
        }
    }

    private void enableNotifications(BluetoothGatt currentGatt,
                                     BluetoothGattCharacteristic characteristic) {
        if (!hasConnectPermission()) {
            return;
        }
        currentGatt.setCharacteristicNotification(characteristic, true);
        BluetoothGattDescriptor descriptor = characteristic.getDescriptor(CCCD_UUID);
        if (descriptor == null) {
            append("CCCD não encontrado em " + characteristic.getUuid());
            return;
        }
        byte[] value = BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE;
        if (Build.VERSION.SDK_INT >= 33) {
            int result = currentGatt.writeDescriptor(descriptor, value);
            append("WRITE CCCD solicitado result=" + result);
        } else {
            descriptor.setValue(value);
            boolean queued = currentGatt.writeDescriptor(descriptor);
            append("WRITE CCCD solicitado queued=" + queued);
        }
    }

    private void runDiagnostic() {
        if (!ensureReady("diagnóstico")) {
            return;
        }
        cancelPendingTasks();
        experimentRunning = true;
        append("Iniciando diagnóstico: F3 → 19 → 1A → GATT battery/features");
        sendFrame(buildFrame(0xF3, 0x01, 0x00, 0x00, 0x00));
        schedule(350, () -> sendFrame(buildFrame(0x19, 0x01, 0x00, 0x00, 0x00)));
        schedule(700, () -> sendFrame(buildFrame(0x1A, 0x01, 0x00, 0x00, 0x00)));
        schedule(1_050, () -> readCharacteristic(batteryCharacteristic, "battery"));
        schedule(1_400, () -> readCharacteristic(featureCharacteristic, "features"));
        schedule(2_000, () -> {
            experimentRunning = false;
            append("Diagnóstico concluído");
        });
    }

    private void runExpanded18() {
        if (!ensureReady("teste 0x18")) {
            return;
        }
        cancelPendingTasks();
        experimentRunning = true;
        append("Teste expandido: comando 0x18, subcomandos 0–3, um quadro por vez.");
        for (int sub = 0; sub <= 3; sub++) {
            final int value = sub;
            schedule(sub * 350L, () -> sendFrame(buildFrame(0x18, 0x01, value, 0x00, 0x00)));
        }
        schedule(2_200, () -> {
            experimentRunning = false;
            append("Teste 0x18 concluído");
        });
    }

    private void confirmWatchfaceSubcommand(int subcommand) {
        if (!ensureReady("watchface 0x0F")) {
            return;
        }
        byte[] frame = buildFrame(0x0F, 0x01, subcommand, 0x00, 0x00);
        new AlertDialog.Builder(this)
                .setTitle("Enviar 0x0F / sub " + subcommand + "?")
                .setMessage(
                        "Será enviado uma única vez:\n\n" + hex(frame)
                                + "\n\nDepois de 2,5 segundos o app consultará DEVICE_INFO. "
                                + "Não há repetição automática. Use o botão vermelho se surgir "
                                + "progresso, reinício, vibração anormal ou desconexão."
                )
                .setNegativeButton("Cancelar", null)
                .setPositiveButton("Enviar uma vez", (dialog, which) -> runWatchfaceSubcommand(subcommand))
                .show();
    }

    private void runWatchfaceSubcommand(int subcommand) {
        if (!ensureReady("watchface 0x0F")) {
            return;
        }
        cancelPendingTasks();
        experimentRunning = true;
        append("EXPERIMENTO → 0x0F sub=" + subcommand + ", um único quadro.");
        sendFrame(buildFrame(0x0F, 0x01, subcommand, 0x00, 0x00));
        schedule(2_500, () -> {
            append("Verificação pós-experimento → DEVICE_INFO 0xF3");
            sendFrame(buildFrame(0xF3, 0x01, 0x00, 0x00, 0x00));
        });
        schedule(5_000, () -> {
            experimentRunning = false;
            append("Janela de observação concluída para 0x0F/sub " + subcommand);
        });
    }

    private boolean ensureReady(String operation) {
        if (emergencyStopped) {
            toast("Parada de emergência ativa. Rearme antes de " + operation + ".");
            return false;
        }
        if (experimentRunning) {
            toast("Já existe um teste em andamento");
            return false;
        }
        if (gatt == null || writeCharacteristic == null || !hasConnectPermission()) {
            toast("Conecte ao G28 e aguarde o status 'pronto'");
            return false;
        }
        return true;
    }

    private void sendRawAllowed(String rawText) {
        if (!ensureReady("envio bruto")) {
            return;
        }
        byte[] frame;
        try {
            frame = parseHex(rawText);
        } catch (IllegalArgumentException error) {
            toast(error.getMessage());
            return;
        }
        if (frame.length < 5 || (frame[0] & 0xFF) != 0xDF) {
            toast("O quadro deve começar por DF e conter o comando no byte 5");
            return;
        }
        int command = frame[4] & 0xFF;
        if (!(command == 0x18 || command == 0x19 || command == 0x1A
                || command == 0xF0 || command == 0xF3)) {
            toast(String.format(
                    Locale.US,
                    "Comando 0x%02X bloqueado no campo bruto; use os testes controlados",
                    command
            ));
            return;
        }
        sendFrame(frame);
    }

    private void sendFrame(byte[] frame) {
        if (emergencyStopped) {
            append("TX BLOQUEADO: parada de emergência ativa");
            return;
        }
        BluetoothGatt currentGatt = gatt;
        BluetoothGattCharacteristic characteristic = writeCharacteristic;
        if (currentGatt == null || characteristic == null || !hasConnectPermission()) {
            append("TX cancelado: GATT/NUS indisponível");
            return;
        }

        append("TX " + hex(frame));
        try {
            if (Build.VERSION.SDK_INT >= 33) {
                int result = currentGatt.writeCharacteristic(
                        characteristic,
                        frame,
                        BluetoothGattCharacteristic.WRITE_TYPE_NO_RESPONSE
                );
                append("Write solicitado result=" + result);
            } else {
                characteristic.setWriteType(BluetoothGattCharacteristic.WRITE_TYPE_NO_RESPONSE);
                characteristic.setValue(frame);
                boolean queued = currentGatt.writeCharacteristic(characteristic);
                append("Write solicitado queued=" + queued);
            }
        } catch (Exception error) {
            append("Falha TX: " + error.getClass().getSimpleName() + ": " + error.getMessage());
        }
    }

    private void readCharacteristic(BluetoothGattCharacteristic characteristic, String name) {
        if (emergencyStopped) {
            append("READ " + name + " bloqueado pela emergência");
            return;
        }
        if (gatt == null || characteristic == null || !hasConnectPermission()) {
            append("READ " + name + " indisponível");
            return;
        }
        try {
            boolean queued = gatt.readCharacteristic(characteristic);
            append("READ solicitado " + characteristic.getUuid() + " queued=" + queued);
        } catch (Exception error) {
            append("Falha READ " + name + ": " + error.getMessage());
        }
    }

    private void handleRead(BluetoothGattCharacteristic characteristic, byte[] value, int status) {
        append("READ " + characteristic.getUuid() + " status=" + status + " data=" + hex(value));
        if (BATTERY_UUID.equals(characteristic.getUuid()) && value != null && value.length == 1) {
            append("Bateria interpretada: " + (value[0] & 0xFF) + "%");
        }
    }

    private void handleNotification(BluetoothGattCharacteristic characteristic, byte[] value) {
        byte[] copy = value == null ? new byte[0] : value.clone();
        append("RX " + characteristic.getUuid() + " " + hex(copy));
        if (copy.length >= 5 && ((copy[0] & 0xFF) == 0xFD || (copy[0] & 0xFF) == 0xDF)) {
            int command = copy[4] & 0xFF;
            append(String.format(
                    Locale.US,
                    "  ↳ quadro %02X, comando 0x%02X, ASCII=\"%s\"",
                    copy[0] & 0xFF,
                    command,
                    printableAscii(copy)
            ));
        }
    }

    private void emergencyStop() {
        emergencyStopped = true;
        experimentRunning = false;
        cancelPendingTasks();
        stopScan();
        append("!!! PARADA DE EMERGÊNCIA ACIONADA !!!");
        append("Tarefas futuras canceladas; novos TX bloqueados; encerrando GATT.");
        disconnectGattOnly();
        setStatus("PARADA DE EMERGÊNCIA ATIVA — sem transmissão e sem conexão");
        toast("Processo interrompido e Bluetooth desconectado");
    }

    private void rearmLaboratory() {
        new AlertDialog.Builder(this)
                .setTitle("Rearmar laboratório?")
                .setMessage("Isso apenas libera novos testes. O relógio continuará desconectado até você procurá-lo e conectar novamente.")
                .setNegativeButton("Cancelar", null)
                .setPositiveButton("Rearmar", (dialog, which) -> {
                    emergencyStopped = false;
                    experimentRunning = false;
                    setStatus("Laboratório rearmado — procure e conecte o G28");
                    append("Laboratório rearmado pelo operador");
                })
                .show();
    }

    private void disconnect(boolean fromEmergency) {
        if (!fromEmergency) {
            cancelPendingTasks();
            experimentRunning = false;
        }
        stopScan();
        disconnectGattOnly();
        setStatus(emergencyStopped ? "PARADA DE EMERGÊNCIA ATIVA" : "Desconectado");
        append("Conexão encerrada pelo operador");
    }

    private void disconnectGattOnly() {
        BluetoothGatt currentGatt = gatt;
        gatt = null;
        writeCharacteristic = null;
        notifyCharacteristic = null;
        batteryCharacteristic = null;
        featureCharacteristic = null;
        if (currentGatt != null && hasConnectPermission()) {
            try {
                currentGatt.disconnect();
            } catch (Exception ignored) {
            }
            try {
                currentGatt.close();
            } catch (Exception ignored) {
            }
        }
    }

    private void schedule(long delayMillis, Runnable action) {
        final Runnable[] holder = new Runnable[1];
        holder[0] = () -> {
            pendingTasks.remove(holder[0]);
            if (!emergencyStopped) {
                action.run();
            }
        };
        pendingTasks.add(holder[0]);
        handler.postDelayed(holder[0], delayMillis);
    }

    private void cancelPendingTasks() {
        for (Runnable task : new ArrayList<>(pendingTasks)) {
            handler.removeCallbacks(task);
        }
        pendingTasks.clear();
    }

    private static byte[] buildFrame(int command, int p0, int p1, int p2, int p3) {
        byte[] frame = new byte[]{
                (byte) 0xDF,
                0x00,
                0x05,
                0x00,
                (byte) command,
                (byte) p0,
                (byte) p1,
                (byte) p2,
                (byte) p3
        };
        int checksum = 0;
        for (int index = 0; index < frame.length; index++) {
            if (index != 3) {
                checksum = (checksum + (frame[index] & 0xFF)) & 0xFF;
            }
        }
        frame[3] = (byte) checksum;
        return frame;
    }

    private static byte[] parseHex(String text) {
        String cleaned = text == null ? "" : text.replaceAll("[^0-9A-Fa-f]", "");
        if (cleaned.isEmpty()) {
            throw new IllegalArgumentException("Digite um quadro hexadecimal");
        }
        if ((cleaned.length() & 1) != 0) {
            throw new IllegalArgumentException("Quantidade ímpar de dígitos hexadecimais");
        }
        byte[] result = new byte[cleaned.length() / 2];
        for (int index = 0; index < result.length; index++) {
            int offset = index * 2;
            result[index] = (byte) Integer.parseInt(cleaned.substring(offset, offset + 2), 16);
        }
        return result;
    }

    private static String hex(byte[] bytes) {
        if (bytes == null || bytes.length == 0) {
            return "(vazio)";
        }
        StringBuilder result = new StringBuilder();
        for (byte value : bytes) {
            if (result.length() > 0) {
                result.append(' ');
            }
            result.append(String.format(Locale.US, "%02X", value & 0xFF));
        }
        return result.toString();
    }

    private static String printableAscii(byte[] bytes) {
        StringBuilder result = new StringBuilder();
        for (byte value : bytes) {
            int unsigned = value & 0xFF;
            result.append(unsigned >= 32 && unsigned <= 126 ? (char) unsigned : '.');
        }
        return result.toString();
    }

    private String safeName(BluetoothDevice device) {
        if (!hasConnectPermission()) {
            return "(sem permissão)";
        }
        try {
            String name = device.getName();
            return name == null || name.isBlank() ? "(sem nome)" : name;
        } catch (SecurityException error) {
            return "(sem permissão)";
        }
    }

    private String safeAddress(BluetoothDevice device) {
        if (!hasConnectPermission()) {
            return "(protegido)";
        }
        try {
            return device.getAddress();
        } catch (SecurityException error) {
            return "(protegido)";
        }
    }

    private void copyLog() {
        ClipboardManager clipboard = (ClipboardManager) getSystemService(Context.CLIPBOARD_SERVICE);
        if (clipboard != null) {
            clipboard.setPrimaryClip(ClipData.newPlainText("Orbis Watch Lab log", logView.getText()));
            toast("Log copiado");
        }
    }

    private void setStatus(String status) {
        runOnUiThread(() -> statusView.setText("Status: " + status));
    }

    private void append(String message) {
        runOnUiThread(() -> logView.append(clock.format(new Date()) + "  " + message + "\n"));
    }

    private void toast(String message) {
        runOnUiThread(() -> Toast.makeText(this, message, Toast.LENGTH_SHORT).show());
    }

    private TextView text(String value, int sizeSp, boolean bold) {
        TextView view = new TextView(this);
        view.setText(value);
        view.setTextSize(sizeSp);
        if (bold) {
            view.setTypeface(Typeface.DEFAULT_BOLD);
        }
        return view;
    }

    private Button button(String label) {
        Button button = new Button(this);
        button.setText(label);
        button.setTextSize(15);
        button.setAllCaps(false);
        button.setMinHeight(dp(54));
        return button;
    }

    private LinearLayout.LayoutParams matchWrap() {
        return new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT
        );
    }

    private LinearLayout.LayoutParams marginLayout(int left, int top, int right, int bottom) {
        LinearLayout.LayoutParams params = matchWrap();
        params.setMargins(dp(left), dp(top), dp(right), dp(bottom));
        return params;
    }

    private LinearLayout.LayoutParams weightedButton() {
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(
                0,
                ViewGroup.LayoutParams.WRAP_CONTENT,
                1f
        );
        params.setMargins(dp(2), dp(2), dp(2), dp(2));
        return params;
    }

    private int dp(int value) {
        return (int) (value * getResources().getDisplayMetrics().density + 0.5f);
    }

    @Override
    protected void onDestroy() {
        cancelPendingTasks();
        stopScan();
        disconnectGattOnly();
        super.onDestroy();
    }

    private static final class DeviceEntry {
        final BluetoothDevice device;
        final String name;
        final int rssi;

        DeviceEntry(BluetoothDevice device, String name, int rssi) {
            this.device = device;
            this.name = name;
            this.rssi = rssi;
        }
    }
}
