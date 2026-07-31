from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: patch_v38_exact_auth.py <MainActivity.java>')

path = Path(sys.argv[1])
src = path.read_text(encoding='utf-8')

src = src.replace('Orbis Watch OTA 5610 v3.7', 'Orbis Watch OTA 5610 v3.8')
src = src.replace('Autenticação oficial appid e transição NUS → OTA',
                  'Mapa de autenticação HryFine exato e transição NUS → OTA')
src = src.replace('Servidor oficial: aguardando consulta appid',
                  'Servidor oficial: aguardando mapa autenticado completo')

if 'import java.util.Random;' not in src:
    src = src.replace('import java.util.Map;\n', 'import java.util.Map;\nimport java.util.Random;\n')

old_meta_intro = '''        officialUpdateAvailable = false;
        append("SERVIDOR v3.7: usando o nome exato appid retornado pela API e pelo fluxo Constans.getQueryMap().");
        ioExecutor.execute(() -> {
            try {
                Map<String, String> params = new LinkedHashMap<>();
                params.put("appid", OTA_APP_KEY);
                params.put("unique_code", otaUniqueCode);
                params.put("sign", sign(params));
                String response = httpGet(OTA_ENDPOINT + "?" + queryString(params));
'''
new_meta_intro = '''        officialUpdateAvailable = false;
        append("SERVIDOR v3.8: reproduzindo Constans.getQueryMap() e SignUtils.getSign() sem campos presumidos.");
        ioExecutor.execute(() -> {
            try {
                Map<String, String> params = buildOfficialServerParams(otaUniqueCode);
                params.put("sign", sign(params));
                append("SERVER AUTH MAP: appid=" + params.get("appid")
                        + " bundle_id=" + params.get("bundle_id")
                        + " lang=" + params.get("lang")
                        + " nonce=" + params.get("nonce")
                        + " timestamp=" + params.get("timestamp"));
                String response = httpGet(OTA_ENDPOINT + "?" + queryString(params));
'''
if old_meta_intro not in src:
    raise SystemExit('v3.7 metadata auth block not found')
src = src.replace(old_meta_intro, new_meta_intro)

src = src.replace('append("SERVER appid → " + abbreviate(response, 2400));',
                  'append("SERVER auth exata → " + abbreviate(response, 2400));')
src = src.replace('append("SERVER appid falhou: " + error.getMessage());',
                  'append("SERVER auth exata falhou: " + error.getMessage());')

old_general_intro = '''        append("Consultando servidor oficial com parâmetro appid e unique_code validado pelo G28.");
        ioExecutor.execute(() -> {
            try {
                Map<String, String> params = new LinkedHashMap<>();
                params.put("appid", OTA_APP_KEY);
                params.put("unique_code", otaUniqueCode);
                params.put("sign", sign(params));
                String response = httpGet(OTA_ENDPOINT + "?" + queryString(params));
'''
new_general_intro = '''        append("Consultando servidor oficial com o mapa exato do HryFine e unique_code validado pelo G28.");
        ioExecutor.execute(() -> {
            try {
                Map<String, String> params = buildOfficialServerParams(otaUniqueCode);
                params.put("sign", sign(params));
                append("SERVER AUTH MAP: appid=" + params.get("appid")
                        + " bundle_id=" + params.get("bundle_id")
                        + " lang=" + params.get("lang")
                        + " nonce=" + params.get("nonce")
                        + " timestamp=" + params.get("timestamp"));
                String response = httpGet(OTA_ENDPOINT + "?" + queryString(params));
'''
if old_general_intro not in src:
    raise SystemExit('v3.7 general auth block not found')
src = src.replace(old_general_intro, new_general_intro)

old_sign = '''    private static String sign(Map<String, String> params) throws Exception {
        List<String> keys = new ArrayList<>(params.keySet());
        Collections.sort(keys);
        StringBuilder source = new StringBuilder();
        for (String key : keys) source.append(key).append('=').append(params.get(key)).append('&');
        source.append(OTA_SECRET);
        MessageDigest digest = MessageDigest.getInstance("MD5");
        return hexCompact(digest.digest(source.toString().getBytes(StandardCharsets.UTF_8))).toLowerCase(Locale.US);
    }
'''
new_sign = '''    /** Exact reconstruction of Constans.getQueryMap(appid). */
    private static Map<String, String> buildOfficialServerParams(String uniqueCode) {
        Map<String, String> params = new LinkedHashMap<>();
        params.put("appid", OTA_APP_KEY);
        params.put("bundle_id", "3");
        params.put("lang", Locale.getDefault().getLanguage());
        params.put("nonce", String.valueOf(new Random().nextInt(1_000_000) + 10_000));
        params.put("unique_code", uniqueCode);
        return params;
    }

    /** Exact reconstruction of SignUtils.getSign(map, false, secret). */
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
        return hexCompact(digest.digest(source.toString().getBytes(StandardCharsets.UTF_8)))
                .toLowerCase(Locale.US);
    }
'''
if old_sign not in src:
    raise SystemExit('legacy sign method not found')
src = src.replace(old_sign, new_sign)

required = [
    'params.put("bundle_id", "3")',
    'params.put("lang", Locale.getDefault().getLanguage())',
    'params.put("nonce", String.valueOf(new Random().nextInt(1_000_000) + 10_000))',
    'params.put("timestamp", String.valueOf(System.currentTimeMillis() / 1000L))',
    'source.append("key=").append(OTA_SECRET)',
    'Map<String, String> params = buildOfficialServerParams(otaUniqueCode)',
]
for marker in required:
    if marker not in src:
        raise SystemExit('missing exact auth marker: ' + marker)

if 'source.append(OTA_SECRET);' in src:
    raise SystemExit('legacy invalid signing suffix remains')

path.write_text(src, encoding='utf-8')
print('v3.8 exact HryFine authentication patch applied')
