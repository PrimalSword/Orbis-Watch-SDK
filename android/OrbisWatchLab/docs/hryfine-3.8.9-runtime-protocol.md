# HryFine 3.8.9 / G28 — mapa de protocolo recuperado

## Escopo e cadeia de evidência

- Pacote analisado: `Hryfine.zip`
- SHA-256: `202900e9776d04d5cf4255ddb9a0bbfe856cab3524c40441a1aa7eba875f01f7`
- Projeto: `G28`
- Firmware observado: `V1.5`
- String de identificação: `E06B_G28_WE[G28]_RStyle1_240x240_HryFine`
- Código OTA/NUS: `6800A4B00456312E3503473238`
- A análise usa o smali completo exportado do HryFine 3.8.9 e quadros recebidos do relógio real.

Arquivos principais:

- `classes6.dex/com/lianhezhuli/hyfit/ble/SettingIssuedUtils.smali`
- `classes6.dex/com/lianhezhuli/hyfit/ble/GeneralUtils.smali`
- `classes6.dex/com/lianhezhuli/hyfit/ble/CommandID.smali`
- `classes6.dex/com/lianhezhuli/hyfit/ble/utils/NotifyWriteUtils.smali`
- `classes6.dex/com/lianhezhuli/hyfit/ble/utils/UserInfoAndRemindUtils.smali`
- `classes6.dex/com/lianhezhuli/hyfit/ble/infoutils/BleDataUtils.smali`
- `classes6.dex/com/lianhezhuli/hyfit/ble/enums/DeviceContro.smali`
- `classes6.dex/com/lianhezhuli/hyfit/ble/ota/Cus5610OTAUtils.smali`

## Transporte normal NUS

UUIDs:

- serviço: `6E400001-B5A3-F393-E0A9-E50E24DCCA9F`
- app → relógio: `6E400002-B5A3-F393-E0A9-E50E24DCCA9F`
- relógio → app: `6E400003-B5A3-F393-E0A9-E50E24DCCA9F`

Quadro normal:

| Offset | Campo |
|---:|---|
| 0 | prefixo `DF` (dados/comando) ou `FD` (ACK) |
| 1–2 | comprimento do corpo, big-endian |
| 3 | soma aditiva de 8 bits, excluindo o próprio byte 3 |
| 4 | command ID |
| 5 | versão do protocolo (`01`) |
| 6 | key/action |
| 7–8 | tamanho do payload, big-endian |
| 9… | payload |

Comprimento total: `4 + bodyLength`.

Exemplo de consulta de configurações:

```text
DF 00 05 EE 09 01 00 00 00
```

## Command IDs normais

| ID | Nome recuperado |
|---:|---|
| `01` | OTA legado |
| `02` | escrita de configuração |
| `03` | bind |
| `04` | unbind |
| `05` | dados esportivos |
| `06` | reset |
| `07` | teste de fábrica |
| `08` | alarmes |
| `09` | configurações do dispositivo |
| `0A` | `FLASH_READ` (somente nome; sem uso seguro comprovado) |
| `0B` | teste do dispositivo |
| `0C` | controle relógio → telefone |
| `0D` | restaurar fábrica |
| `0F` | mostrador |
| `10` | medicamento |
| `11` | beber água |
| `12` | notificações de mensagens |
| `13` | OTA novo |
| `14` | sedentário |
| `19` | recursos/capacidades |
| `1A` | funções auxiliares |
| `1F` | código de pareamento BLE |
| `20` | identificação do produto |
| `F0` | consulta de firmware |
| `F3` | informações do dispositivo |

## Consultas somente leitura confirmadas no código

| Função HryFine | Command/key |
|---|---|
| configurações atuais | `09/00` |
| lembrete de água | `11/00` |
| lembrete sedentário | `14/00` |
| recursos do dispositivo | `19/00` |
| identificação do produto | `20/00` |
| suporte social | `1A/03` |
| suporte a pagamento | `1A/05` |
| economia de energia | `1A/07` |
| encerrar “encontrar telefone” | `1A/15` |

No G28, `20/00` produziu ACK `FD`, mas ainda não produziu payload `DF/20`.

## Controles e configurações exatos

### Telefone localizar relógio

`SettingIssuedUtils.findBracelet(boolean)`:

- command `02`
- key `0B`
- payload `01` para ativar, `00` para desativar

### Modo de fotografia

`SettingIssuedUtils.switchPhoto(boolean)`:

- command `02`
- key `0C`
- payload `01` para ativar, `00` para desativar

### Sincronização de hora/RTC

`SettingIssuedUtils.settingSysTime()`:

- command `02`
- key `01`
- payload de 4 bytes

Empacotamento:

```text
b0 = ((year - 2000) << 2) | (month >> 2)
b1 = ((month & 3) << 6) | (day << 1) | (hour >> 4)
b2 = ((hour & 0x0F) << 4) | (minute >> 2)
b3 = ((minute & 3) << 6) | second
```

A versão v3.21 apenas gera uma prévia local desse quadro; não o transmite.

### Beber água — escrita

`SettingIssuedUtils.settingDrinkWater()`:

- command `02`
- key `21`
- payload de 6 bytes:

```text
[lunchBreak, switch, intervalMinutes/15, startTime, endTime, repeatMask]
```

### Sedentário — escrita

`SettingIssuedUtils.settingSedentaryRemind()`:

