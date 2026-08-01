#!/usr/bin/env python3
from pathlib import Path
import sys

path = Path(sys.argv[1])
src = path.read_text(encoding='utf-8')

def rep(old, new):
    global src
    if old not in src:
        raise SystemExit('patch_v323 missing snippet: ' + old[:160])
    src = src.replace(old, new, 1)

rep('Orbis Watch OTA 5610 v3.22', 'Orbis Watch OTA 5610 v3.23')
rep(
    'A v3.22 corrige o parser de ACK FD e audita o schema bin_list devolvido pelo servidor, sem baixar BIN, sem alterar hora, RTC ou firmware; handshake e identidade continuam manuais.',
    'A v3.23 mantém o parser de ACK FD, audita bin_list e acrescenta uma consulta histórica limitada V1.4→V1.0, somente de metadados, sem baixar BIN, sem alterar hora, RTC ou firmware; handshake e identidade continuam manuais.'
)
rep('''        Button binListSchema = button("22. Explicar bin_list do HryFine — local");
        binListSchema.setOnClickListener(v -> appendBinListSchema());
        content.addView(binListSchema, marginLayout(0, 2, 0, 8));

        Button scanTransition = button("Buscar novamente o G28/OTA agora");''',
'''        Button binListSchema = button("22. Explicar bin_list do HryFine — local");
        binListSchema.setOnClickListener(v -> appendBinListSchema());
        content.addView(binListSchema, marginLayout(0, 2, 0, 2));

        Button historicalBinList = button("23. Consultar versões anteriores V1.4→V1.0 — metadados, sem download");
        historicalBinList.setOnClickListener(v -> confirmHistoricalBinListProbe());
        content.addView(historicalBinList, marginLayout(0, 2, 0, 8));

        Button scanTransition = button("Buscar novamente o G28/OTA agora");''')
rep('''    private boolean nusOtaInfoValidated;
    private boolean officialUpdateAvailable;
    private boolean otaStartRequested;''',
'''    private boolean nusOtaInfoValidated;
    private boolean officialUpdateAvailable;
    private boolean historicalBinListProbeRunning;
    private boolean otaStartRequested;''')
