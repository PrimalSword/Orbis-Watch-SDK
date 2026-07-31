from pathlib import Path
import re
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: patch_v35.py <MainActivity.java>')
source_path = Path(sys.argv[1])
src = source_path.read_text(encoding='utf-8')

src=src.replace('Orbis Watch OTA 5610 v3.4','Orbis Watch OTA 5610 v3.5')
src=src.replace('Mapeador dos canais FF12, FF00 e OTA experimental do G28','Probe oficial D5 no canal FF02/FF01 do G28')
src=src.replace('mas não desfaz bytes que já tenham sido gravados.', 'e esta versão não oferece comandos de gravação de firmware.')

needle='''    private byte[] nusRxBuffer = new byte[0];
    private int nusExpectedLength;
'''
repl='''    private byte[] nusRxBuffer = new byte[0];
    private int nusExpectedLength;
    private byte[] candidateRxBuffer = new byte[0];
    private int candidateExpectedLength;
    private BluetoothGattCharacteristic pendingReadCharacteristic;
    private String pendingReadLabel;
'''
assert needle in src
src=src.replace(needle,repl)

start=src.index('        content.addView(section("Canais proprietários encontrados no G28"), matchWrap());')
end=src.index('        content.addView(section("Log"), matchWrap());', start)
new_ui='''        content.addView(section("Probe oficial FF02 → FF01"), matchWrap());
        TextView candidateNote = text(
                "O APK do HryFine monta as requisições 5610 com cabeçalho D5, campos de 11 bytes e checksum de 16 bits. " +
                        "Esta versão envia somente as consultas 0x0F e 0x01 no FF02 e observa a resposta no FF01. " +
                        "Não há tabela, BIN, bloco, checksum de firmware ou finalização nesta tela.",
                12,
                false);
        content.addView(candidateNote, marginLayout(2, 1, 2, 4));

        LinearLayout readCandidateRow = horizontal();
        Button readFf14 = button("Ler FF14");
        readFf14.setOnClickListener(v -> readCandidate(ff14Notify, "FF14"));
        Button readFf01 = button("Ler FF01");
        readFf01.setOnClickListener(v -> readCandidate(ff01Notify, "FF01"));
        readCandidateRow.addView(readFf14, weightedButton());
        readCandidateRow.addView(readFf01, weightedButton());
        content.addView(readCandidateRow, marginLayout(0, 2, 0, 2));

        Button safeCandidateInspection = button("Inspeção segura: ler FF14 e depois FF01");
        safeCandidateInspection.setOnClickListener(v -> runCandidateReadInspection());
        content.addView(safeCandidateInspection, marginLayout(0, 2, 0, 2));

        LinearLayout notifyCandidateRow = horizontal();
        Button notifyFf01 = button("Ativar FF01 notify");
        notifyFf01.setOnClickListener(v -> activateCandidateNotifications(ff01Notify, "FF01"));
        Button notifyFf14 = button("Ativar FF14 (diagnóstico)");
        notifyFf14.setOnClickListener(v -> activateCandidateNotifications(ff14Notify, "FF14"));
        notifyCandidateRow.addView(notifyFf01, weightedButton());
        notifyCandidateRow.addView(notifyFf14, weightedButton());
        content.addView(notifyCandidateRow, marginLayout(0, 2, 0, 4));

        LinearLayout ff02ProbeRow = horizontal();
        Button ff02Protocol = button("D5 oficial 0x0F → FF02");
        ff02Protocol.setOnClickListener(v -> confirmCandidateProbe(ff02Write, "FF02", 0x0F));
        Button ff02Info = button("D5 oficial 0x01 → FF02");
        ff02Info.setOnClickListener(v -> confirmCandidateProbe(ff02Write, "FF02", 0x01));
        ff02ProbeRow.addView(ff02Protocol, weightedButton());
        ff02ProbeRow.addView(ff02Info, weightedButton());
        content.addView(ff02ProbeRow, marginLayout(0, 2, 0, 5));

        TextView probeWarning = text(
                "Fluxo recomendado: validar NUS → ativar FF01 notify → executar um único probe D5 → aguardar a resposta D6. " +
                        "O FF13 e os comandos de gravação foram retirados da interface desta versão.",
                12,
                false);
        content.addView(probeWarning, marginLayout(2, 2, 2, 5));

        transferView = text("Transferência de firmware: DESATIVADA na v3.5", 13, true);
        transferView.setTypeface(Typeface.MONOSPACE);
        content.addView(transferView, marginLayout(2, 2, 2, 7));

'''
src=src[:start]+new_ui+src[end:]

