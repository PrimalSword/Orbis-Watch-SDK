from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: patch_v310_server_latest.py <MainActivity.java>')

path = Path(sys.argv[1])
src = path.read_text(encoding='utf-8')

src = src.replace('Orbis Watch OTA 5610 v3.9', 'Orbis Watch OTA 5610 v3.10')
src = src.replace(
    'Assinatura MD5 hexadecimal oficial e transição NUS → OTA',
    'Servidor oficial autenticado e estado real de atualização',
)
src = src.replace(
    'SERVIDOR v3.8: reproduzindo Constans.getQueryMap() e SignUtils.getSign() sem campos presumidos.',
    'SERVIDOR v3.10: autenticação oficial validada; consultando o pacote publicado para o unique_code.',
)

old = '''                } else {
                    append("SERVER SEM BIN_LIST: autenticação/assinatura ainda será determinada pela mensagem acima.");
                    setStatus("Servidor respondeu sem bin_list; entrada em OTA permanece bloqueada.");
                }
'''
new = '''                } else if ("success".equalsIgnoreCase(apiCode)) {
                    JSONObject apiData = root.optJSONObject("data");
                    int dataKeys = apiData == null ? -1 : apiData.length();
                    append("SERVER AUTENTICADO: resposta success sem bin_list (dataKeys=" + dataKeys + "). "
                            + "O fluxo oficial do HryFine trata este resultado como dispositivo já na versão mais recente.");
                    setStatus("Servidor oficial autenticado: nenhum pacote OTA publicado para "
                            + emptyAsDash(otaProject) + " " + emptyAsDash(otaVersion) + ".");
                } else {
                    append("SERVER SEM BIN_LIST: resposta não autenticada ou formato inesperado; code="
                            + emptyAsDash(apiCode));
                    setStatus("Servidor respondeu sem pacote OTA; entrada em OTA permanece bloqueada.");
                }
'''
if old not in src:
    raise SystemExit('legacy no-bin-list status block not found')
src = src.replace(old, new, 1)

old_general = '''                if (response != null && response.contains("bin_list")) {
                    parseJsonText(response);
                } else {
                    append("Servidor respondeu sem bin_list; nenhum comando OTA foi liberado.");
                }
'''
new_general = '''                if (response != null && response.contains("bin_list")) {
                    parseJsonText(response);
                } else if (response != null && response.contains("\\\"code\\\":\\\"success\\\"")) {
                    append("Servidor autenticado, mas não há pacote OTA publicado para este unique_code.");
                } else {
                    append("Servidor respondeu sem bin_list; nenhum comando OTA foi liberado.");
                }
'''
if old_general not in src:
    raise SystemExit('general no-bin-list block not found')
src = src.replace(old_general, new_general, 1)

required = [
    'Orbis Watch OTA 5610 v3.10',
    'SERVER AUTENTICADO: resposta success sem bin_list',
    'já na versão mais recente',
    'nenhum pacote OTA publicado para',
]
for marker in required:
    if marker not in src:
        raise SystemExit('missing v3.10 marker: ' + marker)

if 'autenticação/assinatura ainda será determinada' in src:
    raise SystemExit('obsolete ambiguous signature message remains')

path.write_text(src, encoding='utf-8')
print('v3.10 authenticated-latest-state patch applied')