rep('''        append("A v3.22 apenas audita os metadados caso apareçam. Não baixa arquivos e não transmite tabela de partições.");
        append("===== FIM BIN_LIST =====");
    }
''',
'''        append("A v3.23 também pode consultar, de forma limitada, os códigos históricos V1.4 até V1.0 derivados da identidade real do G28.");
        append("A consulta histórica faz no máximo cinco GETs autenticados, para no primeiro bin_list encontrado, não baixa arquivos e não transmite tabela de partições.");
        append("===== FIM BIN_LIST =====");
    }
''')
rep('''    private void auditBinList(JSONArray bins) {
''', '''    private void confirmHistoricalBinListProbe() {
        if (!nusOtaInfoValidated || otaUniqueCode.isEmpty()) {
            toast("Execute primeiro a consulta OTA pelo NUS e aguarde a identidade completa");
            return;
        }
        if (historicalBinListProbeRunning) {
            toast("A consulta histórica já está em andamento");
            return;
        }
        new AlertDialog.Builder(this)
                .setTitle("Consulta histórica limitada")
                .setMessage("Serão feitas no máximo cinco consultas GET ao servidor oficial, usando a identidade real do G28 com versões V1.4 até V1.0. "
                        + "A busca para no primeiro bin_list encontrado. Nenhum arquivo será baixado, nenhum comando BLE será transmitido e nenhuma memória do relógio será alterada.")
                .setNegativeButton("Cancelar", null)
                .setPositiveButton("CONSULTAR METADADOS", (dialog, which) -> runHistoricalBinListProbe())
                .show();
    }

    private void runHistoricalBinListProbe() {
        if (historicalBinListProbeRunning) return;
        historicalBinListProbeRunning = true;
        append("===== CONSULTA HISTÓRICA BIN_LIST G28 — SEM DOWNLOAD / SEM TX BLE =====");
        append("Base real: versão=" + emptyAsDash(otaVersion)
                + " projeto=" + emptyAsDash(otaProject)
                + " unique_code=" + otaUniqueCode);
        append("Escopo fixo: V1.4, V1.3, V1.2, V1.1 e V1.0; intervalo de 1,2 s; parada no primeiro bin_list não vazio.");
        setStatus("Consultando metadados históricos do G28; relógio não será alterado.");

        ioExecutor.execute(() -> {
            boolean found = false;
            String foundVersion = "";
            int attempts = 0;
            try {
                String[] versions = new String[]{"V1.4", "V1.3", "V1.2", "V1.1", "V1.0"};
                for (String version : versions) {
                    if (emergencyStopped) {
                        append("HISTÓRICO interrompido pela parada de emergência.");
                        break;
                    }
                    String historicalCode = buildHistoricalUniqueCode(version);
                    if (historicalCode.isEmpty()) {
                        append("HISTÓRICO " + version + ": não foi possível reconstruir o unique_code.");
                        continue;
                    }
                    attempts++;
                    Map<String, String> params = buildOfficialServerParams(historicalCode);
                    params.put("sign", sign(params));
                    append("HISTÓRICO tentativa=" + attempts
                            + " versão=" + version
                            + " unique_code=" + historicalCode);
                    String response = httpGet(OTA_ENDPOINT + "?" + queryString(params));
                    JSONObject root = new JSONObject(response == null ? "{}" : response);
                    String code = root.optString("code", "");
                    String message = root.optString("msg", "");
                    JSONArray bins = findBinList(root);
                    int count = bins == null ? -1 : bins.length();
                    append("HISTÓRICO resultado versão=" + version
                            + " code=" + emptyAsDash(code)
                            + " msg=" + emptyAsDash(message)
                            + " bin_list=" + (count < 0 ? "ausente" : String.valueOf(count))
                            + " response=" + abbreviate(response, 1200));
                    if (bins != null && bins.length() > 0) {
                        found = true;
                        foundVersion = version;
                        append("HISTÓRICO ENCONTROU BIN_LIST para " + version
                                + ". Auditando somente metadados; nenhum bin_file será baixado.");
                        auditBinList(bins);
                        break;
                    }
                    if (attempts < versions.length) {
                        try { Thread.sleep(1200L); }
                        catch (InterruptedException interrupted) {
                            Thread.currentThread().interrupt();
                            append("HISTÓRICO interrompido durante o intervalo.");
                            break;
                        }
                    }
                }
            } catch (Exception error) {
                append("HISTÓRICO falhou: " + error.getClass().getSimpleName()
                        + ": " + emptyAsDash(error.getMessage()));
            } finally {
                historicalBinListProbeRunning = false;
                append("HISTÓRICO resumo: tentativas=" + attempts
                        + " encontrou=" + found
                        + " versão=" + emptyAsDash(foundVersion));
                append("POLÍTICA: nenhum download, nenhum 0x03, nenhum bloco de firmware e nenhum TX BLE.");
                append("===== FIM CONSULTA HISTÓRICA BIN_LIST =====");
                setStatus(found
                        ? "Metadados históricos encontrados; gravação continua bloqueada."
                        : "Nenhuma bin_list encontrada nas versões históricas consultadas.");
            }
        });
    }

    private String buildHistoricalUniqueCode(String version) {
        try {
            byte[] current = hexToBytes(otaUniqueCode);
            if (current.length < 6) return "";
            int currentVersionLength = current[4] & 0xFF;
            int projectLengthOffset = 5 + currentVersionLength;
            if (projectLengthOffset >= current.length) return "";
            int projectLength = current[projectLengthOffset] & 0xFF;
            int projectOffset = projectLengthOffset + 1;
            if (projectOffset + projectLength > current.length) return "";

            byte[] versionBytes = version.getBytes(StandardCharsets.UTF_8);
            byte[] output = new byte[4 + 1 + versionBytes.length + 1 + projectLength];
            System.arraycopy(current, 0, output, 0, 4);
            output[4] = (byte) versionBytes.length;
            System.arraycopy(versionBytes, 0, output, 5, versionBytes.length);
            int outProjectLengthOffset = 5 + versionBytes.length;
            output[outProjectLengthOffset] = (byte) projectLength;
            System.arraycopy(current, projectOffset, output, outProjectLengthOffset + 1, projectLength);
            return hexCompact(output);
        } catch (Exception error) {
            append("Falha ao reconstruir unique_code histórico " + version + ": " + error.getMessage());
            return "";
        }
    }

    private void auditBinList(JSONArray bins) {
''')
rep('''    private static String hexCompact(byte[] bytes) {
        StringBuilder out = new StringBuilder();
        for (byte b : bytes) out.append(String.format(Locale.US, "%02X", b & 0xFF));
        return out.toString();
    }
''', '''    private static String hexCompact(byte[] bytes) {
        StringBuilder out = new StringBuilder();
        for (byte b : bytes) out.append(String.format(Locale.US, "%02X", b & 0xFF));
        return out.toString();
    }
    private static byte[] hexToBytes(String text) {
        String clean = cleanHex(text);
        if ((clean.length() & 1) != 0) throw new IllegalArgumentException("hex com tamanho ímpar");
        byte[] output = new byte[clean.length() / 2];
        for (int i = 0; i < output.length; i++) {
            output[i] = (byte) Integer.parseInt(clean.substring(i * 2, i * 2 + 2), 16);
        }
        return output;
    }
''')

path.write_text(src, encoding='utf-8')
