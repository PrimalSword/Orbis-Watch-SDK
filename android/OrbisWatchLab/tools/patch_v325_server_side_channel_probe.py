#!/usr/bin/env python3
from pathlib import Path
import sys

path = Path(sys.argv[1])
src = path.read_text(encoding='utf-8')

def rep(old, new):
    global src
    if old not in src:
        raise SystemExit('patch_v325 missing snippet: ' + old[:220])
    src = src.replace(old, new, 1)

rep('Orbis Watch OTA 5610 v3.24', 'Orbis Watch OTA 5610 v3.25')
rep(
    'mediante confirmação explícita. A v3.24 mantém a consulta histórica V1.4→V1.0 e acrescenta a arqueologia estática dos comandos 0x07/0x0B/0xF0 e da ferramenta gráfica Bluetrum ABPartTool; nenhum comando novo é enviado ao relógio. ',
    'mediante confirmação explícita. A v3.25 preserva a consulta histórica e acrescenta uma inspeção HTTP dos canais force_update e firmware/get_configs do HryFine, somente de metadados, sem download e sem qualquer TX BLE. '
)

rep('''    private static final String OTA_ENDPOINT = "https://ota.lianhezhuli.com/api/hry/get_update";
    private static final String OTA_APP_KEY = "oaa648257e8";
    private static final String OTA_SECRET = "ead8ff5fe2f9385b55e6e509cf311a35";
''', '''    private static final String OTA_ENDPOINT = "https://ota.lianhezhuli.com/api/hry/get_update";
    private static final String FORCE_UPDATE_ENDPOINT = "https://ota.lianhezhuli.com/api/hry/force_update";
    private static final String FIRMWARE_CONFIG_ENDPOINT = "https://app.howruf.com/api/firmware/get_configs";
    private static final String OTA_APP_KEY = "oaa648257e8";
    private static final String OTA_SECRET = "ead8ff5fe2f9385b55e6e509cf311a35";
    private static final String PUBLIC_APP_KEY = "hfa6481b99d";
    private static final String PUBLIC_SECRET = "5317efb0d5949ae2144d3c8040cafdbb";
''')

rep('''    private boolean officialUpdateAvailable;
    private boolean historicalBinListProbeRunning;
    private boolean otaStartRequested;
''', '''    private boolean officialUpdateAvailable;
    private boolean historicalBinListProbeRunning;
    private boolean serverSideChannelProbeRunning;
    private boolean otaStartRequested;
''')

rep('''        Button parArchaeology = button("25. Mostrar análise Bluetrum .par — local");
        parArchaeology.setOnClickListener(v -> appendParToolArchaeology());
        content.addView(parArchaeology, marginLayout(0, 2, 0, 8));

        Button scanTransition = button("Buscar novamente o G28/OTA agora");''', '''        Button parArchaeology = button("25. Mostrar análise Bluetrum .par — local");
        parArchaeology.setOnClickListener(v -> appendParToolArchaeology());
        content.addView(parArchaeology, marginLayout(0, 2, 0, 2));

        Button serverSideChannels = button("26. Consultar canais alternativos do servidor — metadados, sem BLE");
        serverSideChannels.setOnClickListener(v -> confirmServerSideChannelProbe());
        content.addView(serverSideChannels, marginLayout(0, 2, 0, 8));

        Button scanTransition = button("Buscar novamente o G28/OTA agora");''')

