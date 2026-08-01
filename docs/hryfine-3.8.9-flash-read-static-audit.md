# Auditoria estática do `FLASH_READ` HryFine 3.8.9

## Resultado

- Fonte analisada: exportação integral `Hryfine.zip`
- SHA-256: `202900e9776d04d5cf4255ddb9a0bbfe856cab3524c40441a1aa7eba875f01f7`
- Arquivos Smali analisados: **56.787**
- Chamadas encontradas a `IssuedUtil.getSendByte`: **76**
- Chamadas com command normal `0x0A`: **0**
- Ocorrências literais relacionadas a `FLASH_READ`: **1**
- Callbacks BLE com nomes compatíveis com dump/readback/memória: **0**

## Única evidência encontrada

```smali
.field public static final COMMAND_ID_FLASH_READ:B = 0xat
```

Local:

```text
classes6.dex/com/lianhezhuli/hyfit/ble/CommandID.smali:27
```

Não foi encontrado:

- método emissor que use `0x0A` como primeiro argumento de `IssuedUtil.getSendByte`;
- callback para dados de memória;
- bean/evento de dump;
- parser de resposta `DF/0x0A`;
- tela ou fluxo de diagnóstico que execute leitura;
- formato de endereço, tamanho, alinhamento ou fragmentação.

## Conclusão

O HryFine 3.8.9 preserva apenas o nome simbólico do comando. A implementação está ausente ou pertenceu a outra versão/produto. Isso não autoriza inventar um quadro `DF/0x0A`.

Também não se deve confundir esse command ID do protocolo normal com `D5/0x0A` do bootloader 5610. No fluxo OTA confirmado, `D5/0x0A` é a verificação/checksum de uma partição após escrita, e não um readback.

## Próxima etapa de arqueologia

O auditor em `tools/audit_hryfine_flash_read.py` aceita qualquer ZIP ou diretório contendo Smali. A estratégia agora é comparar:

1. versões antigas do HryFine;
2. outros aplicativos oficiais da Shenzhen United Power que reutilizem o mesmo SDK BLE;
3. ferramentas de fábrica/diagnóstico da família 5610;
4. SDKs ou amostras que contenham uma chamada real ao command `0x0A`.

Uma versão candidata só libera teste no relógio depois de revelar:

- command e key exatos;
- largura e endianess do endereço;
- tamanho máximo e alinhamento;
- resposta e fragmentação;
- erro para endereço inválido;
- evidência de que a operação é estritamente de leitura.

## Gate de segurança

Mesmo após recuperar a estrutura, o primeiro teste será limitado a um bloco mínimo, repetido duas vezes e comparado byte a byte. O aplicativo não enviará partições OTA, firmware, finalização, reboot ou qualquer escrita.