old='''    private void runCandidateReadInspection() {
        if (gatt == null) { toast("Conecte primeiro"); return; }
        cancelPendingTasks();
        append("INSPEÇÃO SEGURA: somente leituras FF14 e FF01; nenhum quadro será escrito.");
        readCandidate(ff14Notify, "FF14");
        schedule(700, () -> readCandidate(ff01Notify, "FF01"));
        schedule(1_500, () -> append("Inspeção segura concluída. Agora ative uma notificação por vez, se desejar."));
    }
'''
new='''    private void runCandidateReadInspection() {
        if (gatt == null) { toast("Conecte primeiro"); return; }
        cancelPendingTasks();
        pendingReadCharacteristic = ff01Notify;
        pendingReadLabel = "FF01";
        append("INSPEÇÃO SEGURA: leitura FF14; FF01 será enfileirada somente após o callback GATT.");
        readCandidate(ff14Notify, "FF14");
    }
'''
assert old in src
src=src.replace(old,new)

pattern=re.compile(r'''    private void confirmCandidateProbe\(BluetoothGattCharacteristic target, String label, int command\) \{.*?\n    \}\n\n    private void sendCandidateProbe\(BluetoothGattCharacteristic target, String label, int command\) \{.*?\n    \}\n''',re.S)
m=pattern.search(src)
assert m
new_probe='''    private void confirmCandidateProbe(BluetoothGattCharacteristic target, String label, int command) {
        if (target == null || gatt == null) { toast(label + " write não está disponível"); return; }
        if (!ff01NotificationsReady) {
            toast("Ative primeiro a notificação FF01");
            append("PROBE BLOQUEADO: FF01 notify ainda não foi confirmado.");
            return;
        }
        String commandLabel = String.format(Locale.US, "0x%02X", command);
        new AlertDialog.Builder(this)
                .setTitle("Enviar requisição D5 oficial " + commandLabel + "?")
                .setMessage("Será enviado um único quadro no FF02, reproduzindo Cus5610CommandUtils.generalSendBytes: " +
                        "cabeçalho D5, checksum de 16 bits e comprimento de 16 bits. Não envia tabela, BIN, bloco de firmware nem finalização.")
                .setNegativeButton("Cancelar", null)
                .setPositiveButton("ENVIAR UMA VEZ", (d, w) -> sendCandidateProbe(target, label, command))
                .show();
    }

    private void sendCandidateProbe(BluetoothGattCharacteristic target, String label, int command) {
        if (emergencyStopped || gatt == null || target == null || !hasConnectPermission()) return;
        byte[] payload = command == 0x0F ? new byte[]{0x10, 0x00} : new byte[0];
        byte[] frame = buildOfficial5610Request(command, 1, 0, 0, payload);
        int properties = target.getProperties();
        int writeType = (properties & BluetoothGattCharacteristic.PROPERTY_WRITE_NO_RESPONSE) != 0
                ? BluetoothGattCharacteristic.WRITE_TYPE_NO_RESPONSE
                : BluetoothGattCharacteristic.WRITE_TYPE_DEFAULT;
        int checksum = ((frame[7] & 0xFF) << 8) | (frame[8] & 0xFF);
        candidateRxBuffer = new byte[0];
        candidateExpectedLength = 0;
        append(String.format(Locale.US,
                "PROBE D5 OFICIAL %s cmd=0x%02X checksum=0x%04X len=%d TX %s",
                label, command, checksum, frame.length, hex(frame)));
        try {
            if (Build.VERSION.SDK_INT >= 33) {
                int result = gatt.writeCharacteristic(target, frame, writeType);
                append("Write D5 " + label + " result=" + result + " type=" + writeType
                        + (writeType == BluetoothGattCharacteristic.WRITE_TYPE_NO_RESPONSE ? " (WRITE_NR)" : ""));
            } else {
                target.setWriteType(writeType);
                target.setValue(frame);
                boolean queued = gatt.writeCharacteristic(target);
                append("Write D5 " + label + " queued=" + queued + " type=" + writeType);
            }
        } catch (Exception error) {
            append("Falha probe D5 " + label + ": " + error.getMessage());
        }
    }
'''
src=src[:m.start()]+new_probe+src[m.end():]

