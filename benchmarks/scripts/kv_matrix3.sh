#!/usr/bin/env bash
# Corrected matrix: custom glslc v2026.3-dev, q4 dequant-once arm, interleaved pre/post + canary
set -uo pipefail
ICD=/home/alloy/mesa-main/build-rel/src/amd/vulkan/radeon_devenv_icd.x86_64.json
LDP=/home/alloy/libdrm-install/lib
POST=/home/alloy/llama-latest-post/build-vk/bin/llama-bench   # master + #25494 + 6e2b7ea (q8+q4 dequant-once ON)
PRE=/home/alloy/llama-latest-pre/build-vk/bin/llama-bench     # master (q8+q4 baseline OFF)
OUT=/home/alloy/kv-matrix3-results; mkdir -p "$OUT"
LOG="$OUT/run.log"; : > "$LOG"
log(){ echo "[$(date +%H:%M:%S)] $*" | tee -a "$LOG"; }
declare -A M=(
  [coder30b]=/home/alloy/models/Qwen3-Coder-30B-A3B-Instruct-UD-Q6_K_XL.gguf
  [qwen35b]=/home/alloy/models/Qwen3.6-35B-A3B-UD-Q5_K_XL.gguf )
DEPTHS=0,4096,16384,32768,65536
restore(){ log "restoring services"; systemctl --user start comfyui.service comfyui-gpu-yield.service llama-swap.service 2>&1 | tee -a "$LOG"; }
trap restore EXIT
log "stopping services"; systemctl --user stop llama-swap.service comfyui-gpu-yield.service comfyui.service 2>&1 | tee -a "$LOG"; sleep 8
DRV=$(VK_ICD_FILENAMES="$ICD" LD_LIBRARY_PATH="$LDP" vulkaninfo 2>/dev/null | grep -m1 driverInfo | awk -F= '{print $2}')
log "driver:$DRV | POSTq4t=$(cd /home/alloy/llama-latest-post && git log --oneline -1 --format=%h) PRE=$(cd /home/alloy/llama-latest-pre && git log --oneline -1 --format=%h) | glslc=$(/home/alloy/shaderc/build/glslc/glslc --version|head -1)"

run(){ # $1 bin  $2 tag  $3 mk  $4 kv  $5.. flags
  local bin=$1 tag=$2 mk=$3 kv=$4; shift 4
  local of="$OUT/${tag}_${mk}_${kv}.md"
  log "=== ${tag} / ${mk} / ${kv} ==="
  gtt=$(cat /sys/class/drm/card*/device/mem_info_gtt_used 2>/dev/null | sort -n | tail -1)
  VK_ICD_FILENAMES="$ICD" VK_DRIVER_FILES="$ICD" LD_LIBRARY_PATH="$LDP" \
    timeout 3000 "$bin" -m "${M[$mk]}" -ngl 99 -fa 1 -b 512 -ub 512 \
      -p 512 -n 32 -d "$DEPTHS" -r 3 -o md "$@" \
      > "$of" 2> "${of%.md}.err" && log "  ok (gtt_pre=${gtt:-?})" || log "  FAIL rc=$?"
  sleep 20   # settle: let TTM deferred free drain between arms
}

# start canary
run "$POST" canary0 coder30b f16
for mk in coder30b qwen35b; do
  run "$POST" post "$mk" f16
  run "$POST" post "$mk" q8  -ctk q8_0 -ctv q8_0   # dequant-once ON
  run "$PRE"  pre  "$mk" q8  -ctk q8_0 -ctv q8_0   # baseline OFF
  run "$POST" post "$mk" q4  -ctk q4_0 -ctv q4_0   # dequant-once ON
  run "$PRE"  pre  "$mk" q4  -ctk q4_0 -ctv q4_0   # baseline OFF
done
# end canary (compare to canary0 for window stability)
run "$POST" canary1 coder30b f16
log "=== MATRIX3 DONE ==="
touch /home/alloy/KV-MATRIX3-DONE
