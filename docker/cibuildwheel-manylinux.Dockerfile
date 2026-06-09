ARG BASE_IMAGE=quay.io/pypa/manylinux_2_28_x86_64
FROM ${BASE_IMAGE}

# Keep manylinux build dependencies in the container image so local machines and
# GitHub runners use the same packaging environment.
RUN dnf install -y \
    cargo \
    cmake \
    git \
    libcurl-devel \
    libicu-devel \
    libjpeg-turbo-devel \
    libpng-devel \
    libuv-devel \
    libwebp-devel \
    openssl-devel \
    zlib-devel \
    pkgconf-pkg-config \
    rust \
    && dnf clean all
