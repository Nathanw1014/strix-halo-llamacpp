#!/usr/bin/env bash
# GPU batch: verify rowlists branch + pp2048 ceiling runs (max-pp + kyuz0 match)
set -uo pipefail
export VK_ICD_FILENAMES=/home/alloy/mesa-main/build-rel/src/amd/vulkan/radeon_devenv_icd.x86_64.json
export VK_DRIVER_FILES="$VK_ICD_FILENAMES"
export LD_LIBRARY_PATH=/home/alloy/libdrm-install/lib
ROWBIN=/home/alloy/llama-mmid-rowlists/build-vk
CEIL=/home/alloy/llama-fullstack/build-ceil/bin/llama-bench
# 0b29b30 flipped defaults ON: keep arms explicit so historical numbers stay comparable
MMID_ON="GGML_VK_MMID_ROWLISTS=1 GGML_VK_MMID_SMALLN=1 GGML_VK_MMID_BM64=1 GGML_VK_MMID_WAVE32=1 GGML_VK_MMID_F16B=1 GGML_VK_MMID_M128=1"
OUT=/home/alloy/finalize-results; mkdir -p "$OUT"; LOG="$OUT/run.log"; : > "$LOG"
log(){ echo "[$(date +%H:%M:%S)] $*" | tee -a "$LOG"; }
C30=/home/alloy/models/Qwen3-Coder-30B-A3B-Instruct-UD-Q6_K_XL.gguf
Q35=/home/alloy/models/Qwen3.6-35B-A3B-UD-Q5_K_XL.gguf
restore(){ log restore; systemctl --user start comfyui.service comfyui-gpu-yield.service llama-swap.service 2>&1|tee -a "$LOG"; }
trap restore EXIT
log "stop services"; systemctl --user stop llama-swap.service comfyui-gpu-yield.service comfyui.service 2>&1|tee -a "$LOG"; sleep 8

# --- 1. rowlists branch correctness + isolated gain (35B, where mmid pays) ---
log "=== rowlists: test-backend-ops MUL_MAT_ID ==="
env GGML_VK_MMID_ROWLISTS=1 timeout 400 "$ROWBIN/bin/test-backend-ops" -o MUL_MAT_ID 2>&1 | grep -iE 'backends passed|dumped core' | tail -1 | tee -a "$LOG"
log "=== rowlists ON vs OFF, 35B pp512 d0/16k ==="
env GGML_VK_MMID_ROWLISTS=1 GGML_VK_MMID_SMALLN=0 GGML_VK_MMID_BM64=0 GGML_VK_MMID_WAVE32=0 GGML_VK_MMID_F16B=0 GGML_VK_MMID_M128=0 timeout 900 "$ROWBIN/bin/llama-bench" -m "$Q35" -ngl 99 -fa 1 -b 512 -ub 512 -p 512 -n 0 -d 0,16384 -r 3 -o md > "$OUT/rowlists_on.md" 2>"$OUT/rowlists_on.err" && log "  on ok" || log "  on FAIL"
env GGML_VK_MMID_ROWLISTS=0 GGML_VK_MMID_SMALLN=0 GGML_VK_MMID_BM64=0 GGML_VK_MMID_WAVE32=0 GGML_VK_MMID_F16B=0 GGML_VK_MMID_M128=0 timeout 900 "$ROWBIN/bin/llama-bench" -m "$Q35" -ngl 99 -fa 1 -b 512 -ub 512 -p 512 -n 0 -d 0,16384 -r 3 -o md > "$OUT/rowlists_off.md" 2>"$OUT/rowlists_off.err" && log "  off ok" || log "  off FAIL"
sleep 15

# --- 2. pp2048 ceiling: max-pp (ub1024) + kyuz0-match (ub512), CEIL q4, both models ---
for pair in "c30 $C30" "q35 $Q35"; do
  set -- $pair; tag=$1; mdl=$2
  for UB in 512 1024; do
    log "=== pp2048 CEIL q4 $tag ub$UB ==="
    env $MMID_ON timeout 3000 "$CEIL" -m "$mdl" -ngl 99 -fa 1 -b 2048 -ub $UB -ctk q4_0 -ctv q4_0 \
       -p 2048 -n 0 -d 0,16384,32768,65536 -r 3 -o md > "$OUT/pp2048_${tag}_ub${UB}.md" 2>"$OUT/pp2048_${tag}_ub${UB}.err" && log "  ok" || log "  FAIL"
    sleep 15
  done
done
log "=== FINALIZE DONE ==="; touch /home/alloy/FINALIZE-DONE
