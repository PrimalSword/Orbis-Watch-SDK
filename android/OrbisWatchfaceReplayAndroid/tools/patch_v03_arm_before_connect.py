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
    'private boolean notificationsReady;\n    private boolean replayStarted;',
    'private boolean notificationsReady;\n    private boolean replayArmed;\n    private boolean replayStarted;',
    'replayArmed field',
)

text = replace_once(
    text,
    'TextView title = text("ORBIS G28 — REPLAY ANDROID v0.2", 21, Color.WHITE, true);',
    'TextView title = text("ORBIS G28 — REPLAY ANDROID v0.3", 21, Color.WHITE, true);',
    'title version',
)

text = replace_once(
    text,
    '''        connectButton = button("1. PROCURAR E CONECTAR G28");
        connectButton.setOnClickListener(v -> startScan());
        root.addView(connectButton);

        replayButton = button("2. ARMAR E REENVIAR MOSTRADOR OFICIAL");
        replayButton.setEnabled(false);
        replayButton.setOnClickListener(v -> showReplayConfirmation());
        root.addView(replayButton);
''',
    '''        connectButton = button("CONFIRMAR, CONECTAR E INICIAR");
        connectButton.setOnClickListener(v -> showArmBeforeConnect());
        root.addView(connectButton);

        replayButton = button("START AUTOMÁTICO ASSIM QUE A SESSÃO FICAR PRONTA");
        replayButton.setEnabled(false);
        replayButton.setVisibility(View.GONE);
        root.addView(replayButton);
''',
    'buttons',
)

anchor = '''    private void startScan() {
'''
method = '''    private void showArmBeforeConnect() {
        if (replayStarted) {
            toast("Não há reconexão automática após o START.");
            return;
        }
        if (state == State.SCANNING || state == State.CONNECTING || state == State.DISCOVERING) {
            toast("A conexão já está em andamento.");
            return;
        }
        EditText input = new EditText(this);
        input.setSingleLine(true);
        input.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_FLAG_CAP_CHARACTERS);
        input.setHint("G28 REPLAY");
        new AlertDialog.Builder(this)
                .setTitle("Confirmar antes de conectar")
                .setMessage("O G28 encerra sessões BLE ociosas em cerca de 12 segundos. Digite G28 REPLAY agora; depois o app conectará e enviará START automaticamente assim que FF01 e MTU estiverem prontos.")
                .setView(input)
                .setNegativeButton("Cancelar", null)
                .setPositiveButton("CONECTAR E INICIAR", (dialog, which) -> {
                    if (!"G28 REPLAY".equals(input.getText().toString().trim())) {
                        toast("Confirmação incorreta; nada enviado.");
                        return;
                    }
                    replayArmed = true;
                    append("REPLAY confirmado antes da conexão. O START será automático assim que a sessão ficar pronta.");
                    startScan();
                })
                .show();
    }

'''
text = replace_once(text, anchor, method + anchor, 'pre-connect confirmation method')

text = replace_once(
    text,
    '''    private void maybeReady() {
        if (!notificationsReady || !mtuReady || state == State.FAILED) return;
        state = State.READY;
        append("Sessão pronta: FF01 notify ativo e MTU validado. Nenhum byte funcional enviado.");
        updateUi();
    }
''',
    '''    private void maybeReady() {
        if (!notificationsReady || !mtuReady || state == State.FAILED) return;
        state = State.READY;
        append("Sessão pronta: FF01 notify ativo e MTU validado.");
        updateUi();
        if (replayArmed && !replayStarted) {
            append("Confirmação já registrada; enviando START imediatamente para evitar timeout ocioso do G28.");
            handler.postDelayed(this::beginReplay, 80);
        } else {
            append("Nenhum START enviado porque o replay não estava armado antes da conexão.");
        }
    }
''',
    'automatic start when ready',
)

text = replace_once(
    text,
    '''    private void beginReplay() {
        if (state != State.READY || replayStarted || frames.isEmpty()) return;
        replayStarted = true;
''',
    '''    private void beginReplay() {
        if (state != State.READY || replayStarted || !replayArmed || frames.isEmpty()) return;
        replayStarted = true;
        replayArmed = false;
''',
    'begin replay armed guard',
)

text = replace_once(
    text,
    '''    private void failBeforeStart(String message) {
        state = State.FAILED;
''',
    '''    private void failBeforeStart(String message) {
        replayArmed = false;
        state = State.FAILED;
''',
    'clear arm on pre-start failure',
)

text = replace_once(
    text,
    '''        } else {
            closeGatt();
            state = State.IDLE;
''',
    '''        } else {
            replayArmed = false;
            closeGatt();
            state = State.IDLE;
''',
    'clear arm on manual disconnect',
)

text = replace_once(
    text,
    'case READY: label = "pronto — nenhum START enviado"; break;',
    'case READY: label = replayArmed ? "pronto — START automático" : "pronto — não armado"; break;',
    'ready label',
)

text = replace_once(
    text,
    '''        connectButton.setEnabled(!replayStarted && state != State.SCANNING && state != State.CONNECTING && state != State.DISCOVERING);
        replayButton.setEnabled(state == State.READY && !replayStarted);
''',
    '''        connectButton.setEnabled(!replayStarted && state != State.SCANNING && state != State.CONNECTING && state != State.DISCOVERING && state != State.READY);
        replayButton.setEnabled(false);
''',
    'button state',
)

path.write_text(text, encoding="utf-8")
print("patched", path)
