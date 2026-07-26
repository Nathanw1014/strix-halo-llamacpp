#!/usr/bin/env bash
set -uo pipefail
GLSLC=/home/alloy/shaderc/build/glslc/glslc
build_one(){
  local dir=$1 tag=$2; cd "$dir"; local LOG="$dir/build2.log"; : > "$LOG"
  echo "[$(date +%H:%M:%S)] configure $tag ($(git log --oneline -1 --format=%h)) glslc=$($GLSLC --version|head -1)" | tee -a "$LOG"
  rm -rf build-vk
  cmake -B build-vk -DGGML_VULKAN=ON -DCMAKE_BUILD_TYPE=Release -DGGML_NATIVE=ON \
        -DLLAMA_CURL=OFF -DLLAMA_BUILD_TESTS=ON \
        -DVulkan_INCLUDE_DIR=/home/alloy/.local/include \
        -DVulkan_GLSLC_EXECUTABLE=$GLSLC >>"$LOG" 2>&1
  echo "[$(date +%H:%M:%S)] build $tag" | tee -a "$LOG"
  cmake --build build-vk --target llama-bench test-backend-ops -j"$(nproc)" >>"$LOG" 2>&1
  local rc=$?; echo "[$(date +%H:%M:%S)] $tag ninja rc=$rc" | tee -a "$LOG"; return $rc
}
build_one /home/alloy/llama-latest-post POSTq4t; rcp=$?
build_one /home/alloy/llama-latest-pre  PRE;     rcr=$?
echo "POSTq4t rc=$rcp PRE rc=$rcr" > /home/alloy/llama-build2-status.txt
[ $rcp -eq 0 ] && [ $rcr -eq 0 ] && touch /home/alloy/LLAMA-BUILD2-DONE
