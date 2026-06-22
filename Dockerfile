FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    gcc \
    curl \   
    unzip \
    ffmpeg \
    libffi-dev \
    ca-certificates \
    build-essential \
    procps \
    && curl -fsSL https://deno.land/install.sh | sh \
    && rm -rf /var/lib/apt/lists/*

ENV DENO_INSTALL=/root/.deno
ENV PATH=$DENO_INSTALL/bin:$PATH
ENV DOCKER=1

WORKDIR /app
COPY . .

RUN pip install -U pip \
    && pip install --no-cache-dir -r requirements.txt

CMD ["bash", "start"]
