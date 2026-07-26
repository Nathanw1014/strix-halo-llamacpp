FROM rocm/dev-ubuntu-24.04:7.2.4-complete
LABEL com.github.containers.toolbox="true" \
      org.opencontainers.image.title="strix-halo-fa-hip" \
      org.opencontainers.image.description="llama.cpp ROCm/HIP for Strix Halo (gfx1151), quantized-KV decode fix"
COPY hip/bin /opt/strix-fa/hip/bin
# put the fixed binaries on PATH so `distrobox/toolbox enter` finds llama-server/cli/bench
ENV PATH=/opt/strix-fa/hip/bin:$PATH \
    LD_LIBRARY_PATH=/opt/strix-fa/hip/bin:${LD_LIBRARY_PATH}
WORKDIR /models
EXPOSE 8080
ENTRYPOINT ["/opt/strix-fa/hip/bin/llama-server"]
CMD ["--help"]
