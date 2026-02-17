#syntax=docker/dockerfile:1
FROM debian:bookworm-slim AS build

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        git \
        make \
        build-essential \
        pkg-config \
        ca-certificates \
        librabbitmq-dev \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

RUN git clone https://github.com/EarthScope/libslink.git && \
    cd libslink && \
    make install

RUN git clone https://github.com/EarthScope/libmseed.git && \
    cd libmseed && \
    make install

WORKDIR /app
COPY . .
RUN make

FROM debian:bookworm-slim AS connector
RUN apt-get update \
    && apt-get install -y --no-install-recommends librabbitmq4 \
    && rm -rf /var/lib/apt/lists/*
COPY --from=build /usr/local/lib/libslink* /usr/lib/
COPY --from=build /app/build/connector /usr/local/bin/connector
COPY connector/streamlist.conf.example /app/streamlist.conf
ENV PATH="/usr/local/bin:${PATH}" \
    STREAMLIST_FILE=/app/streamlist.conf
CMD ["connector", "-h"]

FROM debian:bookworm-slim AS consumer
RUN apt-get update \
    && apt-get install -y --no-install-recommends librabbitmq4 libpq5 \
    && rm -rf /var/lib/apt/lists/*
COPY --from=build /usr/local/lib/libmseed* /usr/lib/
COPY --from=build /app/build/consumer /usr/local/bin/consumer
ENV PATH="/usr/local/bin:${PATH}"
CMD ["consumer", "--help"]

FROM python:3.11-slim AS publisher
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DEFAULT_TIMEOUT=120 \
    PIP_RETRIES=10 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

COPY tools/publish_mseed/requirements.txt /app/tools/publish_mseed/requirements.txt
RUN python -m pip install --no-cache-dir --prefer-binary -r /app/tools/publish_mseed/requirements.txt

COPY tools/publish_mseed /app/tools/publish_mseed

CMD ["python", "tools/publish_mseed/publish_mseed.py", "--help"]

FROM pytorch/pytorch:2.5.1-cuda12.4-cudnn9-runtime AS detector
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DEFAULT_TIMEOUT=120 \
    PIP_RETRIES=10 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

COPY detector/requirements.txt /app/detector/requirements.txt
RUN python -m pip install --no-cache-dir --prefer-binary -r /app/detector/requirements.txt

COPY detector /app/detector

CMD ["python", "-m", "detector.main", "--help"]
