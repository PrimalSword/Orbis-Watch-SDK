# HryFine 3.8.9 — fluxo OTA, `bin_list` e auditoria segura do G28

## Resposta direta

O HryFine contém **a definição e o parser de `bin_list`**, mas não contém uma `bin_list` concreta do G28 nem os arquivos de firmware correspondentes dentro do APK.

A lista concreta é recebida dinamicamente do servidor oficial:

```text
https://ota.lianhezhuli.com/api/hry/get_update
```

A requisição usa o `unique_code` obtido do relógio e uma assinatura MD5 reconstruída do próprio aplicativo. Quando o servidor não oferece atualização para aquele código, a resposta pode autenticar normalmente e vir sem `bin_list`.

## Cadeia de evidência

Pacote analisado:

- arquivo: `Hryfine.zip`
- SHA-256: `202900e9776d04d5cf4255ddb9a0bbfe856cab3524c40441a1aa7eba875f01f7`
- versão observada: HryFine 3.8.9
- projeto do relógio: G28
- firmware: V1.5
- `unique_code`: `6800A4B00456312E3503473238`

Classes principais:

- `network/bean/OtaUpdateInfo.smali`
- `network/bean/OtaUpdateInfo$BinListBean.smali`
- `network/request/Request.smali`
- `network/request/RequestUtils.smali`
- `function/device/DeviceOtaActivity.smali`
- `ble/ota/Cus5610OTAUtils.smali`
- `ble/ota/Cus5610CommandUtils.smali`
- `ble/utils/AckPackageConfigUtils.smali`
- `ble/utils/NotifyWriteUtils.smali`

## O que existe no APK

O objeto `OtaUpdateInfo` possui:

```text
id
name
status
show_tips
unique_code
bin_list[]
```

Cada item de `bin_list` possui:

```text
id
hry_id
part_id
part_addr
part_len
bin_file
bin_size
status
is_force
is_test
is_white
```

Esses campos formam o manifesto que o aplicativo espera receber. Eles não são preenchidos por valores fixos no APK.

## O que não existe no APK

A busca integral pelo pacote exportado não encontrou uma imagem de firmware do G28 em `.bin`, `.fw`, `.img`, `.hex` ou formato equivalente.

O único arquivo com extensão `.bin` encontrado foi:

```text
DebugProbesKt.bin
```

Ele é um recurso interno do Kotlin e não é firmware do relógio.

Portanto, desmontar o APK revela o formato do manifesto e o protocolo, mas não entrega automaticamente a imagem V1.5 nem uma atualização futura.

## Requisição oficial

O HryFine cria o mapa com:

```text
appid=oaa648257e8
bundle_id=3
lang=<idioma>
nonce=<aleatório>
unique_code=<código do relógio>
timestamp=<Unix seconds>
sign=<MD5 maiúsculo>
```

A assinatura é calculada ordenando as chaves, ignorando valores vazios ou `0`, concatenando:

```text
chave=valor&...&key=ead8ff5fe2f9385b55e6e509cf311a35
```

Depois aplica MD5 e usa hexadecimal maiúsculo.

## Comportamento oficial quando `bin_list` chega

`DeviceOtaActivity` executa esta sequência:

1. recebe `OtaUpdateInfo`;
2. verifica se `bin_list` existe e possui ao menos um item;
3. ordena os itens por `part_id`;
4. baixa cada `bin_file` para o diretório privado `files/ota/`;
5. cria `OtaBean(part_id, caminho_local, id)` para cada arquivo;
6. instancia `Cus5610OTAUtils` com a lista de metadados e os caminhos baixados;
7. constrói a tabela de partições do comando OTA `0x03`.

Se `bin_list` estiver ausente ou vazio, o botão de atualização é desabilitado e o fluxo de download não inicia.

## Estrutura da tabela de partições

`Cus5610OTAUtils.sendPartitionTable()` cria nove bytes por item:

```text
part_id              1 byte
part_addr big-endian 4 bytes
part_len  big-endian 4 bytes
```

Depois envia esses registros como payload do comando OTA `D5/0x03`.

Essa tabela não deve ser inventada. `part_addr` e `part_len` precisam vir de um manifesto genuíno ou de uma imagem oficial validada independentemente.

## ACK normal `FD`

A análise de `AckPackageConfigUtils` e `NotifyWriteUtils.handleAck()` corrige a interpretação dos ACKs curtos.

Formato observado:

```text
offset 0      FD
offsets 1–2   body length = 5
offset 3      checksum aditivo
offset 4      command
offset 5      command key original
offsets 6–7   metadado de 16 bits ignorado pelo parser HryFine
offset 8      status
```

O HryFine considera:

```text
status == 1  → sucesso
status != 1  → não sucesso
```

Exemplo real do G28:

```text
FD 00 05 25 19 00 00 09 01
```

Interpretação correta:

```text
command=0x19
key=0x00
meta_opaque=0x0009
status=1 (sucesso)
```

Os bytes `09 01` não são tamanho de payload. O ACK não carrega payload DF.

## Biblioteca Bluetrum

O APK contém:

```text
com/bluetrum/abpartool/ParTool
libabpartool.so
```

A biblioteca é chamada pelo editor de mostradores para converter imagem bruta em formato `.par`. Isso é uma pista forte de que o ecossistema HryFine suporta hardware Bluetrum, mas, isoladamente, não prova que o G28 específico use um determinado SoC Bluetrum.

A assinatura OTA `5610` e a presença dessa biblioteca fortalecem a hipótese, mas a confirmação do processador ainda exige evidência ligada ao próprio firmware ou ao manifesto do G28.

## Situação do G28

A consulta oficial já observada para:

```text
6800A4B00456312E3503473238
```

foi autenticada, mas não devolveu `bin_list`. A explicação compatível com o fluxo do próprio HryFine é que não havia um pacote de atualização publicado para essa identidade naquele momento.

Isso não significa que o servidor nunca terá uma lista. Significa apenas que a lista não está embutida no aplicativo e não foi oferecida para esse código na consulta realizada.

## Política da v3.22

A v3.22:

- reconhece corretamente ACKs `FD`;
- consulta o servidor oficial com o mesmo formato do HryFine;
- se aparecer `bin_list`, imprime os campos de cada item;
- verifica IDs, tamanhos, intervalos e sobreposição de partições;
- não baixa `bin_file`;
- não envia `0x03`;
- não transmite firmware, checksum final, finalização ou reboot.

## Próxima evidência necessária

Para avançar até firmware customizado preservando relógio e recuperação, ainda precisamos de pelo menos uma destas fontes:

- uma `bin_list` oficial futura do G28;
- arquivos baixados pelo HryFine durante uma atualização real;
- cache privado legítimo do próprio aplicativo após uma atualização;
- uma imagem oficial de recuperação;
- documentação ou toolchain do SoC confirmado.
