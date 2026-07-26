FROM rocm/dev-ubuntu-24.04:7.2.4-complete
COPY hip/bin /opt/strix-fa/hip/bin
ENV LD_LIBRARY_PATH=/opt/strix-fa/hip/bin:${LD_LIBRARY_PATH}
WORKDIR /models
EXPOSE 8080
ENTRYPOINT ["/opt/strix-fa/hip/bin/llama-server"]
CMD ["--help"]
