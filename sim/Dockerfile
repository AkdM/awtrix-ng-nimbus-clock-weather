# AWTRIX NG simulator: the firmware's own Linux build (awtrix-linux), headless,
# serving the web UI and HTTP API on port 8080.
FROM ubuntu:24.04

RUN apt-get update \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      build-essential cmake git ca-certificates openssl tzdata \
      libssl-dev liblzma-dev libjpeg-turbo8-dev python3-venv \
 && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /opt/pio && /opt/pio/bin/pip install --no-cache-dir platformio
ENV PATH=/opt/pio/bin:$PATH

# Build the same release the clock runs
ARG AWTRIX_REF=v1.2.2
RUN git clone --depth 1 --branch "$AWTRIX_REF" https://github.com/Blueforcer/awtrix-ng /src
WORKDIR /src
RUN pio pkg install -e native
# Two jobs: the container VM only has 2 GB of memory
RUN cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -DAWTRIX_WERROR=OFF \
 && cmake --build build --target awtrix-linux --parallel 2

EXPOSE 8080
VOLUME /data
# --lan listens on all addresses so the published port reaches it; the panel size is the
# command, 32x8 (TC001) unless sim.sh passes 52x16 (TC002)
ENTRYPOINT ["/src/build/awtrix-linux", "--data", "/data", "--port", "8080", "--lan", \
            "--webui", "/src/webui/index.html"]
CMD ["--width", "32", "--height", "8"]
