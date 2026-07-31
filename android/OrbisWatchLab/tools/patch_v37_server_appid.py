from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: patch_v37_server_appid.py <MainActivity.java>')
path = Path(sys.argv[1])
src = path.read_text(encoding='utf-8')

src = src.replace('Orbis Watch OTA 5610 v3.6', 'Orbis Watch OTA 5610 v3.7')
src = src.replace('Transição oficial NUS → modo OTA 5610', 'Autenticação oficial appid e transição NUS → OTA')
src = src.replace('Servidor oficial: não consultado', 'Servidor oficial: aguardando consulta appid')

old_meta = '''    private void queryOfficialServerMetadataOnly() {
        if (!nusOtaInfoValidated || otaUniqueCode.isEmpty()) {
            toast("Execute primeiro a consulta OTA pelo NUS e aguarde a resposta completa");
            return;
        }
        officialUpdateAvailable = false;
        append("SERVIDOR: consultando metadados oficiais com o unique_code recebido do G28.");
        ioExecutor.execute(() -> {
            String[] keyNames = {"app_key", "app_id"};
            for (String keyName : keyNames) {
                try {
                    Map<String, String> params = new LinkedHashMap<>();
                    params.put(keyName, OTA_APP_KEY);
                    params.put("unique_code", otaUniqueCode);
                    params.put("sign", sign(params));
                    String response = httpGet(OTA_ENDPOINT + "?" + queryString(params));
                    append("SERVER " + keyName + " → " + abbreviate(response, 1800));
                    if (response != null && response.contains("bin_list")) {
                        JSONObject root = new JSONObject(response);
                        JSONArray bins = findBinList(root);
                        officialUpdateAvailable = bins != null && bins.length() > 0;
                        append("SERVER VALIDADO: bin_list=" + (bins == null ? 0 : bins.length())
                                + " updateAvailable=" + officialUpdateAvailable);
                        setStatus(officialUpdateAvailable
                                ? "Servidor confirmou pacote OTA. Passo 3 liberado."
                                : "Servidor respondeu, mas não há BIN de atualização.");
                        renderOtaStatus();
                        return;
                    }
                } catch (Exception error) {
                    append("SERVER " + keyName + " falhou: " + error.getMessage());
                }
            }
            setStatus("Servidor não confirmou pacote OTA; entrada em OTA permanece bloqueada.");
            append("SERVIDOR: nenhuma resposta válida com bin_list foi obtida.");
            renderOtaStatus();
        });
    }
'''
new_meta = '''    private void queryOfficialServerMetadataOnly() {
        if (!nusOtaInfoValidated || otaUniqueCode.isEmpty()) {
            toast("Execute primeiro a consulta OTA pelo NUS e aguarde a resposta completa");
            return;
        }
        officialUpdateAvailable = false;
        append("SERVIDOR v3.7: usando o nome exato appid retornado pela API e pelo fluxo Constans.getQueryMap().");
        ioExecutor.execute(() -> {
            try {
                Map<String, String> params = new LinkedHashMap<>();
                params.put("appid", OTA_APP_KEY);
                params.put("unique_code", otaUniqueCode);
                params.put("sign", sign(params));
                String response = httpGet(OTA_ENDPOINT + "?" + queryString(params));
                append("SERVER appid → " + abbreviate(response, 2400));
                JSONObject root = new JSONObject(response == null ? "{}" : response);
                String apiCode = root.optString("code", "");
                String apiMessage = root.optString("msg", "");
                append("SERVER RESULTADO: code=" + emptyAsDash(apiCode) + " msg=" + emptyAsDash(apiMessage));
                JSONArray bins = findBinList(root);
                officialUpdateAvailable = bins != null && bins.length() > 0;
                if (bins != null) {
                    append("SERVER VALIDADO: bin_list=" + bins.length()
                            + " updateAvailable=" + officialUpdateAvailable);
                    setStatus(officialUpdateAvailable
                            ? "Servidor confirmou pacote OTA. Passo 3 liberado."
                            : "Servidor autenticou a consulta, mas não há BIN de atualização.");
                } else {
                    append("SERVER SEM BIN_LIST: autenticação/assinatura ainda será determinada pela mensagem acima.");
                    setStatus("Servidor respondeu sem bin_list; entrada em OTA permanece bloqueada.");
                }
            } catch (Exception error) {
                append("SERVER appid falhou: " + error.getMessage());
                setStatus("Falha ao consultar o servidor; entrada em OTA permanece bloqueada.");
            }
            renderOtaStatus();
        });
    }
'''
if old_meta not in src:
    raise SystemExit('metadata method not found')
src = src.replace(old_meta, new_meta)

old_general = '''    private void queryOfficialServer() {
        if (otaUniqueCode.isEmpty()) { toast("Primeiro execute a consulta OTA pelo NUS"); return; }
        append("Consultando servidor oficial experimental com unique_code=" + otaUniqueCode);
        ioExecutor.execute(() -> {
            String[] keyNames = {"app_key", "app_id"};
            for (String keyName : keyNames) {
                try {
                    Map<String, String> params = new LinkedHashMap<>();
                    params.put(keyName, OTA_APP_KEY);
                    params.put("unique_code", otaUniqueCode);
                    params.put("sign", sign(params));
                    String response = httpGet(OTA_ENDPOINT + "?" + queryString(params));
                    append("SERVER " + keyName + " → " + abbreviate(response, 1800));
                    if (response != null && response.contains("bin_list")) {
                        parseJsonText(response);
                        return;
                    }
                } catch (Exception error) {
                    append("SERVER " + keyName + " falhou: " + error.getMessage());
                }
            }
            append("Servidor não aceitou as duas assinaturas reconstruídas. O unique_code foi preservado para uso manual.");
        });
    }
'''
new_general = '''    private void queryOfficialServer() {
        if (otaUniqueCode.isEmpty()) { toast("Primeiro execute a consulta OTA pelo NUS"); return; }
        append("Consultando servidor oficial com parâmetro appid e unique_code validado pelo G28.");
        ioExecutor.execute(() -> {
            try {
                Map<String, String> params = new LinkedHashMap<>();
                params.put("appid", OTA_APP_KEY);
                params.put("unique_code", otaUniqueCode);
                params.put("sign", sign(params));
                String response = httpGet(OTA_ENDPOINT + "?" + queryString(params));
                append("SERVER appid → " + abbreviate(response, 2400));
                if (response != null && response.contains("bin_list")) {
                    parseJsonText(response);
                } else {
                    append("Servidor respondeu sem bin_list; nenhum comando OTA foi liberado.");
                }
            } catch (Exception error) {
                append("SERVER appid falhou: " + error.getMessage());
            }
        });
    }
'''
if old_general not in src:
    raise SystemExit('general server method not found')
src = src.replace(old_general, new_general)

if 'String[] keyNames = {"app_key", "app_id"};' in src:
    raise SystemExit('legacy key loop remains')
if 'params.put("appid", OTA_APP_KEY);' not in src:
    raise SystemExit('appid patch missing')

path.write_text(src, encoding='utf-8')
print('v3.7 appid server patch applied')