rep('''    private void appendHryFineFrameValidation(byte[] frame, int prefix, int command, int key) {
''', '''    private void confirmServerSideChannelProbe() {
        if (!nusOtaInfoValidated || otaUniqueCode.isEmpty()) {
            toast("Execute primeiro a consulta OTA pelo NUS e aguarde a identidade V1.5/G28");
            return;
        }
        if (serverSideChannelProbeRunning) {
            toast("A consulta dos canais alternativos já está em andamento");
            return;
        }
        new AlertDialog.Builder(this)
                .setTitle("Canais alternativos do HryFine")
                .setMessage("A ação fará apenas consultas HTTP autenticadas aos endpoints oficiais force_update e firmware/get_configs. "
                        + "Serão usados o unique_code real e, no máximo, cinco códigos históricos já derivados. "
                        + "Nenhum arquivo será baixado, nenhum login anônimo será criado, nenhum comando BLE será transmitido e o relógio não será alterado.")
                .setNegativeButton("Cancelar", null)
                .setPositiveButton("CONSULTAR METADADOS", (dialog, which) -> runServerSideChannelProbe())
                .show();
    }

    private void runServerSideChannelProbe() {
        if (serverSideChannelProbeRunning) return;
        serverSideChannelProbeRunning = true;
        append("===== CANAIS ALTERNATIVOS DO SERVIDOR HRYFINE — SEM DOWNLOAD / SEM TX BLE =====");
        append("Identidade real: versão=" + emptyAsDash(otaVersion)
                + " projeto=" + emptyAsDash(otaProject)
                + " unique_code=" + otaUniqueCode);
        append("Endpoints: /api/hry/force_update e /api/firmware/get_configs.");
        append("Política: sem login anônimo, authcode vazio, sem download, sem BLE, sem 0x03 e sem escrita.");
        setStatus("Consultando canais alternativos do servidor; relógio permanece intocado.");

        ioExecutor.execute(() -> {
            int forceAttempts = 0;
            boolean forced = false;
            String forcedVersion = "";
            try {
                String[] versions = new String[]{otaVersion, "V1.4", "V1.3", "V1.2", "V1.1", "V1.0"};
                for (String version : versions) {
                    if (emergencyStopped) {
                        append("FORCE_UPDATE interrompido pela parada de emergência.");
                        break;
                    }
                    String code = version.equals(otaVersion) ? otaUniqueCode : buildHistoricalUniqueCode(version);
                    if (code.isEmpty()) continue;
                    forceAttempts++;
                    Map<String, String> params = buildOfficialServerParams(code);
                    params.put("sign", sign(params));
                    append("FORCE_UPDATE tentativa=" + forceAttempts + " versão=" + version + " unique_code=" + code);
                    String response = httpGet(FORCE_UPDATE_ENDPOINT + "?" + queryString(params));
                    JSONObject root = new JSONObject(response == null ? "{}" : response);
                    JSONObject data = root.optJSONObject("data");
                    boolean value = data != null && data.optBoolean("force_update", false);
                    append("FORCE_UPDATE resultado versão=" + version
                            + " code=" + emptyAsDash(root.optString("code", ""))
                            + " msg=" + emptyAsDash(root.optString("msg", ""))
                            + " force_update=" + value
                            + " response=" + abbreviate(response, 1000));
                    if (value) {
                        forced = true;
                        forcedVersion = version;
                        append("FORCE_UPDATE ativo para " + version + ". Apenas o metadado foi registrado; o MAC especial e o fluxo OTA continuam bloqueados.");
                        break;
                    }
                    if (forceAttempts < versions.length) {
                        try { Thread.sleep(1000L); }
                        catch (InterruptedException interrupted) {
                            Thread.currentThread().interrupt();
                            break;
                        }
                    }
                }

                Map<String, String> config = buildPublicServerParams();
                config.put("firmware_version", otaVersion);
                config.put("firmware_name", otaProject);
                config.put("authcode", "");
                config.put("sign", signWithSecret(config, PUBLIC_SECRET));
                append("FIRMWARE_CONFIG consulta versão=" + otaVersion + " nome=" + otaProject + " authcode=vazio");
                String configResponse = httpGet(FIRMWARE_CONFIG_ENDPOINT + "?" + queryString(config));
                JSONObject configRoot = new JSONObject(configResponse == null ? "{}" : configResponse);
                JSONObject configData = configRoot.optJSONObject("data");
                append("FIRMWARE_CONFIG resultado code=" + emptyAsDash(configRoot.optString("code", ""))
                        + " msg=" + emptyAsDash(configRoot.optString("msg", ""))
                        + " dataKeys=" + (configData == null ? 0 : configData.length())
                        + " id=" + (configData == null ? "-" : String.valueOf(configData.optInt("id", -1)))
                        + " off_list=" + (configData == null ? "-" : emptyAsDash(configData.optString("off_list", "")))
                        + " response=" + abbreviate(configResponse, 1200));
            } catch (Exception error) {
                append("CANAIS ALTERNATIVOS falharam: " + error.getClass().getSimpleName()
                        + ": " + emptyAsDash(error.getMessage()));
            } finally {
                serverSideChannelProbeRunning = false;
                append("CANAIS resumo: force_tentativas=" + forceAttempts
                        + " force_ativo=" + forced
                        + " versão=" + emptyAsDash(forcedVersion));
                append("Nenhum login anônimo foi criado. Se firmware/get_configs exigir authcode, o erro ficará registrado sem nova ação automática.");
                append("POLÍTICA: nenhum download, nenhum 0x03, nenhum bloco de firmware e nenhum TX BLE.");
                append("===== FIM CANAIS ALTERNATIVOS DO SERVIDOR =====");
                setStatus(forced
                        ? "Servidor marcou force_update; nenhuma ação de dispositivo foi executada."
                        : "Consulta de canais alternativos concluída sem alterar o relógio.");
            }
        });
    }

    private void appendHryFineFrameValidation(byte[] frame, int prefix, int command, int key) {
''')

