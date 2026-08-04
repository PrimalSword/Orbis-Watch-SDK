from pathlib import Path

JAVA = Path('android/OrbisG28Bridge/app/src/main/java/com/orbisg28bridge/BridgeActivity.java')
BUILD = Path('android/OrbisG28Bridge/app/build.gradle')
README = Path('android/OrbisG28Bridge/README_BRIDGE.md')

text = JAVA.read_text(encoding='utf-8')
old = '''                final String request = line;
                main.post(() -> handleCommand(request));
'''
new = '''                final String request = line;
                try {
                    JSONObject received = new JSONObject(request);
                    JSONObject ack = new JSONObject();
                    ack.put("type", "command_received");
                    ack.put("id", received.optInt("id", 0));
                    ack.put("cmd", received.optString("cmd", ""));
                    sendJson(ack);
                } catch (Exception ignored) { }
                handleCommand(request);
'''
if old not in text:
    raise SystemExit('command dispatch block not found')
text = text.replace(old, new, 1)
text = text.replace('Orbis G28 BLE Bridge v2.0', 'Orbis G28 BLE Bridge v2.1')
text = text.replace('event.put("version", "2.0")', 'event.put("version", "2.1")')
JAVA.write_text(text, encoding='utf-8')

build = BUILD.read_text(encoding='utf-8')
build = build.replace('versionCode 200', 'versionCode 210')
build = build.replace("versionName '2.0-adb-ble-bridge'", "versionName '2.1-command-dispatch-fix'")
BUILD.write_text(build, encoding='utf-8')

README.write_text(
    '# Orbis G28 Android BLE Bridge v2.1\n\n'
    'Correção: comandos recebidos por USB/ADB são reconhecidos imediatamente e processados fora da thread visual.\n\n'
    'PC -> ADB forward TCP 8765 -> Android -> BLE -> G28 OTA.\n\n'
    'Somente D5/0F e D5/01 são aceitos.\n',
    encoding='utf-8',
)
