FROM debian:bullseye-slim

# Install dependencies
RUN apt-get update && apt-get install -y \
    curl unzip ca-certificates && \
    update-ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Install rclone
RUN curl -O https://downloads.rclone.org/rclone-current-linux-amd64.zip \
    && unzip rclone-current-linux-amd64.zip \
    && cd rclone-*-linux-amd64 \
    && cp rclone /usr/bin/ \
    && chown root:root /usr/bin/rclone \
    && chmod 755 /usr/bin/rclone

# Copy rclone.conf
RUN mkdir -p /root/.config/rclone
COPY rclone.conf /root/.config/rclone/rclone.conf

WORKDIR /app

# Expose Render port
EXPOSE 10000

# Run WebDAV using Render's $PORT env var
CMD ["sh", "-c", "rclone serve http multirun: \
  --addr :${PORT:-10000} \
  --vfs-cache-mode full \
  --vfs-cache-max-size 18G \
  --vfs-cache-max-age 3h \
  --vfs-read-chunk-size 128M \
  --vfs-read-chunk-size-limit off \
  --buffer-size 128M \
  --dir-cache-time 2h \
  --poll-interval 10s \
  --transfers 4 \
  --checkers 8 \
  --fast-list"]
