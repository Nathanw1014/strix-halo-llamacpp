#!/usr/bin/env bash
set -uo pipefail
GLSLC=/home/alloy/shaderc/build/glslc/glslc
build_one(){
  local dir=$1 tag=$2; cd "$dir"; local LOG="$dir/ceilbuild.log"; : > "$LOG"
  echo "[$(date +%H:%M:%S)] configure $tag ($(git log --oneline -1 --format=%h))" | tee -a "$LOG"
  rm -rf build-ceil
  cmake -B build-ceil -DGGML_VULKAN=ON -DCMAKE_BUILD_TYPE=Release -DGGML_NATIVE=ON \
        -DLLAMA_CURL=OFF -DLLAMA_BUILD_TESTS=ON \
        -DVulkan_INCLUDE_DIR=/home/alloy/.local/include -DVulkan_GLSLC_EXECUTABLE=$GLSLC >>"$LOG" 2>&1
  echo "[$(date +%H:%M:%S)] build $tag" | tee -a "$LOG"
  cmake --build build-ceil --target llama-bench test-backend-ops -j"$(nproc)" >>"$LOG" 2>&1
  local rc=$?; echo "[$(date +%H:%M:%S)] $tag rc=$rc" | tee -a "$LOG"; return $rc
}
build_one /home/alloy/llama-fullstack CEIL; c=$?
build_one /home/alloy/llama-base5c    BASE; b=$?
echo "CEIL rc=$c BASE rc=$b" > /home/alloy/ceil-build-status.txt
[ $c -eq 0 ] && [ $b -eq 0 ] && touch /home/alloy/CEIL-BUILD-DONE
