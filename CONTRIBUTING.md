# Contributing

## Requirements

- Python 3.12+
- Rust toolchain pinned in `.mise.toml`
- `uv`, `just`, and preferably `mise`

## Development workflow

CI should orchestrate the same `just` recipes developers run locally. Keep build logic in
`Justfile`; GitHub Actions should call those recipes rather than duplicating shell logic.

```bash
mise install
just setup
just check
```

Useful recipes:

```bash
just test-unit
just test-single tests/test_render.py::TestMap::test_basic_render
just test-filter "render"
just lint
just lint-fix
just format
just typecheck
just build-rust
just build
just build-wheels
just test-docker
```

## Code style

- Prefer small, explicit, boring code over clever abstractions.
- Validate near trust boundaries and raise `MlnativeError` with actionable context.
- Use modern Python typing: `dict[str, Any]`, `str | None`, and typed function signatures.
- Let ruff sort imports and format code; line length is 100.
- Keep public docs concise and add tests for behavior changes.

## Rust renderer

The Python API talks to `rust/src/main.rs` over JSON on stdin/stdout. The daemon supports:

- `init`
- `reload_style`
- `render`
- `render_batch`
- `quit`

Build locally with:

```bash
just build-rust
```

The built binary is copied into `mlnative/bin/` by CI/build recipes using the platform name
expected by `mlnative._bridge.get_binary_path()`.

## Wheels and releases

- Python and Rust package versions should stay in sync.
- Tag format: `v{version}`.
- Linux wheels are built with `cibuildwheel` and include the native renderer executable.
- Source distributions include the Rust source for rebuilds.

`cibuildwheel` uses the project-owned `docker/cibuildwheel-manylinux.Dockerfile` image so
local builds and GitHub Actions use the same manylinux dependency set. Build wheels locally with:

```bash
just build-wheels
```

The wheel helper in `scripts/build_cibw_wheel.py` builds the Rust binary inside that container,
keeps only the matching platform executable in `mlnative/bin/`, and retags wheel metadata from
`py3-none-any` to the appropriate manylinux platform tag.

## CI/CD

GitHub Actions runs:

1. `just check` for lint, format, type checking, and unit tests.
2. `cargo clippy --locked --all-targets --all-features -- -D warnings` for the Rust renderer.
3. Linux binary builds for smoke and integration tests.
4. `just ci-build-wheels` on release tags to build Linux x64 and ARM64 wheels with `cibuildwheel`.
5. `just ci-build-sdist`, GitHub release creation, provenance attestation, and PyPI trusted publishing.

Build-time Linux dependencies are captured in the cibuildwheel Dockerfile. Local source builds need
CMake plus libcurl/OpenSSL/image/ICU/libuv development headers. Runtime users of
pre-built Linux wheels still need system graphics/runtime libraries such as `mesa-vulkan-drivers`,
`libcurl4`, `libglfw3`, `libuv1`, and `zlib1g`.

Integration tests render real maps and require the native binary, runtime libraries, network access,
and OpenFreeMap availability. Unit tests skip integration coverage with `-m "not integration"`.

Common issues:

- **Permission denied on binary**: `_bridge.py` attempts to restore executable permissions.
- **Missing `libcurl` at build time**: install the platform's libcurl development package or build via `just build-wheels`.
- **Renderer exits immediately**: install Vulkan/runtime graphics libraries.
- **Network timeouts**: verify outbound HTTPS access to style/tile services or raise `MLNATIVE_TIMEOUT`.

Release checklist:

```bash
# 1. Update pyproject.toml and rust/Cargo.toml versions
# 2. Update CHANGELOG.md
just check
just build

git add pyproject.toml rust/Cargo.toml rust/Cargo.lock CHANGELOG.md
git commit -m "Bump version to X.Y.Z"
git tag -a vX.Y.Z -m "Release vX.Y.Z"
git push origin main --tags
```
