ARG BASE_IMAGE=quay.io/pypa/manylinux_2_28_x86_64
FROM ${BASE_IMAGE}

# Keep manylinux build dependencies in the container image so local machines and
# GitHub runners use the same packaging environment.
RUN dnf install -y \
    cargo \
    cmake \
    git \
    glslang-devel \
    libcurl-devel \
    libicu-devel \
    libjpeg-turbo-devel \
    libjpeg-turbo-static \
    libpng-devel \
    libpng-static \
    libuv-devel \
    libwebp-devel \
    libwebp-static \
    openssl-devel \
    openssl-static \
    spirv-tools-devel \
    zlib-devel \
    zlib-static \
    pkgconf-pkg-config \
    rust \
    && dnf clean all
