FROM rocm/dev-ubuntu-24.04:7.2.4-complete
LABEL com.github.containers.toolbox="true" \
      org.opencontainers.image.title="strix-halo-llamacpp-hip" \
      org.opencontainers.image.description="llama.cpp ROCm/HIP for Strix Halo (gfx1151), quantized-KV decode fix"
COPY hip/bin /opt/strix-halo-llamacpp/hip/bin
# put the fixed binaries on PATH so `distrobox/toolbox enter` finds llama-server/cli/bench
ENV PATH=/opt/strix-halo-llamacpp/hip/bin:$PATH \
    LD_LIBRARY_PATH=/opt/strix-halo-llamacpp/hip/bin:${LD_LIBRARY_PATH}
WORKDIR /models
EXPOSE 8080
ENTRYPOINT ["/opt/strix-halo-llamacpp/hip/bin/llama-server"]
CMD ["--help"]
