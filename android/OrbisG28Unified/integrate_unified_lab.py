#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 3:
    raise SystemExit('usage: integrate_unified_lab.py <census-app-root> <watch-lab-root>')

census = Path(sys.argv[1]).resolve()
watch = Path(sys.argv[2]).resolve()
java_dir = census / 'app/src/main/java/com/orbisg28siliconcensus'
main = java_dir / 'MainActivity.java'
if not main.is_file():
    raise SystemExit(f'missing census MainActivity: {main}')

# Preserve the complete v0.8 diagnostic tool as an internal activity.
diag = main.read_text()
diag = diag.replace('public final class MainActivity extends Activity',
                    'public final class DiagnosticsActivity extends Activity')
diag = diag.replace('MainActivity.this', 'DiagnosticsActivity.this')
diag = diag.replace('ORBIS G28 SILICON CENSUS v0.8', 'ORBIS G28 LAB — DIAGNÓSTICO v1.0')
diag = diag.replace('ORBIS G28 — SILICON CENSUS v0.8', 'ORBIS G28 LAB — DIAGNÓSTICO')
diag = diag.replace(
    'A v0.8 corrige a navegação da tela e mantém o mapeamento estático do fluxo OTA 5610, sem rede e sem escrever no relógio.',
    'Diagnóstico completo: BLE/GATT, HCI via Shizuku, HryFine, fluxo 5610 e pacotes locais. Esta área não grava firmware.')
(java_dir / 'DiagnosticsActivity.java').write_text(diag)

# Import the latest active 5610 laboratory as a second internal activity.
watch_main = watch / 'app/src/main/java/com/orbiswatchlab/MainActivity.java'
if not watch_main.is_file():
    raise SystemExit(f'missing reconstructed Watch Lab MainActivity: {watch_main}')
lab = watch_main.read_text()
lab = lab.replace('package com.orbiswatchlab;', 'package com.orbisg28siliconcensus;')
lab = lab.replace('public final class MainActivity extends Activity',
                  'public final class ActiveLabActivity extends Activity')
lab = lab.replace('MainActivity.this', 'ActiveLabActivity.this')
lab = lab.replace('Orbis Watch OTA 5610 v3.25', 'ORBIS G28 LAB — OTA 5610')
lab = lab.replace('Entrada controlada no bootloader OTA 5610 do G28',
                  'Laboratório ativo do G28 — alvo de trabalho Bluetrum BT8918C')
(java_dir / 'ActiveLabActivity.java').write_text(lab)

# Replace the launcher with a concise dashboard.
dashboard = r'''package com.orbisg28siliconcensus;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
import android.graphics.Color;
import android.os.Bundle;
import android.view.Gravity;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

public final class MainActivity extends Activity {
    @Override protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        buildUi();
    }

    private void buildUi() {
        ScrollView page = new ScrollView(this);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(dp(16), dp(16), dp(16), dp(24));
        root.setBackgroundColor(Color.rgb(15, 17, 22));
        page.addView(root, new ScrollView.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        TextView title = text("ORBIS G28 LAB", 28, Color.WHITE, true);
        title.setGravity(Gravity.CENTER_HORIZONTAL);
        root.addView(title);
        TextView subtitle = text(
                "Um único aplicativo para identificar, documentar e testar o G28",
                14, Color.rgb(185, 194, 214), false);
        subtitle.setGravity(Gravity.CENTER_HORIZONTAL);
        subtitle.setPadding(0, dp(4), 0, dp(16));
        root.addView(subtitle);

        root.addView(card(
                "ALVO DE TRABALHO",
                "Bluetrum BT8918C — confiança de engenharia: 72%\n" +
                "Família BT8918/BT891x — confiança: 93%\n\n" +
                "Confirmado diretamente:\n" +
                "• fabricante HCI 0x0642 Bluetrum\n" +
                "• Bluetooth Core 5.3\n" +
                "• subversion 0x0003\n" +
                "• Classic e BLE com o mesmo fingerprint\n" +
                "• projeto E06B_G28_WE, firmware V1.5",
                Color.rgb(135, 224, 175)));

        root.addView(card(
                "O QUE O APP FAZ",
                "Diagnóstico: BLE/GATT, HCI por Shizuku, análise do HryFine, fluxo OTA 5610 e pacotes locais.\n\n" +
                "Laboratório ativo: conecta ao G28, consulta OTA, solicita entrada no bootloader, negocia D5/0x0F e lê a identidade D5/0x01.\n\n" +
                "Tabela, BIN, partições, RAM e firmware continuam bloqueados até existir recuperação verificável.",
                Color.rgb(150, 195, 255)));

        Button diagnose = button("1. DIAGNÓSTICO E RESULTADOS");
        diagnose.setOnClickListener(v ->
                startActivity(new Intent(this, DiagnosticsActivity.class)));
        root.addView(diagnose);

        Button active = button("2. LABORATÓRIO ATIVO OTA 5610");
        active.setOnClickListener(v -> new AlertDialog.Builder(this)
                .setTitle("Abrir laboratório ativo?")
                .setMessage("Esta área pode solicitar que o G28 entre no bootloader. " +
                        "D5/0x0F e D5/0x01 não enviam firmware, mas podem reiniciar ou desconectar o relógio. " +
                        "Use-o fora do pulso e com bateria suficiente.")
                .setNegativeButton("Cancelar", null)
                .setPositiveButton("ABRIR LABORATÓRIO", (d, w) ->
                        startActivity(new Intent(this, ActiveLabActivity.class)))
                .show());
        root.addView(active);

        Button roadmap = button("3. PLANO ATÉ ORBIS_OK / DOOM");
        roadmap.setOnClickListener(v -> new AlertDialog.Builder(this)
                .setTitle("Rota técnica")
                .setMessage("1. Criar passaporte de recuperação.\n\n" +
                        "2. Confirmar OTA 5610, D5/0x0F e D5/0x01.\n\n" +
                        "3. Obter mapa genuíno de flash/partições.\n\n" +
                        "4. Validar um payload RISC-V mínimo em RAM que responda ORBIS_OK.\n\n" +
                        "5. Depois: display, toque e Doom.\n\n" +
                        "As próximas funções serão incorporadas neste mesmo aplicativo.")
                .setPositiveButton("Entendi", null)
                .show());
        root.addView(roadmap);

        root.addView(card(
                "REGRA DE RISCO",
                "O botão de emergência bloqueia novos quadros e encerra o GATT. " +
                "Ele não desfaz um quadro já aceito. Cada operação ativa exige confirmação e deixa log bruto.",
                Color.rgb(255, 190, 130)));

        setContentView(page);
    }

    private TextView card(String heading, String body, int accent) {
        TextView view = text(heading + "\n\n" + body, 14, Color.rgb(226, 230, 240), false);
        view.setPadding(dp(14), dp(14), dp(14), dp(14));
        view.setBackgroundColor(Color.rgb(29, 33, 42));
        view.setTextColor(accent);
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        lp.setMargins(0, 0, 0, dp(10));
        view.setLayoutParams(lp);
        return view;
    }

    private Button button(String label) {
        Button button = new Button(this);
        button.setText(label);
        button.setAllCaps(false);
        button.setTextSize(15);
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        lp.setMargins(0, dp(4), 0, dp(4));
        button.setLayoutParams(lp);
        return button;
    }

    private TextView text(String value, int sp, int color, boolean bold) {
        TextView view = new TextView(this);
        view.setText(value);
        view.setTextSize(sp);
        view.setTextColor(color);
        if (bold) view.setTypeface(android.graphics.Typeface.DEFAULT_BOLD);
        return view;
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }
}
'''
main.write_text(dashboard)

