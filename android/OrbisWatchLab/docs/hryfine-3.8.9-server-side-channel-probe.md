# HryFine 3.8.9 — canais alternativos do servidor

## Motivação

O endpoint oficial `api/hry/get_update` autenticou corretamente o G28, mas devolveu `data={}` para a versão real `V1.5` e também para as versões históricas reconstruídas `V1.4` até `V1.0`.

A análise estática do HryFine revelou dois canais adicionais que não baixam firmware por si mesmos:

- `https://ota.lianhezhuli.com/api/hry/force_update`
- `https://app.howruf.com/api/firmware/get_configs`

## `force_update`

O HryFine chama esse endpoint imediatamente após obter o `unique_code` OTA. A resposta contém apenas um booleano:

```json
{
  "force_update": false
}
```

Quando verdadeiro, o aplicativo ativa um fluxo especial de atualização e procura um MAC fixo de fábrica. A v3.25 **não executa esse fluxo**. Ela apenas consulta e registra o booleano para:

- a identidade real `V1.5/G28`;
- no máximo cinco identidades históricas `V1.4` até `V1.0`;
- encerrando a busca caso encontre `force_update=true`.

## `firmware/get_configs`

O HryFine envia:

```text
firmware_version = V1.5
firmware_name    = G28
```

A resposta esperada usa o bean `FirmwareConfigBean`, com os campos:

```text
id
off_list
```

Esse endpoint não fornece `bin_list`, endereços de partição ou arquivos de firmware. Ele pode, contudo, confirmar que a combinação de firmware/projeto existe no cadastro de configuração do aplicativo.

O endpoint normalmente recebe `authcode`. A v3.25 não cria login anônimo e não reutiliza credenciais do HryFine. Ela envia `authcode` vazio, com a assinatura exata do aplicativo, e registra a resposta ou eventual rejeição.

## Limites de segurança

A v3.25:

- não baixa `bin_file`;
- não cria login anônimo;
- não transmite BLE durante a consulta;
- não entra no bootloader;
- não envia tabela `0x03`;
- não envia firmware, checksum, finalização ou reboot;
- não altera RTC, configurações ou flash do relógio.

## Interpretação

- `force_update=false` em todas as versões: o canal especial de fábrica não está habilitado para o G28 consultado.
- `force_update=true`: existe um fluxo especial registrado no servidor, mas isso não prova que haja uma imagem acessível pelo endpoint público.
- `firmware/get_configs` com `data` válido: confirma cadastro da combinação `V1.5/G28`, não a presença de firmware.
- erro de autenticação no `firmware/get_configs`: indica que será necessário decidir separadamente se vale criar um login anônimo controlado; a v3.25 não faz isso automaticamente.