candidate_start = src.index('        boolean directOta = otaNotify != null && otaNotify.getUuid().equals(characteristic.getUuid());')
candidate_end = src.index('    }\n\n    private void consumeNusNotification', candidate_start)
new='''        boolean directOta = otaNotify != null && otaNotify.getUuid().equals(characteristic.getUuid());
        boolean fromFf01 = ff01Notify != null && ff01Notify.getUuid().equals(characteristic.getUuid());
        boolean fromFf14 = ff14Notify != null && ff14Notify.getUuid().equals(characteristic.getUuid());
        if (fromFf01) {
            append("  ↳ resposta recebida no canal oficial candidato FF01");
            consumeCandidateNotification(copy);
            return;
        }
        if (fromFf14) {
            append("  ↳ resposta no FF14 (canal alternativo): ASCII=\"" + printableAscii(copy) + "\"");
            return;
        }
        if (directOta) {
            if (copy.length > 0 && ((copy[0] & 0xFF) == 0xD6 || otaRxBuffer.length > 0)) {
                consumeOtaNotification(copy);
            } else {
                append("  ↳ dados OTA não-D6: ASCII=\"" + printableAscii(copy) + "\"");
            }
        }
'''
src = src[:candidate_start] + new + src[candidate_end:]

insert_at=src.index('    private void consumeOtaNotification(byte[] chunk) {')
candidate_parser='''    private void consumeCandidateNotification(byte[] chunk) {
        if (chunk == null || chunk.length == 0) return;

        if (candidateRxBuffer.length == 0) {
            if ((chunk[0] & 0xFF) != 0xD6) {
                append("  ↳ FF01 sem cabeçalho D6: ASCII=\"" + printableAscii(chunk) + "\"");
                return;
            }
            if (chunk.length < 9) {
                candidateRxBuffer = chunk.clone();
                candidateExpectedLength = 9;
                append("  ↳ D6 fragmentado: aguardando cabeçalho completo");
                return;
            }

            int status = chunk[3] & 0xFF;
            if (chunk.length == 9 && isShortCandidateChecksumValid(chunk)
                    && (status < 1 || status > 10)) {
                parseShortCandidateFrame(chunk);
                return;
            }

            int payloadLength = chunk[8] & 0xFF;
            candidateExpectedLength = 9 + payloadLength;
            if (candidateExpectedLength < 9 || candidateExpectedLength > 4096) {
                append("  ↳ D6 candidato com comprimento inválido=" + candidateExpectedLength);
                candidateExpectedLength = 0;
                return;
            }
        }

        byte[] joined = new byte[candidateRxBuffer.length + chunk.length];
        System.arraycopy(candidateRxBuffer, 0, joined, 0, candidateRxBuffer.length);
        System.arraycopy(chunk, 0, joined, candidateRxBuffer.length, chunk.length);
        candidateRxBuffer = joined;

        if (candidateRxBuffer.length >= 9 && candidateExpectedLength == 9) {
            int status = candidateRxBuffer[3] & 0xFF;
            if (isShortCandidateChecksumValid(candidateRxBuffer)
                    && (status < 1 || status > 10)) {
                byte[] frame = java.util.Arrays.copyOf(candidateRxBuffer, 9);
                candidateRxBuffer = new byte[0];
                candidateExpectedLength = 0;
                parseShortCandidateFrame(frame);
                return;
            }
            candidateExpectedLength = 9 + (candidateRxBuffer[8] & 0xFF);
            if (candidateExpectedLength < 9 || candidateExpectedLength > 4096) {
                append("  ↳ D6 candidato com comprimento inválido=" + candidateExpectedLength);
                candidateRxBuffer = new byte[0];
                candidateExpectedLength = 0;
                return;
            }
        }

        if (candidateExpectedLength > 0 && candidateRxBuffer.length >= candidateExpectedLength) {
            byte[] frame = java.util.Arrays.copyOf(candidateRxBuffer, candidateExpectedLength);
            candidateRxBuffer = new byte[0];
            candidateExpectedLength = 0;
            append("  ↳ resposta D6 oficial completa no FF01");
            parseOtaFrame(frame);
        }
    }

    private static boolean isShortCandidateChecksumValid(byte[] frame) {
        if (frame == null || frame.length < 9) return false;
        int sum = 0;
        for (int i = 0; i < 8; i++) sum = (sum + (frame[i] & 0xFF)) & 0xFF;
        return sum == (frame[8] & 0xFF);
    }

    private void parseShortCandidateFrame(byte[] frame) {
        int command = frame[1] & 0xFF;
        int version = frame[2] & 0xFF;
        int flag = frame[3] & 0xFF;
        int sequence = ((frame[4] & 0xFF) << 8) | (frame[5] & 0xFF);
        int aux = ((frame[6] & 0xFF) << 8) | (frame[7] & 0xFF);
        append(String.format(Locale.US,
                "  ↳ D6 CURTO cmd=0x%02X ver=%d flag=0x%02X seq=%d aux=%d checksum8=OK",
                command, version, flag, sequence, aux));
        if (flag == 0x80) {
            append("  ↳ NACK proprietário 0x80: quadro reconhecido pelo FF02/FF01, mas rejeitado pelo formato/protocolo.");
        }
    }

'''
src=src[:insert_at]+candidate_parser+src[insert_at:]

