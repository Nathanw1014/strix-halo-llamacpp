#!/usr/bin/env bash
# Ceiling matrix: BASE(5c3a586 stock) vs CEIL(all fixes+mmid), base 5c3a586, custom glslc, Mesa 26.3
set -uo pipefail
ICD=/home/alloy/mesa-main/build-rel/src/amd/vulkan/radeon_devenv_icd.x86_64.json
LDP=/home/alloy/libdrm-install/lib
BASE=/home/alloy/llama-base5c/build-ceil/bin/llama-bench
CEIL=/home/alloy/llama-fullstack/build-ceil/bin/llama-bench
# 0b29b30 flipped defaults ON: both arms fully explicit or the off-arm silently inherits defaults
MMID_ON="GGML_VK_MMID_ROWLISTS=1 GGML_VK_MMID_SMALLN=1 GGML_VK_MMID_BM64=1 GGML_VK_MMID_WAVE32=1 GGML_VK_MMID_F16B=1 GGML_VK_MMID_M128=1"
MMID_OFF="GGML_VK_MMID_ROWLISTS=0 GGML_VK_MMID_SMALLN=0 GGML_VK_MMID_BM64=0 GGML_VK_MMID_WAVE32=0 GGML_VK_MMID_F16B=0 GGML_VK_MMID_M128=0"
OUT=/home/alloy/kv-ceil-results; mkdir -p "$OUT"; LOG="$OUT/run.log"; : > "$LOG"
log(){ echo "[$(date +%H:%M:%S)] $*" | tee -a "$LOG"; }
declare -A M=(
  [coder30b]=/home/alloy/models/Qwen3-Coder-30B-A3B-Instruct-UD-Q6_K_XL.gguf
  [qwen35b]=/home/alloy/models/Qwen3.6-35B-A3B-UD-Q5_K_XL.gguf )
DEPTHS=0,4096,16384,32768,65536
restore(){ log "restore"; systemctl --user start comfyui.service comfyui-gpu-yield.service llama-swap.service 2>&1|tee -a "$LOG"; }
trap restore EXIT
log "stop services"; systemctl --user stop llama-swap.service comfyui-gpu-yield.service comfyui.service 2>&1|tee -a "$LOG"; sleep 8
log "driver:$(VK_ICD_FILENAMES=$ICD LD_LIBRARY_PATH=$LDP vulkaninfo 2>/dev/null|grep -m1 driverInfo|awk -F= '{print $2}') | BASE=$(cd /home/alloy/llama-base5c&&git log --oneline -1 --format=%h) CEIL=$(cd ~/llama-fullstack&&git log --oneline -1 --format=%h)"
run(){ # $1 bin $2 tag $3 mk $4 kv $5 mmidenv $6.. flags
  local bin=$1 tag=$2 mk=$3 kv=$4 menv=$5; shift 5
  local of="$OUT/${tag}_${mk}_${kv}.md"
  log "=== $tag / $mk / $kv ==="
  env $menv VK_ICD_FILENAMES="$ICD" VK_DRIVER_FILES="$ICD" LD_LIBRARY_PATH="$LDP" \
    timeout 3000 "$bin" -m "${M[$mk]}" -ngl 99 -fa 1 -b 512 -ub 512 -p 512 -n 32 -d "$DEPTHS" -r 3 -o md "$@" \
    > "$of" 2> "${of%.md}.err" && log "  ok" || log "  FAIL rc=$?"
  sleep 20
}
run "$BASE" canary0 coder30b f16 ""
for mk in coder30b qwen35b; do
  run "$BASE" base "$mk" f16 ""
  run "$BASE" base "$mk" q4 "" -ctk q4_0 -ctv q4_0
  run "$CEIL" ceilNoMmid "$mk" q4 "$MMID_OFF" -ctk q4_0 -ctv q4_0
  run "$CEIL" ceil "$mk" q4 "$MMID_ON" -ctk q4_0 -ctv q4_0
  run "$CEIL" ceil "$mk" q8 "$MMID_ON" -ctk q8_0 -ctv q8_0
done
run "$BASE" canary1 coder30b f16 ""
log "=== CEIL MATRIX DONE ==="; touch /home/alloy/CEIL-MATRIX-DONE
