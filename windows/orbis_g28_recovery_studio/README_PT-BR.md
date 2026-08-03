# Orbis G28 Recovery Studio para Windows

Aplicativo independente para conversar diretamente com o bootloader OTA 5610/Bluetrum do G28 por Bluetooth Low Energy.

## O que a v0.1 faz

- escaneia dispositivos G28/OTA;
- detecta o transporte observado no G28 (`18A8 / 2AA8 / 2AA9`);
- aceita também o transporte proprietário HryFine 5610 (`6e40ff01/02/03`);
- negocia o protocolo com `D5/0x0F` e payload `10 00`;
- consulta a identidade com `D5/0x01` somente depois de confirmar `V1.1`;
- reagrupa notificações D6 fragmentadas;
- salva todo o tráfego em JSONL;
- monta qualquer quadro D5 em modo de simulação;
- valida a estrutura inicial de manifestos de recuperação.

## Proteções desta versão

A v0.1 transmite somente `D5/0x0F` e `D5/0x01`. Não transmite tabela de partições, dados, checksums de firmware ou `D5/0x0E`.

## Execução pelo código-fonte

```powershell
cd windows\orbis_g28_recovery_studio
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python app.py
```

No Windows, deixe o Bluetooth ligado e mantenha o relógio em modo OTA.

## Manifesto esperado futuramente

```json
{
  "device": "G28",
  "version": "V1.5",
  "parts": [
    {
      "part_id": 4,
      "address": 0,
      "length": 123456,
      "file": "code.bin",
      "sha256": "..."
    }
  ]
}
```

A presença desse arquivo, isoladamente, não libera gravação. Os arquivos e metadados ainda precisarão ser verificados contra uma fonte legítima.
