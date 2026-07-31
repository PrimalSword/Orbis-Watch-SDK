from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: fix_v35_java_quotes.py <MainActivity.java>")

path = Path(sys.argv[1])
src = path.read_text(encoding="utf-8")

replacements = {
    'append("  ↳ resposta no FF14 (canal alternativo): ASCII="" + printableAscii(copy) + """);':
        'append("  ↳ resposta no FF14 (canal alternativo): ASCII=" + printableAscii(copy));',
    'append("  ↳ dados OTA não-D6: ASCII="" + printableAscii(copy) + """);':
        'append("  ↳ dados OTA não-D6: ASCII=" + printableAscii(copy));',
    'append("  ↳ FF01 sem cabeçalho D6: ASCII="" + printableAscii(chunk) + """);':
        'append("  ↳ FF01 sem cabeçalho D6: ASCII=" + printableAscii(chunk));',
    '+ " ASCII="" + printableAscii(copy) + """);':
        '+ " ASCII=" + printableAscii(copy));',
}

count = 0
for old, new in replacements.items():
    hits = src.count(old)
    src = src.replace(old, new)
    count += hits

if count != 4:
    raise SystemExit(f"expected to repair 4 Java quote sites, repaired {count}")
if 'ASCII=""' in src:
    raise SystemExit("unrepaired adjacent Java quotes remain")

path.write_text(src, encoding="utf-8")
print(f"repaired {count} v3.5 Java quote sites")
