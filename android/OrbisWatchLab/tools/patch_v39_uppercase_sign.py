from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: patch_v39_uppercase_sign.py <MainActivity.java>')

path = Path(sys.argv[1])
src = path.read_text(encoding='utf-8')

src = src.replace('Orbis Watch OTA 5610 v3.8', 'Orbis Watch OTA 5610 v3.9')
src = src.replace('Mapa de autenticação HryFine exato e transição NUS → OTA',
                  'Assinatura MD5 hexadecimal oficial e transição NUS → OTA')

old = '''        return hexCompact(digest.digest(source.toString().getBytes(StandardCharsets.UTF_8)))
                .toLowerCase(Locale.US);
'''
new = '''        // HryFine calls HexUtil.encodeHexStr(digest, false): false means uppercase hex.
        return hexCompact(digest.digest(source.toString().getBytes(StandardCharsets.UTF_8)))
                .toUpperCase(Locale.US);
'''
if old not in src:
    raise SystemExit('lowercase signature block not found')
src = src.replace(old, new)

needle = '''                append("SERVER AUTH MAP: appid=" + params.get("appid")
                        + " bundle_id=" + params.get("bundle_id")
                        + " lang=" + params.get("lang")
                        + " nonce=" + params.get("nonce")
                        + " timestamp=" + params.get("timestamp"));
'''
replacement = needle + '''                append("SERVER SIGN FORMAT: MD5 hexadecimal MAIÚSCULO, conforme HexUtil.encodeHexStr(..., false).");
'''
count = src.count(needle)
if count != 2:
    raise SystemExit(f'expected 2 auth-map log sites, found {count}')
src = src.replace(needle, replacement)

sign_start = src.find('    private static String sign(Map<String, String> params) throws Exception {')
if sign_start < 0:
    raise SystemExit('sign method not found')
sign_end = src.find('\n    }', sign_start)
if sign_end < 0:
    raise SystemExit('sign method end not found')
sign_body = src[sign_start:sign_end]
if '.toLowerCase(Locale.US);' in sign_body:
    raise SystemExit('lowercase signature conversion remains in sign method')
if '.toUpperCase(Locale.US);' not in sign_body:
    raise SystemExit('uppercase signature conversion missing in sign method')

path.write_text(src, encoding='utf-8')
print('v3.9 uppercase HryFine signature patch applied')
