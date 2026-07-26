#!/usr/bin/env bash
set -uo pipefail
export PKG_CONFIG_PATH=/home/alloy/libdrm-install/lib/pkgconfig:${PKG_CONFIG_PATH:-}
cd /home/alloy/mesa-main
LOG=/home/alloy/mesa-main/build.log; : > "$LOG"
echo "[$(date +%H:%M:%S)] pkg-config libdrm = $(pkg-config --modversion libdrm)" | tee -a "$LOG"
echo "[$(date +%H:%M:%S)] meson setup" | tee -a "$LOG"
meson setup build-rel -Dvulkan-drivers=amd -Dgallium-drivers= -Dllvm=disabled -Dplatforms= -Dvideo-codecs= -Dglx=disabled -Degl=disabled -Dgbm=disabled \
   -Dbuildtype=release -Dwerror=false >>"$LOG" 2>&1
rc=$?; echo "[$(date +%H:%M:%S)] meson rc=$rc" | tee -a "$LOG"
[ $rc -ne 0 ] && { echo "SETUP FAILED"; tail -15 "$LOG"; exit 1; }
echo "[$(date +%H:%M:%S)] ninja (this is the ~10-15min part)" | tee -a "$LOG"
ninja -C build-rel >>"$LOG" 2>&1
rc=$?; echo "[$(date +%H:%M:%S)] ninja rc=$rc" | tee -a "$LOG"
echo "--- ICD + .so ---" | tee -a "$LOG"
find build-rel -name '*icd*.json' -o -name 'libvulkan_radeon.so' 2>/dev/null | tee -a "$LOG"
[ $rc -eq 0 ] && touch /home/alloy/MESA-BUILD-DONE
exit $rc
