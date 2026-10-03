ARG UV_VERSION=0.12.21
ARG UV_DIGEST=sha256:a7aed3216253ee804de3e2d8afa5073baa1a177335345d43845cd4165e43b711
FROM ghcr.io/astral-sh/uv:${UV_VERSION}@${UV_DIGEST} AS uv

FROM debian:13-slim@sha256:a99cfc517144bc59b1978475ec53b46ecabec7e43635402ee5b77cc54cd1b20a

ARG UV_VERSION
ARG IMAGE_REVISION
LABEL org.opencontainers.image.revision=${IMAGE_REVISION}
ENV DEBIAN_FRONTEND=noninteractive \
    UV_LINK_MODE=copy \
    UV_PYTHON_INSTALL_DIR=/opt/uv/python \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    HOME=/tmp \
    TMPDIR=/tmp

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates git \
    && rm -rf /var/lib/apt/lists/*

COPY --from=uv /uv /uvx /usr/local/bin/
COPY pyproject.toml uv.lock .python-version README.md LICENSE ./
COPY src/ ./src/
COPY scripts/e2e_authoring.py /opt/prodeng/scripts/e2e_authoring.py
COPY examples/smart-kettle/ /opt/prodeng/examples/smart-kettle/

# The uv-managed CPython bundles pip with vendored copies of urllib3,
# msgpack, and setuptools that nothing in the image invokes — dependencies
# install via uv and the shipped venv is pip-less — so strip the payload
# instead of shipping unused vulnerable vendored packages.
RUN mkdir -p /opt/prodeng/scripts \
    && uv python install 3.12 \
    && rm -rf /opt/uv/python/bin/pip* \
              /opt/uv/python/cpython-*/bin/pip* \
              /opt/uv/python/cpython-*/lib/python3.12/site-packages/pip \
              /opt/uv/python/cpython-*/lib/python3.12/site-packages/pip-*.dist-info \
              /opt/uv/python/cpython-*/lib/python3.12/ensurepip \
    && uv sync --locked --no-default-groups \
    && chmod -R a+rX /app /opt/uv/python

ENV PATH="/app/.venv/bin:${PATH}"
USER 10001:10001

CMD ["python", "-m", "prodeng"]