- command `02`
- key `03`
- payload de 8 bytes:

```text
[lunchBreak, switch, threshold_hi, threshold_lo,
 (intervalMinutes-30)/15, startTime, endTime, repeatMask]
```

## Eventos relógio → telefone (`command 0C`)

O action code fica no `key` (offset 6). Quando há um parâmetro, ele começa no payload (offset 9).

| Action | Evento |
|---:|---|
| `01` | encontrar telefone |
| `02` | tirar foto |
| `03` | abrir modo de fotografia |
| `04` | fechar modo de fotografia |
| `05` | encerrar teste cardíaco |
| `06` | encerrar teste de pressão/sangue |
| `08` | aceitar bind |
| `09` | rejeitar bind |
| `0A` | reproduzir mídia |
| `0B` | pausar mídia |
| `0C` | diminuir volume |
| `0D` | aumentar volume |
| `0E` | encerrar teste de temperatura |
| `0F` | sair de encontrar telefone |
| `10` | encerrar oxigênio no sangue |
| `12` | estado Bluetooth (parâmetro) |
| `13` | solicitar pareamento/bond Android |

Não foi encontrado um comando NUS explícito para “OK Google”. A hipótese mais forte é uso de Bluetooth Classic/HID/headset, mas isso ainda precisa ser comprovado no G28.

## Respostas de lembretes

### `11/00` — beber água

Payload esperado (6 bytes):

```text
[lunchBreak, switch, interval15, startTime, endTime, repeatMask]
```

- intervalo em minutos = `interval15 * 15`
- máscara de repetição = `repeatMask & 0x7F`

### `14/00` — sedentário

Payload esperado (8 bytes):

```text
[lunchBreak, switch, threshold_hi, threshold_lo,
 interval15, startTime, endTime, repeatMask]
```

- threshold = big-endian de 16 bits
- intervalo em minutos = `interval15 * 15 + 30`
- máscara de repetição = `repeatMask & 0x7F`

## Bloco `09/00` de configurações

O payload observado tem 71 bytes. Estrutura recuperada:

1. byte de formato/versão;
2. perfil compacto de 4 bytes;
3. sequência TLV a partir do offset 5.

Perfil:

```text
sex    = profile0 >> 7
age    = profile0 & 0x7F
height = (profile1 << 1) | (profile2 >> 7)
weight = ((profile2 & 0x7F) << 3) | (profile3 >> 5)
```

TLVs reconhecidos:

| Tag | Conteúdo |
|---:|---|
| `02` | meta diária de passos (4 bytes BE) |
| `03` | configuração sedentária (8 bytes) |
| `04` | 11 flags de notificações sociais |
| `05` | monitoramento de sono: switch/início/fim |
| `06` | base: pulso/plataforma/idioma/vibração |
| `07` | levantar para acender: switch/início/fim |
| `08` | frequência cardíaca automática |
| `09` | não perturbe: switch/início/fim |
| `0B` | formato 12/24 horas |
| `0C` | campo de 1 byte ainda sem nome seguro |
| `0D` | Viber |
| `0E` | unidade de temperatura |
| `0F` | Zalo |
| `11` | acender tela o dia todo |
| `12` | não perturbe o dia todo |

## Recursos `19/00`

O payload precisa começar em `AA`. Flags selecionadas recuperadas do parser HryFine:

- byte 1: BLE3, contatos, temperatura, chave 12/24h, unidades, idioma, oxigênio;
- byte 2: mostrador configurável, customizável, envio de mostrador, razão de resolução;
- byte 3: Viber e formato da tela;
- byte 19: sedentário, pagamento, `supportMacXor55`, social, vibração;
- byte 26: HID, DND o dia todo, economia de energia, tipo de pagamento;
- byte 27: encontrar telefone fora do app;
- byte 28: código de pareamento BLE e identificação do produto.

Esse comando é central para decidir se o “OK Google” depende de HID/Classic e para confirmar capacidades de recuperação.

## OTA 5610 confirmado

- MAC normal: `41:42:99:10:58:57`
- MAC bootloader: `41:42:99:10:58:02` (XOR55)
- serviço: `18A8`
- RX: `2AA8` (read/notify)
- TX: `2AA9` (write/write-no-response)
- protocolo: `V1.1`

Consultas seguras já confirmadas:

- `D5/0F` → negociação;
- `D5/01` → identidade.

O próximo comando oficial `0x03` distribui uma tabela de partições originada do `bin_list`. Ele permanece bloqueado porque é uma escrita e ainda não existe manifesto genuíno.

## Restrições de segurança do projeto

Continuam bloqueados:

- comando OTA `0x03`;
- blocos de firmware;
- checksums/finalização;
- reboot de transferência;
- sincronização de RTC real pelo laboratório;
- qualquer tabela de partições inventada;
- uso de `FLASH_READ 0x0A` sem recuperar chamada, payload e semântica completos.

## Arquitetura-alvo

```text
BOOT/RECOVERY original
 ├── relógio + RTC
 ├── BLE NUS de manutenção
 ├── menu local
 │    ├── relógio
 │    ├── DOOM
 │    └── manutenção
 └── saída segura do DOOM sem reflashing
```

A viabilidade de DOOM ainda depende de identificar chipset, RAM, flash, controlador de tela, touch/botão e obter uma imagem/manifesto de firmware válido. Este mapa resolve o protocolo de aplicativo, mas não substitui essas informações de hardware.
