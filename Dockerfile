FROM debian:bullseye-slim

# Install dependencies
RUN apt-get update && apt-get install -y \
    curl unzip ca-certificates python3 python3-pip nginx gettext-base supervisor && \
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

# Install Python dependencies
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy application files
COPY app.py .
COPY nginx.conf.template /etc/nginx/nginx.conf.template

# Create supervisor config
RUN echo '[supervisord]\n\
nodaemon=true\n\
logfile=/dev/null\n\
pidfile=/var/run/supervisord.pid\n\
\n\
[program:rclone]\n\
command=rclone serve http multirun: --addr :8000 --vfs-cache-mode full --vfs-cache-max-size 18G --vfs-cache-max-age 3h --vfs-read-chunk-size 128M --vfs-read-chunk-size-limit off --buffer-size 128M --dir-cache-time 2h --poll-interval 10s --transfers 4 --checkers 8 --fast-list\n\
autostart=true\n\
autorestart=true\n\
stdout_logfile=/dev/stdout\n\
stdout_logfile_maxbytes=0\n\
stderr_logfile=/dev/stderr\n\
stderr_logfile_maxbytes=0\n\
\n\
[program:flask]\n\
command=python3 /app/app.py\n\
autostart=true\n\
autorestart=true\n\
stdout_logfile=/dev/stdout\n\
stdout_logfile_maxbytes=0\n\
stderr_logfile=/dev/stderr\n\
stderr_logfile_maxbytes=0\n\
environment=FLASK_PORT=5000\n\
\n\
[program:nginx]\n\
command=bash -c "sleep 3 && envsubst '\''$PORT'\'' < /etc/nginx/nginx.conf.template > /etc/nginx/sites-enabled/default && nginx -g '\''daemon off;'\''"\n\
autostart=true\n\
autorestart=true\n\
stdout_logfile=/dev/stdout\n\
stdout_logfile_maxbytes=0\n\
stderr_logfile=/dev/stderr\n\
stderr_logfile_maxbytes=0\n' > /etc/supervisor/conf.d/supervisord.conf

# Expose Render port
EXPOSE 10000

CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
