# HryFine 3.8.9 — auditoria dos comandos de diagnóstico

## Escopo

A exportação integral do HryFine 3.8.9 foi examinada estaticamente, incluindo 56.787 arquivos Smali e todas as chamadas encontradas a `IssuedUtil.getSendByte(...)`.

Foram localizadas 76 chamadas emissoras. A distribuição dos command IDs comprovados foi:

```text
02×42, 03×1, 04×1, 05×3, 08×1, 09×1, 0D×1, 0E×1,
0F×7, 10×1, 11×1, 12×1, 13×2, 14×1, 19×1, 1A×5,
1F×2, 20×1, F0×1, F1×1 e F3×1.
```

## Comandos dormentes

As constantes abaixo existem em `CommandID.smali`, mas não possuem emissor real, parser de resposta ou fluxo de interface no APK analisado:

| Command ID | Nome simbólico | Emissores comprovados | Parser comprovado |
|---:|---|---:|---:|
| `07` | `FACTORY_TEST` | 0 | 0 |
| `0A` | `FLASH_READ` | 0 | 0 |
| `0B` | `DEVICE_TEST` | 0 | 0 |

A presença do nome não estabelece key, payload, endereço, comprimento, alinhamento ou segurança operacional. Nenhum desses comandos deve ser transmitido por inferência.

## Fluxo real `F0/F1/F3`

O command `F0` não é uma consulta de firmware nem um diagnóstico de memória.

`NotifyWriteUtils.getVerification()`:

1. gera um UUID aleatório;
2. remove os hífens;
3. usa oito bytes ASCII como payload;
4. calcula `verificationCode` somando `((byte XOR 0xFF) & 0xFF)`;
5. envia `F0/00` com esses oito bytes.

Quando o HryFine recebe uma resposta `DF/F0`, compara o byte de verificação recebido com `verificationCode`. Se coincidir, envia `F1/00` com payload `00`.

A resposta `F1` conduz à consulta `F3` de informações do dispositivo ou a uma variação do fluxo de bind, conforme as capacidades detectadas.

Resumo:

```text
F0 → desafio/verificação
F1 → confirmação da verificação
F3 → informações do dispositivo
```

## Consequência para o G28

- `0x07` e `0x0B` não fornecem hoje um caminho comprovado para identificar chipset, flash, LCD ou touch.
- `0x0A` permanece sem implementação utilizável.
- `F0/F1` não devem ser tratados como ferramentas de diagnóstico.
- O Orbis não envia nenhum desses quadros na v3.24; apenas mostra esta auditoria localmente.

## Gate de segurança

Um comando dormente somente poderá ser testado se outra implementação legítima revelar, de forma verificável:

- command e key;
- payload exato;
- semântica dos campos;
- formato da resposta;
- tratamento de erro;
- evidência de ausência de escrita ou reset.

Até lá, partições OTA, firmware, RTC real, finalização, reboot e qualquer leitura de flash inventada permanecem bloqueados.
