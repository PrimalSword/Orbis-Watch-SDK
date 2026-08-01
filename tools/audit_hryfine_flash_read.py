#!/usr/bin/env python3
"""Audit decompiled HryFine smali for evidence of normal-protocol flash read command 0x0A.

This script is deliberately static-only. It never connects to a device and never emits BLE frames.
It accepts either a directory or a ZIP containing .smali files.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import sys
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterator

COMMAND = 0x0A

METHOD_RE = re.compile(r"^\.method\s+(.*)$")
END_METHOD_RE = re.compile(r"^\.end method")
CONST_RE = re.compile(
    r"^\s*const(?:/4|/16|/high16|/wide(?:/16|/32|/high16)?|)?\s+([vp]\d+),\s+(-?0x[0-9a-fA-F]+|-?\d+)"
)
MOVE_RE = re.compile(r"^\s*move(?:-object|-wide|/from16|/16)?\s+([vp]\d+),\s+([vp]\d+)")
CALL_RE = re.compile(
    r"invoke-static\s+\{([^}]*)\},\s+Lcom/lianhezhuli/hyfit/ble/IssuedUtil;->getSendByte\(([^)]*)\)\[B"
)
FLASH_TEXT_RE = re.compile(r"FLASH_READ|COMMAND_ID_FLASH_READ|flash[_ ]?read", re.I)
CALLBACK_RE = re.compile(r"\.method\s+.*(?:flash[_ ]?read|memory|dump|readback)", re.I)


@dataclass
class Evidence:
    file: str
    line: int
    method: str
    kind: str
    text: str
    first_arg_value: int | None = None


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def iter_smali(source: Path) -> Iterator[tuple[str, str]]:
    if source.is_dir():
        for p in source.rglob("*.smali"):
            yield str(p.relative_to(source)), p.read_text(errors="replace")
        return
    if not zipfile.is_zipfile(source):
        raise ValueError(f"Fonte não é diretório nem ZIP válido: {source}")
    with zipfile.ZipFile(source) as zf:
        for name in zf.namelist():
            if name.endswith(".smali"):
                with zf.open(name) as f:
                    yield name, io.TextIOWrapper(f, encoding="utf-8", errors="replace").read()


def audit(source: Path) -> dict:
    evidences: list[Evidence] = []
    smali_count = 0
    call_count = 0
    command_0a_calls = 0
    callback_candidates = 0

    for name, text in iter_smali(source):
        smali_count += 1
        regs: dict[str, int] = {}
        method = "<fora de método>"
        for lineno, line in enumerate(text.splitlines(), 1):
            m = METHOD_RE.match(line)
            if m:
                method = m.group(1)
                regs = {}
            elif END_METHOD_RE.match(line):
                method = "<fora de método>"
                regs = {}

            m = CONST_RE.match(line)
            if m:
                try:
                    regs[m.group(1)] = int(m.group(2), 0)
                except ValueError:
                    pass

            m = MOVE_RE.match(line)
            if m:
                dst, src = m.groups()
                if src in regs:
                    regs[dst] = regs[src]
                else:
                    regs.pop(dst, None)

            if FLASH_TEXT_RE.search(line):
                evidences.append(Evidence(name, lineno, method, "literal", line.strip()))

            if "/com/lianhezhuli/hyfit/ble/" in ("/" + name) and CALLBACK_RE.search(line):
                callback_candidates += 1
                evidences.append(Evidence(name, lineno, method, "callback-candidate", line.strip()))

            m = CALL_RE.search(line)
            if m:
                call_count += 1
                args = [a.strip() for a in m.group(1).split(",") if a.strip()]
                first = regs.get(args[0]) if args else None
                if first == COMMAND:
                    command_0a_calls += 1
                    evidences.append(Evidence(name, lineno, method, "sender-0x0A", line.strip(), first))

    literal_count = sum(1 for e in evidences if e.kind == "literal")
    return {
        "source": str(source),
        "source_sha256": sha256(source) if source.is_file() else None,
        "smali_files": smali_count,
        "issuedutil_getSendByte_calls": call_count,
        "normal_protocol_command_0x0A_senders": command_0a_calls,
        "flash_read_literal_occurrences": literal_count,
        "callback_candidates": callback_candidates,
        "safe_conclusion": (
            "Nenhum emissor ativo do comando normal 0x0A foi comprovado estaticamente. Não transmita um quadro inventado."
            if command_0a_calls == 0
            else "Existe ao menos um possível emissor; é necessária revisão manual do fluxo antes de qualquer teste no dispositivo."
        ),
        "evidence": [asdict(e) for e in evidences],
    }


def render_markdown(result: dict) -> str:
    lines = [
        "# Auditoria estática do `FLASH_READ` HryFine",
        "",
        f"- Fonte: `{result['source']}`",
        f"- SHA-256: `{result.get('source_sha256') or 'diretório'}`",
        f"- Arquivos Smali: **{result['smali_files']}**",
        f"- Chamadas a `IssuedUtil.getSendByte`: **{result['issuedutil_getSendByte_calls']}**",
        f"- Emissores comprovados com command `0x0A`: **{result['normal_protocol_command_0x0A_senders']}**",
        f"- Ocorrências literais relacionadas a `FLASH_READ`: **{result['flash_read_literal_occurrences']}**",
        f"- Candidatos de callback por nome: **{result['callback_candidates']}**",
        "",
        "## Conclusão segura",
        "",
        result["safe_conclusion"],
        "",
        "O comando `0x0A` do protocolo normal não deve ser confundido com `D5/0x0A` do bootloader 5610, que pertence ao fluxo de verificação após escrita.",
        "",
        "## Evidências",
        "",
    ]
    if not result["evidence"]:
        lines.append("Nenhuma evidência textual encontrada.")
    else:
        for e in result["evidence"]:
            lines.append(f"- `{e['file']}:{e['line']}` — **{e['kind']}** — `{e['text']}`")
    lines += [
        "",
        "## Gate antes de qualquer teste no relógio",
        "",
        "1. Recuperar command/key e payload exatos de uma implementação real.",
        "2. Confirmar largura e endianess do endereço.",
        "3. Confirmar limite, alinhamento e fragmentação da resposta.",
        "4. Confirmar erro para endereço inválido e ausência de efeitos colaterais.",
        "5. Só então testar um bloco mínimo, repetir a leitura e comparar os bytes.",
        "",
        "Esta auditoria é apenas estática e não transmite BLE.",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("source", type=Path)
    ap.add_argument("--json", type=Path)
    ap.add_argument("--markdown", type=Path)
    args = ap.parse_args()
    try:
        result = audit(args.source)
    except Exception as exc:
        print(f"erro: {exc}", file=sys.stderr)
        return 2
    if args.json:
        args.json.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if args.markdown:
        args.markdown.write_text(render_markdown(result), encoding="utf-8")
    print(json.dumps({k: result[k] for k in result if k != "evidence"}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