insert_at=src.index('    private static byte[] buildOta5610(')
official_builder='''    /** Exact reconstruction of Cus5610CommandUtils.generalSendBytes from classes6.dex. */
    private static byte[] buildOfficial5610Request(int command, int protocolVersion, int block, int fragment, byte[] payload) {
        if (payload == null) payload = new byte[0];
        if (payload.length > 0xFFFF) throw new IllegalArgumentException("Payload 5610 maior que 65535 bytes");

        byte[] frame = new byte[11 + payload.length];
        frame[0] = (byte) 0xD5;
        frame[1] = (byte) command;
        frame[2] = 0x01;
        frame[3] = (byte) protocolVersion;
        frame[4] = (byte) (block >> 8);
        frame[5] = (byte) block;
        frame[6] = (byte) fragment;
        frame[9] = (byte) (payload.length >> 8);
        frame[10] = (byte) payload.length;
        System.arraycopy(payload, 0, frame, 11, payload.length);

        int checksum = 0;
        for (int i = 0; i < frame.length; i++) {
            if (i != 7 && i != 8) checksum = (checksum + (frame[i] & 0xFF)) & 0xFFFF;
        }
        frame[7] = (byte) (checksum >> 8);
        frame[8] = (byte) checksum;
        return frame;
    }

'''
src=src[:insert_at]+official_builder+src[insert_at:]

