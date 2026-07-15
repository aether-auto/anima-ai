# Deterministic CPU-only Linux golden image for anima renderer primitives.
#
# Pinned to a single amd64 base by digest so every golden render — locally on an
# Apple-silicon host via emulation, and in GHCR CI on amd64 runners — happens in
# the exact same environment. This is the ONLY environment allowed to bless a
# canonical baseline PNG (see `anima.testing.goldens update`, which refuses
# unless ANIMA_GOLDEN_IMAGE_REF matches the manifest's pinned container_ref).
#
# No host fonts, no GPU drivers, no runtime downloads: the fixtures are text-free
# and the apt libraries below are exactly what the pinned skia-python wheel needs
# to raster to an off-screen CPU surface.
FROM --platform=linux/amd64 python:3.12-slim-bookworm@sha256:d50fb7611f86d04a3b0471b46d7557818d88983fc3136726336b2a4c657aa30b

# Deterministic locale, timezone, and Python behaviour.
ENV LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    TZ=UTC \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONHASHSEED=0 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# System libraries the pinned skia-python wheel links against for headless CPU
# raster. Mirrors the CI apt set (libegl1 libfontconfig1 libgl1); no drivers.
RUN apt-get update \
    && apt-get install --yes --no-install-recommends \
        libegl1 \
        libfontconfig1 \
        libgl1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

# Runtime dependencies: exactly the hash-locked set, no transitive resolution
# (--no-deps) so nothing escapes the lock. skia-python declares pybind11 as a
# dependency but only needs it at build time, so it is intentionally absent.
COPY requirements/lock-linux.txt requirements/lock-linux.txt
RUN pip install --require-hashes --no-deps -r requirements/lock-linux.txt

# Build backend, also hash-locked, so the editable install below can run with
# --no-build-isolation and never fetch an unpinned setuptools.
COPY requirements/build-linux.txt requirements/build-linux.txt
RUN pip install --require-hashes --no-deps -r requirements/build-linux.txt

# The package itself, installed editable with build isolation disabled.
COPY pyproject.toml pyproject.toml
COPY src src
COPY tests tests
RUN pip install --no-deps --no-build-isolation -e .

# Sanity: heavy renderer imports and the harness is importable at build time.
RUN python -c "import skia, numpy; import anima.testing.goldens; print('golden image OK')"

ENTRYPOINT []
CMD ["python", "-m", "anima.testing.goldens", "--help"]
