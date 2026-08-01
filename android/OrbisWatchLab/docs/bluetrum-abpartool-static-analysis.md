# Bluetrum ABPartTool — análise estática no HryFine 3.8.9

## Componentes encontrados

O APK contém:

```text
com/bluetrum/abpartool/ParTool
com/bluetrum/abpartool/ImageUtils
libabpartool.so
```

A biblioteca nativa existe para:

- `arm64-v8a`;
- `armeabi-v7a`;
- `x86`;
- `x86_64`.

A presença desses componentes confirma que o HryFine integra uma ferramenta gráfica da Bluetrum, mas não prova isoladamente qual SoC está instalado no G28.

## API Java/JNI

A API observada é equivalente a:

```text
ParTool.bitmapToPar(Bitmap, boolean, boolean, boolean)
ParTool.rawToPar(byte[], int width, int height,
                 boolean, boolean, boolean)
```

`bitmapToPar(...)` converte a imagem em bytes brutos e chama a função nativa `rawToPar(...)`.

O método nativo é registrado em `JNI_OnLoad` com a assinatura:

```text
rawToPar([BIIZZZ)[B
```

No binário x86_64 existe o símbolo:

```text
raw_to_par(unsigned char* out,
           unsigned char* in,
           int width,
           int height,
           bool, bool, bool)
```

O wrapper nativo:

1. recebe o buffer de entrada;
2. aloca uma área temporária de `width × height × 4` bytes;
3. chama `raw_to_par`;
4. usa o inteiro retornado como tamanho da saída;
5. cria um `byte[]` Java com esse tamanho.

## Formato de entrada de pixel

`ImageUtils.getRawImageData(...)` converte cada pixel Android em quatro bytes nesta ordem:

```text
A, R, G, B
```

Portanto, a entrada de `rawToPar` não é RGB565 puro. É um buffer ARGB de 32 bits por pixel.

## O que o código nativo indica

A inspeção estática mostra operações compatíveis com:

- quantização de cores;
- dithering;
- comparação de pixels;
- codificação por sequências/repetições;
- criação de um contêiner `.par`.

Os significados dos três parâmetros booleanos não aparecem com nomes seguros no APK. Não devem ser rotulados sem amostras comparativas.

## O que ainda não foi provado

Esta biblioteca, sozinha, não revela:

- chipset exato do G28;
- arquitetura da CPU do relógio;
- RAM ou capacidade da flash;
- endereço da partição de mostradores;
- formato final de uma `bin_list`;
- controlador LCD;
- protocolo de envio do arquivo `.par` ao G28;
- possibilidade de executar código dentro de uma partição gráfica.

Ela demonstra apenas que o ecossistema do aplicativo usa uma ferramenta Bluetrum para empacotar recursos gráficos.

## Utilidade para o projeto DOOM

A ABPartTool pode ajudar a descobrir:

- formato esperado de imagens;
- transparência e ordem de canais;
- compressão dos recursos;
- estrutura de cabeçalho de mostradores;
- limites práticos de tamanho e resolução.

Isso pode resolver parte do caminho de vídeo e recursos gráficos, mas não substitui um firmware executável, mapa de memória ou toolchain do SoC.

## Política da v3.24

A v3.24 apenas exibe os resultados da análise. Ela não:

- cria `.par`;
- baixa mostradores;
- transmite arquivos;
- envia comando de partição;
- altera a memória do relógio.