old='''    private void handleRead(BluetoothGattCharacteristic characteristic, byte[] value, int status) {
        byte[] copy = value == null ? new byte[0] : value.clone();
        append("READ " + characteristic.getUuid() + " status=" + status + " data=" + hex(copy)
                + " ASCII=\"" + printableAscii(copy) + "\"");
        if (status == BluetoothGatt.GATT_SUCCESS && copy.length > 0 && (copy[0] & 0xFF) == 0xD6) {
            append("  ↳ leitura contém cabeçalho D6; encaminhando ao parser OTA.");
            consumeOtaNotification(copy);
        }
    }
'''
new='''    private void handleRead(BluetoothGattCharacteristic characteristic, byte[] value, int status) {
        byte[] copy = value == null ? new byte[0] : value.clone();
        append("READ " + characteristic.getUuid() + " status=" + status + " data=" + hex(copy)
                + " ASCII=\"" + printableAscii(copy) + "\"");
        if (status == BluetoothGatt.GATT_SUCCESS && copy.length > 0 && (copy[0] & 0xFF) == 0xD6) {
            append("  ↳ leitura contém cabeçalho D6; encaminhando ao parser FF01.");
            consumeCandidateNotification(copy);
        }
        if (ff14Notify != null && ff14Notify.getUuid().equals(characteristic.getUuid())
                && pendingReadCharacteristic != null) {
            BluetoothGattCharacteristic next = pendingReadCharacteristic;
            String nextLabel = pendingReadLabel == null ? "próxima" : pendingReadLabel;
            pendingReadCharacteristic = null;
            pendingReadLabel = null;
            schedule(120, () -> {
                append("Fila GATT: iniciando leitura " + nextLabel + " após callback FF14.");
                readCandidate(next, nextLabel);
            });
        }
    }
'''
assert old in src
src=src.replace(old,new)

needle='''        nusRxBuffer = new byte[0];
        nusExpectedLength = 0;
'''
repl='''        nusRxBuffer = new byte[0];
        nusExpectedLength = 0;
        candidateRxBuffer = new byte[0];
        candidateExpectedLength = 0;
        pendingReadCharacteristic = null;
        pendingReadLabel = null;
'''
assert needle in src
src=src.replace(needle,repl)

src=src.replace('''    private void renderTransferStatus() {
        runOnUiThread(() -> transferView.setText("Transferência: " + transferMode + " / " + transferStage
                + "\npart=" + transferPartIndex + " block=" + transferBlockIndex
                + "\nframes=" + transferSentFrames + "/" + transferTotalFrames
                + "\nrisco armado=" + riskArmed));
    }
''','''    private void renderTransferStatus() {
        if (transferView == null) return;
        runOnUiThread(() -> transferView.setText("Transferência de firmware: DESATIVADA na v3.5"));
    }
''')

src=src.replace('''    private void confirmTransfer(TransferMode mode) {
        if (!riskArmed) { toast("Arme o modo de risco primeiro"); return; }
''','''    private void confirmTransfer(TransferMode mode) {
        toast("Gravação de firmware desativada na v3.5");
        append("BLOQUEADO: a v3.5 não permite tabela, bloco ou pacote de firmware.");
        return;
        /*
        if (!riskArmed) { toast("Arme o modo de risco primeiro"); return; }
''')
m=re.search(r'(    private void confirmTransfer\(TransferMode mode\) \{.*?)(\n    \}\n\n    private void startTransfer)',src,re.S)
if m and '/*' in m.group(1) and '*/' not in m.group(1):
    src=src[:m.start(2)]+'\n        */'+src[m.start(2):]

assert 'buildOfficial5610Request' in src
assert 'D5 oficial 0x0F' in src
assert 'Orbis Watch OTA 5610 v3.5' in src
source_path.write_text(src, encoding='utf-8')
print(f'patched v3.5 source: {source_path} ({len(src)} chars)')
