ARG UV_VERSION=0.12.23
ARG UV_DIGEST=sha256:61d393e44e249f2e4b526b6c7ddcecce245946826e608e11c93ad4f5bba55b21
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

# procps ships `ps` so the container-audit Lynis run executes its
# process/crypto/account checks instead of aborting 84 sub-tests.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates git procps \
    && rm -rf /var/lib/apt/lists/*

# The pinned debian:13-slim digest keeps shipping the deb Trivy flags at
# publish (CVE-2026-103111 libpcre2-8-0). Upgrade just that package inside
# the build so the publish gate stays green.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        --only-upgrade \
        libpcre2-8-0 \
    && rm -rf /var/lib/apt/lists/*

# Tighten the login.defs umask to 027 (Lynis AUTH-9328): the image has no
# interactive users, so files created at runtime stay group-readable only.
RUN printf 'UMASK 027\n' >> /etc/login.defs

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
    && uv python install 3.14 \
    && rm -rf /opt/uv/python/bin/pip* \
              /opt/uv/python/cpython-*/bin/pip* \
              /opt/uv/python/cpython-*/lib/python3.*/site-packages/pip \
              /opt/uv/python/cpython-*/lib/python3.*/site-packages/pip-*.dist-info \
              /opt/uv/python/cpython-*/lib/python3.*/ensurepip \
              /root/.cache/uv \
    && uv sync --locked --no-default-groups \
    && chmod -R a+rX /app /opt/uv/python

ENV PATH="/app/.venv/bin:${PATH}"
USER 10001:10001

# CIS Docker DS-0026: the image is a batch CLI, not a long-running service —
# mark the absence of a probe explicitly instead of leaving it undefined.
HEALTHCHECK NONE

CMD ["python", "-m", "prodeng"]
