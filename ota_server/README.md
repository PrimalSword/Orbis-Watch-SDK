# Orbis Watch OTA Server

Servidor independente para catálogo, verificação e distribuição de firmware do Orbis Watch SDK.

## Estado de segurança

Esta versão opera em modo **metadados e download somente**. Toda resposta contém `transport_authorized: false`. O servidor não envia comandos BLE, não inicia o modo OTA e não autoriza gravação no relógio.

O manifesto inicial do projeto `G28` está desativado. Não altere `enabled` para `true` sem:

1. obter um firmware genuíno e compatível com o projeto `G28`;
2. confirmar tamanho, MD5 e SHA-256;
3. validar o protocolo completo de transferência 5610, inclusive tabela, blocos, ACK/NACK, checksum e finalização;
4. determinar se o bootloader exige assinatura criptográfica do fabricante.

## Execução local

```bash
cd ota_server
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
mkdir -p firmware
uvicorn server:app --host 0.0.0.0 --port 8080
```

No Windows, ative o ambiente com `.venv\\Scripts\\activate`.

Verifique:

```bash
curl http://localhost:8080/health
curl "http://localhost:8080/api/v1/ota/check?project=G28&current_version=V1.5"
```

## Autenticação opcional

Defina um token antes de iniciar o servidor:

```bash
export ORBIS_OTA_TOKEN='troque-por-um-token-forte'
```

Depois, envie:

```bash
curl -H "Authorization: Bearer troque-por-um-token-forte" \
  "http://localhost:8080/api/v1/ota/check?project=G28&current_version=V1.5"
```

## Cadastro de firmware

Coloque o arquivo em `ota_server/firmware/` e edite `manifests/G28.json`. O servidor calcula tamanho, MD5 e SHA-256 diretamente do arquivo; esses valores não são confiados ao manifesto.

Exemplo de release:

```json
{
  "project": "G28",
  "version": "V1.6",
  "filename": "G28_V1.6.bin",
  "enabled": false,
  "notes": "Firmware original capturado e ainda não liberado para transporte",
  "signature_required": null
}
```

Mesmo com `enabled: true`, o servidor continuará retornando `transport_authorized: false`. A liberação da gravação pertence a uma fase posterior do cliente BLE, após validação do protocolo e da autenticidade do firmware.

## Docker

```bash
docker build -t orbis-watch-ota ota_server
docker run --rm -p 8080:8080 \
  -e ORBIS_OTA_TOKEN='troque-por-um-token-forte' \
  -v "$PWD/ota_server/manifests:/app/manifests:ro" \
  -v "$PWD/ota_server/firmware:/app/firmware:ro" \
  orbis-watch-ota
```

## Endpoints

- `GET /health`
- `GET /api/v1/ota/check?project=G28&current_version=V1.5`
- `GET /api/v1/ota/manifest/G28`
- `GET /firmware/<arquivo.bin>`
- `GET /docs` para documentação OpenAPI interativa

O parâmetro `unique_code` é aceito por compatibilidade, mas não é registrado, persistido nem tratado como segredo de autenticação.