rep('''    /** Exact reconstruction of SignUtils.getSign(map, false, secret). */
    private static String sign(Map<String, String> params) throws Exception {
        params.put("timestamp", String.valueOf(System.currentTimeMillis() / 1000L));
        List<String> keys = new ArrayList<>(params.keySet());
        Collections.sort(keys);
        StringBuilder source = new StringBuilder();
        for (String key : keys) {
            String value = params.get(key);
            if (value != null && !value.isEmpty() && !"0".equals(value)) {
                source.append(key).append('=').append(value).append('&');
            }
        }
        source.append("key=").append(OTA_SECRET);
        MessageDigest digest = MessageDigest.getInstance("MD5");
        // HryFine calls HexUtil.encodeHexStr(digest, false): false means uppercase hex.
        return hexCompact(digest.digest(source.toString().getBytes(StandardCharsets.UTF_8)))
                .toUpperCase(Locale.US);
    }
''', '''    /** Exact reconstruction of SignUtils.getSign(map, false, OTA secret). */
    private static String sign(Map<String, String> params) throws Exception {
        return signWithSecret(params, OTA_SECRET);
    }

    private static String signWithSecret(Map<String, String> params, String secret) throws Exception {
        params.put("timestamp", String.valueOf(System.currentTimeMillis() / 1000L));
        List<String> keys = new ArrayList<>(params.keySet());
        Collections.sort(keys);
        StringBuilder source = new StringBuilder();
        for (String key : keys) {
            String value = params.get(key);
            if (value != null && !value.isEmpty() && !"0".equals(value)) {
                source.append(key).append('=').append(value).append('&');
            }
        }
        source.append("key=").append(secret);
        MessageDigest digest = MessageDigest.getInstance("MD5");
        // HryFine uses uppercase hexadecimal for these signed requests.
        return hexCompact(digest.digest(source.toString().getBytes(StandardCharsets.UTF_8)))
                .toUpperCase(Locale.US);
    }
''')

rep('''    private static Map<String, String> buildOfficialServerParams(String uniqueCode) {
        Map<String, String> params = new LinkedHashMap<>();
        params.put("appid", OTA_APP_KEY);
        params.put("bundle_id", "3");
        params.put("lang", Locale.getDefault().getLanguage());
        params.put("nonce", String.valueOf(new Random().nextInt(1_000_000) + 10_000));
        params.put("unique_code", uniqueCode);
        return params;
    }
''', '''    private static Map<String, String> buildOfficialServerParams(String uniqueCode) {
        Map<String, String> params = new LinkedHashMap<>();
        params.put("appid", OTA_APP_KEY);
        params.put("bundle_id", "3");
        params.put("lang", Locale.getDefault().getLanguage());
        params.put("nonce", String.valueOf(new Random().nextInt(1_000_000) + 10_000));
        params.put("unique_code", uniqueCode);
        return params;
    }

    /** Exact reconstruction of Constans.getPubQueryMap(), without creating an anonymous login. */
    private static Map<String, String> buildPublicServerParams() {
        Map<String, String> params = new LinkedHashMap<>();
        params.put("appid", PUBLIC_APP_KEY);
        params.put("bundle_id", "3");
        params.put("lang", Locale.getDefault().getLanguage());
        params.put("nonce", String.valueOf(new Random().nextInt(1_000_000) + 10_000));
        return params;
    }
''')

path.write_text(src, encoding='utf-8')
