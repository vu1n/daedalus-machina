FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install docker-compose plugin (v2)
RUN mkdir -p /root/.docker/cli-plugins \
    && curl -fsSL https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64 \
       -o /root/.docker/cli-plugins/docker-compose \
    && chmod +x /root/.docker/cli-plugins/docker-compose

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY autoscaler.py ./

CMD ["python", "-u", "autoscaler.py"]

