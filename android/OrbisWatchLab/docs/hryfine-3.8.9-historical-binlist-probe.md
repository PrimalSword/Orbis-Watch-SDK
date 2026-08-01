# G28 — consulta histórica limitada de `bin_list`

## Evidência atual

A identidade real devolvida pelo relógio é:

```text
68 00 A4 B0 04 56 31 2E 35 03 47 32 38
```

Interpretação confirmada:

- prefixo/modelo: `68 00 A4 B0`;
- comprimento da versão: `04`;
- versão: `V1.5`;
- comprimento do projeto: `03`;
- projeto: `G28`.

A consulta oficial para `6800A4B00456312E3503473238` autentica corretamente e retorna `code=success`, porém `data={}` e nenhuma `bin_list`. Isso corresponde ao caminho do HryFine para dispositivo sem atualização publicada para a versão informada.

## Hipótese testável

Como a versão integra o próprio `unique_code`, o servidor pode manter um pacote de atualização acessível apenas quando recebe uma versão anterior do mesmo hardware/projeto. A v3.23 reconstrói somente estas cinco identidades:

```text
V1.4 → 6800A4B00456312E3403473238
V1.3 → 6800A4B00456312E3303473238
V1.2 → 6800A4B00456312E3203473238
V1.1 → 6800A4B00456312E3103473238
V1.0 → 6800A4B00456312E3003473238
```

A consulta:

- usa o endpoint e a assinatura oficiais já recuperados do HryFine;
- faz no máximo cinco requisições GET;
- aguarda 1,2 segundo entre tentativas;
- encerra no primeiro `bin_list` não vazio;
- apenas registra e audita metadados;
- não baixa `bin_file`;
- não envia nenhum quadro BLE;
- não envia tabela OTA `0x03`;
- não altera RTC, firmware ou partições.

## Auditoria estática adicional

O APK define `COMMAND_ID_FLASH_READ = 0x0A`, mas a busca integral nos oito DEX não encontrou chamada que use `0x0A` como primeiro argumento de `IssuedUtil.getSendByte(...)`. Portanto, o símbolo existe, porém não há formato de solicitação, payload ou fluxo de resposta implementado no HryFine 3.8.9 analisado. Ele continua bloqueado e não deve ser tratado como caminho de leitura segura da flash.

O APK também inclui `com/bluetrum/abpartool` e `libabpartool.so`. Isso comprova que o aplicativo contém ferramenta da Bluetrum para algum fluxo suportado, mas não prova, isoladamente, que o SoC específico do G28 seja Bluetrum.

## Critério de avanço

Se uma consulta histórica devolver `bin_list`, os próximos passos são:

1. preservar o JSON integral;
2. validar `part_id`, `part_addr`, `part_len` e `bin_size`;
3. verificar sobreposições e coerência dos tamanhos;
4. baixar os BINs apenas para análise offline, nunca para gravação automática;
5. identificar arquitetura, cabeçalhos, vetores, strings e mapa de memória;
6. só considerar escrita após existir imagem de recuperação e mapa de partições independentemente validados.
