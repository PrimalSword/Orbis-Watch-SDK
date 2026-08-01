from __future__ import annotations

from pathlib import Path
import sys


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"missing block: {label}")
    if text.count(old) != 1:
        raise SystemExit(f"ambiguous block: {label} count={text.count(old)}")
    return text.replace(old, new, 1)


path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")

text = replace_once(
    text,
    'private boolean servicesStarted;\n    private boolean replayStarted;',
    'private boolean servicesStarted;\n    private boolean mtuReady;\n    private boolean notificationsReady;\n    private boolean replayStarted;',
    'fields',
)

text = replace_once(
    text,
    '        servicesStarted = false;\n        append("Conectando sem pareamento…");',
    '        servicesStarted = false;\n        mtuReady = false;\n        notificationsReady = false;\n        append("Conectando sem pareamento…");',
    'connect reset',
)

text = replace_once(
    text,
    '''                if (newState == BluetoothProfile.STATE_CONNECTED && status == BluetoothGatt.GATT_SUCCESS) {
                    state = State.DISCOVERING;
                    updateUi();
                    try { callbackGatt.requestConnectionPriority(BluetoothGatt.CONNECTION_PRIORITY_HIGH); } catch (Exception ignored) {}
                    boolean mtuRequested;
                    try { mtuRequested = callbackGatt.requestMtu(247); } catch (Exception e) { mtuRequested = false; }
                    append("Conectado. MTU 247 solicitado=" + mtuRequested);
                    handler.postDelayed(() -> discoverOnce(callbackGatt), 1500);
''',
    '''                if (newState == BluetoothProfile.STATE_CONNECTED && status == BluetoothGatt.GATT_SUCCESS) {
                    state = State.DISCOVERING;
                    updateUi();
                    append("Conectado. Descoberta GATT será iniciada antes de MTU/prioridade.");
                    handler.postDelayed(() -> discoverOnce(callbackGatt), 250);
''',
    'connected flow',
)

text = replace_once(
    text,
    '''        public void onMtuChanged(BluetoothGatt callbackGatt, int mtu, int status) {
            runOnUiThread(() -> {
                append("MTU=" + mtu + " status=" + status);
                if (mtu < 238) {
                    failBeforeStart("MTU insuficiente: " + mtu + "; necessário ao menos 238 para frames de 235 bytes.");
                    return;
                }
                discoverOnce(callbackGatt);
            });
        }
''',
    '''        public void onMtuChanged(BluetoothGatt callbackGatt, int mtu, int status) {
            runOnUiThread(() -> {
                append("MTU=" + mtu + " status=" + status);
                if (status != BluetoothGatt.GATT_SUCCESS || mtu < 238) {
                    failBeforeStart("MTU insuficiente ou recusado: mtu=" + mtu + " status=" + status + "; necessário ao menos 238.");
                    return;
                }
                mtuReady = true;
                maybeReady();
            });
        }
''',
    'mtu callback',
)

text = replace_once(
    text,
    '''                state = State.READY;
                append("FF01 notify ativo. Sessão pronta; nenhum byte funcional enviado.");
                updateUi();
''',
    '''                notificationsReady = true;
                append("FF01 notify ativo. Solicitando MTU somente agora, após descoberta e CCCD.");
                try { callbackGatt.requestConnectionPriority(BluetoothGatt.CONNECTION_PRIORITY_HIGH); } catch (Exception ignored) {}
                boolean mtuRequested;
                try { mtuRequested = callbackGatt.requestMtu(247); } catch (Exception e) { mtuRequested = false; }
                append("MTU 247 solicitado=" + mtuRequested);
                if (!mtuRequested) {
                    failBeforeStart("Android recusou requestMtu(247) após ativar FF01.");
                    return;
                }
''',
    'descriptor write',
)

insert_anchor = '''    private void showReplayConfirmation() {
'''
insert_block = '''    private void maybeReady() {
        if (!notificationsReady || !mtuReady || state == State.FAILED) return;
        state = State.READY;
        append("Sessão pronta: FF01 notify ativo e MTU validado. Nenhum byte funcional enviado.");
        updateUi();
    }

'''
text = replace_once(text, insert_anchor, insert_block + insert_anchor, 'maybeReady insert')

text = text.replace(
    'Feche o HryFine e qualquer outro app do relógio. Desligue o Bluetooth do PC. ',
    'FORCE A PARADA do HryFine em Configurações > Apps antes de conectar. Desligue o Bluetooth do PC. ',
)

text = text.replace(
    'ORBIS G28 — REPLAY ANDROID',
    'ORBIS G28 — REPLAY ANDROID v0.2',
)

path.write_text(text, encoding="utf-8")
print("patched", path)
