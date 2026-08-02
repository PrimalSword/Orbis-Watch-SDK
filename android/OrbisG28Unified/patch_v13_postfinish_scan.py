#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: patch_v13_postfinish_scan.py <app-root>')

root = Path(sys.argv[1]).resolve()
java = root / 'app/src/main/java/com/orbisg28siliconcensus/ActiveLabActivity.java'
text = java.read_text()

old_transition = 'boolean transition = otaStartRequested && otaTransitionScanArmed && !emergencyStopped;'
new_transition = ('boolean transition = otaStartRequested && otaTransitionScanArmed '
                  '&& !emergencyStopped && !bootloaderRescueMode;')
if old_transition not in text:
    raise SystemExit('transition guard anchor missing')
text = text.replace(old_transition, new_transition, 1)

old_scan = '''    private void startPostRescueRuntimeScan() {
        bootloaderRescueMode = false;
        if (emergencyStopped || !hasScanPermission() || adapter == null || !adapter.isEnabled()) return;
'''
new_scan = '''    private void startPostRescueRuntimeScan() {
        bootloaderRescueMode = false;
        otaStartRequested = false;
        otaTransitionScanArmed = false;
        otaReconnectInProgress = false;
        if (emergencyStopped || !hasScanPermission() || adapter == null || !adapter.isEnabled()) return;
'''
if old_scan not in text:
    raise SystemExit('post-rescue scan anchor missing')
text = text.replace(old_scan, new_scan, 1)

java.write_text(text)
print('v1.3 post-finish scan arbitration fixed')
