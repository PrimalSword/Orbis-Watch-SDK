from pathlib import Path

JAVA = Path('android/OrbisG28Bridge/app/src/main/java/com/orbisg28bridge/BridgeActivity.java')
BUILD = Path('android/OrbisG28Bridge/app/build.gradle')
README = Path('android/OrbisG28Bridge/README_BRIDGE.md')

text = JAVA.read_text(encoding='utf-8')

old_executor = '''    private final ExecutorService io = Executors.newCachedThreadPool();
    private final Map<String, ScanEntry> scanEntries = new LinkedHashMap<>();
'''
new_executor = '''    private final ExecutorService io = Executors.newCachedThreadPool();
    private final ExecutorService socketWriter = Executors.newSingleThreadExecutor();
    private final Map<String, ScanEntry> scanEntries = new LinkedHashMap<>();
'''
if old_executor not in text:
    raise SystemExit('executor block not found')
text = text.replace(old_executor, new_executor, 1)

old_destroy = '''        io.shutdownNow();
        super.onDestroy();
'''
new_destroy = '''        socketWriter.shutdownNow();
        io.shutdownNow();
        super.onDestroy();
'''
if old_destroy not in text:
    raise SystemExit('onDestroy block not found')
text = text.replace(old_destroy, new_destroy, 1)

old_send = '''    private void sendJson(JSONObject object) {
        String line = object.toString();
        synchronized (writerLock) {
            if (clientWriter != null) {
                clientWriter.println(line);
                clientWriter.flush();
            }
        }
    }
'''
new_send = '''    private void sendJson(JSONObject object) {
        final String line = object.toString();
        if (socketWriter.isShutdown()) return;
        socketWriter.execute(() -> {
            synchronized (writerLock) {
                if (clientWriter != null) {
                    clientWriter.println(line);
                    clientWriter.flush();
                }
            }
        });
    }
'''
if old_send not in text:
    raise SystemExit('sendJson block not found')
text = text.replace(old_send, new_send, 1)

text = text.replace('Orbis G28 BLE Bridge v2.1', 'Orbis G28 BLE Bridge v2.2')
text = text.replace('event.put("version", "2.1")', 'event.put("version", "2.2")')
JAVA.write_text(text, encoding='utf-8')

build = BUILD.read_text(encoding='utf-8')
build = build.replace('versionCode 210', 'versionCode 220')
build = build.replace("versionName '2.1-command-dispatch-fix'", "versionName '2.2-background-socket-writes'")
BUILD.write_text(build, encoding='utf-8')

README.write_text(
    '# Orbis G28 Android BLE Bridge v2.2\n\n'
    'Correção: todas as respostas ao PC são escritas por um executor dedicado de I/O, nunca pela thread principal do Android.\n\n'
    'PC -> ADB forward TCP 8765 -> Android -> BLE -> G28 OTA.\n\n'
    'Somente D5/0F e D5/01 são aceitos.\n',
    encoding='utf-8',
)