manifest = '''<manifest xmlns:android="http://schemas.android.com/apk/res/android">
    <uses-feature android:name="android.hardware.bluetooth_le" android:required="true" />
    <uses-permission android:name="android.permission.INTERNET" />
    <uses-permission android:name="android.permission.BLUETOOTH" android:maxSdkVersion="30" />
    <uses-permission android:name="android.permission.BLUETOOTH_ADMIN" android:maxSdkVersion="30" />
    <uses-permission android:name="android.permission.ACCESS_FINE_LOCATION" android:maxSdkVersion="30" />
    <uses-permission android:name="android.permission.BLUETOOTH_SCAN" android:usesPermissionFlags="neverForLocation" />
    <uses-permission android:name="android.permission.BLUETOOTH_CONNECT" />

    <queries>
        <package android:name="com.lianhezhuli.hyfit" />
        <package android:name="moe.shizuku.privileged.api" />
    </queries>

    <application
        android:allowBackup="false"
        android:icon="@mipmap/ic_launcher"
        android:roundIcon="@mipmap/ic_launcher"
        android:label="Orbis G28 Lab"
        android:supportsRtl="true"
        android:theme="@style/AppTheme">
        <provider
            android:name="rikka.shizuku.ShizukuProvider"
            android:authorities="${applicationId}.shizuku"
            android:multiprocess="false"
            android:enabled="true"
            android:exported="true"
            android:permission="android.permission.INTERACT_ACROSS_USERS_FULL" />

        <activity android:name=".DiagnosticsActivity" android:exported="false" android:screenOrientation="portrait" />
        <activity android:name=".ActiveLabActivity" android:exported="false" android:screenOrientation="portrait" />
        <activity android:name=".MainActivity" android:exported="true" android:screenOrientation="portrait">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>
    </application>
</manifest>
'''
(census / 'app/src/main/AndroidManifest.xml').write_text(manifest)

gradle = census / 'app/build.gradle'
g = gradle.read_text()
g = g.replace('versionCode 8', 'versionCode 100')
g = g.replace("versionName '0.8-scroll-and-validation-fix'", "versionName '1.0-unified-lab'")
gradle.write_text(g)

# Assertions deliberately fail the workflow if future upstream changes break the integration.
assert 'class DiagnosticsActivity' in (java_dir / 'DiagnosticsActivity.java').read_text()
assert 'class ActiveLabActivity' in (java_dir / 'ActiveLabActivity.java').read_text()
assert 'D5/0x0F' in (java_dir / 'ActiveLabActivity.java').read_text()
assert 'D5/0x01' in (java_dir / 'ActiveLabActivity.java').read_text()
assert 'EMERGÊNCIA' in (java_dir / 'ActiveLabActivity.java').read_text()
assert 'ORBIS G28 LAB' in main.read_text()
print('Unified Orbis G28 Lab source assembled')
