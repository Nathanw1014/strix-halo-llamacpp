#!/usr/bin/env bash
set -uo pipefail
cd /home/alloy/llama-mmid-rowlists
LOG=/home/alloy/llama-mmid-rowlists/build.log; : > "$LOG"
echo "[$(date +%H:%M:%S)] configure rowlists ($(git log --oneline -1 --format=%h))" | tee -a "$LOG"
rm -rf build-vk
cmake -B build-vk -DGGML_VULKAN=ON -DCMAKE_BUILD_TYPE=Release -DGGML_NATIVE=ON \
      -DLLAMA_CURL=OFF -DLLAMA_BUILD_TESTS=ON \
      -DVulkan_INCLUDE_DIR=/home/alloy/.local/include -DVulkan_GLSLC_EXECUTABLE=/home/alloy/shaderc/build/glslc/glslc >>"$LOG" 2>&1
echo "[$(date +%H:%M:%S)] build" | tee -a "$LOG"
cmake --build build-vk --target llama-bench test-backend-ops -j"$(nproc)" >>"$LOG" 2>&1
rc=$?; echo "[$(date +%H:%M:%S)] rc=$rc" | tee -a "$LOG"
[ $rc -eq 0 ] && touch /home/alloy/ROWLISTS-BUILD-DONE
