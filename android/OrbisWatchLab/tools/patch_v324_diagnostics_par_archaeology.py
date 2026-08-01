#!/usr/bin/env python3
from pathlib import Path
import sys

path = Path(sys.argv[1])
src = path.read_text(encoding='utf-8')

def rep(old, new):
    global src
    if old not in src:
        raise SystemExit('patch_v324 missing snippet: ' + old[:180])
    src = src.replace(old, new, 1)

rep('Orbis Watch OTA 5610 v3.23', 'Orbis Watch OTA 5610 v3.24')
rep(
    'A v3.23 mantém o parser de ACK FD, audita bin_list e acrescenta uma consulta histórica limitada V1.4→V1.0, somente de metadados, sem baixar BIN, sem alterar hora, RTC ou firmware; handshake e identidade continuam manuais.',
    'A v3.24 mantém a consulta histórica V1.4→V1.0 e acrescenta a arqueologia estática dos comandos 0x07/0x0B/0xF0 e da ferramenta gráfica Bluetrum ABPartTool; nenhum comando novo é enviado ao relógio.'
)
rep('''        Button historicalBinList = button("23. Consultar versões anteriores V1.4→V1.0 — metadados, sem download");
        historicalBinList.setOnClickListener(v -> confirmHistoricalBinListProbe());
        content.addView(historicalBinList, marginLayout(0, 2, 0, 8));

        Button scanTransition = button("Buscar novamente o G28/OTA agora");''',
'''        Button historicalBinList = button("23. Consultar versões anteriores V1.4→V1.0 — metadados, sem download");
        historicalBinList.setOnClickListener(v -> confirmHistoricalBinListProbe());
        content.addView(historicalBinList, marginLayout(0, 2, 0, 2));

        Button diagnosticArchaeology = button("24. Mostrar arqueologia 0x07/0x0B/0xF0 — local");
        diagnosticArchaeology.setOnClickListener(v -> appendDiagnosticArchaeology());
        content.addView(diagnosticArchaeology, marginLayout(0, 2, 0, 2));

        Button parArchaeology = button("25. Mostrar análise Bluetrum .par — local");
        parArchaeology.setOnClickListener(v -> appendParToolArchaeology());
        content.addView(parArchaeology, marginLayout(0, 2, 0, 8));

        Button scanTransition = button("Buscar novamente o G28/OTA agora");''')
rep('''        append("A v3.23 também pode consultar, de forma limitada, os códigos históricos V1.4 até V1.0 derivados da identidade real do G28.");
        append("A consulta histórica faz no máximo cinco GETs autenticados, para no primeiro bin_list encontrado, não baixa arquivos e não transmite tabela de partições.");
        append("===== FIM BIN_LIST =====");
    }

    private void appendHryFineFrameValidation''',
'''        append("A v3.24 também pode consultar, de forma limitada, os códigos históricos V1.4 até V1.0 derivados da identidade real do G28.");
        append("A consulta histórica faz no máximo cinco GETs autenticados, para no primeiro bin_list encontrado, não baixa arquivos e não transmite tabela de partições.");
        append("===== FIM BIN_LIST =====");
    }

    private void appendDiagnosticArchaeology() {
        append("===== ARQUEOLOGIA HRYFINE — 0x07 / 0x0B / 0xF0 =====");
        append("Auditoria integral: 56.787 arquivos Smali e 76 chamadas a IssuedUtil.getSendByte.");
        append("Comandos realmente emitidos: 02×42, 03×1, 04×1, 05×3, 08×1, 09×1, 0D×1, 0E×1, 0F×7, 10×1, 11×1, 12×1, 13×2, 14×1, 19×1, 1A×5, 1F×2, 20×1, F0×1, F1×1 e F3×1.");
        append("0x07 FACTORY_TEST: existe apenas como constante; emissores reais=0 e parser de resposta=0.");
        append("0x0B DEVICE_TEST: existe apenas como constante; emissores reais=0 e parser de resposta=0.");
        append("0x0A FLASH_READ: existe apenas como constante; emissores reais=0 e parser de resposta=0.");
        append("0xF0 não é consulta de firmware: NotifyWriteUtils.getVerification() gera 8 bytes ASCII aleatórios e envia F0/00.");
        append("verificationCode = soma de ((byte XOR 0xFF)) & 0xFF. Ao receber DF/F0, o HryFine compara receiveBytes[10] com esse valor.");
        append("Se coincidir, o app envia F1/00 com payload 00; a resposta F1 conduz à consulta F3 de informações do dispositivo ou ao fluxo alternativo de bind.");
        append("Conclusão: 0x07 e 0x0B estão dormentes no HryFine 3.8.9; F0/F1 são handshake de verificação, não diagnóstico de flash.");
        append("Nenhum quadro 0x07, 0x0B, 0x0A, F0 ou F1 foi transmitido pelo Orbis nesta ação.");
        append("===== FIM ARQUEOLOGIA DIAGNÓSTICA =====");
    }

    private void appendParToolArchaeology() {
        append("===== BLUETRUM ABPARTOOL — ANÁLISE ESTÁTICA =====");
        append("Classe Java: com.bluetrum.abpartool.ParTool; biblioteca libabpartool.so para arm64-v8a, armeabi-v7a, x86 e x86_64.");
        append("API: bitmapToPar(Bitmap, flag1, flag2, flag3) chama rawToPar(raw, width, height, flag1, flag2, flag3).");
        append("ImageUtils.getRawImageData converte cada pixel Android em quatro bytes nesta ordem exata: A, R, G, B.");
        append("JNI registrado em JNI_OnLoad: rawToPar([BIIZZZ)[B. O wrapper aloca width*height*4 bytes para a saída temporária e usa o retorno inteiro como tamanho final.");
        append("Símbolo nativo exportado: raw_to_par(unsigned char* out, unsigned char* in, int width, int height, bool, bool, bool).");
        append("A rotina contém quantização/dithering e codificação por sequências; os três booleanos não têm nomes seguros no APK.");
        append("Isso confirma uma ferramenta Bluetrum para empacotar recursos gráficos .par, mas não prova sozinho o SoC, RAM, endereço de partição ou controlador LCD do G28.");
        append("Nenhum .par foi criado, baixado ou enviado ao relógio nesta ação.");
        append("===== FIM ANÁLISE ABPARTOOL =====");
    }

    private void appendHryFineFrameValidation''')

path.write_text(src, encoding='utf-8')
