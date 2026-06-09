# Audit Issues

- Date: 2026-04-03
- Commit: `9bd2eac59da5`
- Codebase summary (`sloc`): 50 files, 2,696 code LOC, 1,271 documentation LOC, 6,004 total lines; main languages: Python 1,869 LOC, YAML 353 LOC, Rust 259 LOC.
- Scope: Python wrapper (`mlnative/`), Rust renderer (`rust/`), example servers (`examples/`), CI/release workflows (`.github/workflows/`), packaging/build helpers, and test/runtime container files.
- Audit references: [OWASP ASVS 5.0](https://owasp.org/www-project-application-security-verification-standard/) with emphasis on [V15 Secure Coding and Architecture](https://raw.githubusercontent.com/OWASP/ASVS/v5.0.0/5.0/en/0x24-V15-Secure-Coding-and-Architecture.md), [V16 Security Logging and Error Handling](https://raw.githubusercontent.com/OWASP/ASVS/v5.0.0/5.0/en/0x25-V16-Security-Logging-and-Error-Handling.md), and [grugbrain.dev](https://grugbrain.dev/).
- Local dependency lookup: Renovate dry-run succeeded on 2026-04-03; the only actionable delta surfaced was `actions/attest-build-provenance` digest `b3e506e8c389afc651c5bacf2b8f2a1ea0557215` → `a2bbfa25375fe432b6a289bc6b6cd05ecd0c4c32`.

## Prioritized findings

### 1) Reused temp style file is truncated but not rewound before rewrite
- Location: `rust/src/main.rs:89-99`, `tests/test_issue_resolutions.py:138-145`
- Category: security
- Reference: ASVS `v5.0.0-16.5.3`
- Recommendation: Seek to offset 0 before rewriting the reused `NamedTempFile` (or recreate it), then add a regression test that reloads a JSON style twice. As written, repeat `reload_style()` / `set_geojson()` calls can produce a NUL-prefixed style file and break rendering.
- Status: open

### 2) Renderer timeouts can desynchronize the daemon protocol and hand late responses to the wrong caller
- Location: `mlnative/_bridge.py:181-225`, `mlnative/_bridge.py:277-306`
- Category: security
- Reference: ASVS `v5.0.0-15.4.1`, `v5.0.0-16.5.3`
- Recommendation: Treat a timeout as terminal for that daemon instance, or add request IDs and response matching. Today a timed-out command leaves its eventual response in the shared queue, so the next command can consume stale data.
- Status: open

### 3) Example servers still let request data choose arbitrary remote URLs and local style files
- Location: `examples/fastapi_server.py:42-75`, `examples/web_test_server.py:44-129`, `examples/templates/test_form.html:61-63`, `mlnative/map.py:122-139`, `rust/src/main.rs:82-102`
- Category: security
- Reference: ASVS `v5.0.0-15.3.2`, `v5.0.0-15.2.5`
- Recommendation: In server contexts, expose style IDs from an allowlist instead of raw `style` strings, reject local paths / `file://`, and run the renderer with explicit egress restrictions if any untrusted input remains.
- Status: open

### 4) Render endpoints are expensive but ship without auth, quotas, caching, or concurrency budgets
- Location: `examples/fastapi_server.py:41-79`, `examples/web_test_server.py:112-129`, `examples/production_deployment.py:38-67`
- Category: security
- Reference: ASVS `v5.0.0-15.1.3`, `v5.0.0-15.2.2`
- Recommendation: Before any non-local exposure, add authentication, per-client rate limits, worker/concurrency caps, cache hot responses, and explicit time/size budgets.
- Status: open

### 5) The “production-ready” pool example can block forever and its health check performs a full remote render
- Location: `examples/production_deployment.py:58-67`, `examples/production_deployment.py:99-104`
- Category: performance
- Reference: ASVS `v5.0.0-15.1.3`; grugbrain.dev
- Recommendation: Use bounded wait times on `Queue.get()`, return overload errors instead of hanging, and split cheap liveness checks from heavyweight render/dependency checks.
- Status: open

### 6) Batch rendering still buffers the full response set in memory twice
- Location: `rust/src/main.rs:301-337`, `mlnative/_bridge.py:197-210`, `mlnative/_bridge.py:338-364`, `mlnative/map.py:238-246`
- Category: performance
- Reference: ASVS `v5.0.0-15.1.3`, `v5.0.0-15.2.2`
- Recommendation: Keep the view/pixel caps, but move to per-image streaming or chunked framing. The Rust side accumulates every PNG before send, and the Python side then reads the combined payload and copies each slice again.
- Status: open

### 7) `set_geojson()` still reloads the entire style document for every source update
- Location: `mlnative/map.py:438-482`
- Category: complexity
- Reference: ASVS `v5.0.0-15.1.3`; grugbrain.dev (“complexity very, very bad”)
- Recommendation: Add source-level mutation in Rust or separate immutable style from mutable data. The current full-style rewrite is a simple API, but it makes frequent data updates expensive and harder to reason about.
- Status: open

### 8) Release builds create “platform wheels” by renaming a pure `py3-none-any` wheel
- Location: `Justfile:96-114`, `.github/workflows/release.yml:83-90`, `pyproject.toml:54-57`
- Category: complexity
- Reference: ASVS `v5.0.0-15.1.2`; grugbrain.dev
- Recommendation: Use a real platform-wheel pipeline (`cibuildwheel`, `auditwheel`, `delocate`, `maturin`, or equivalent) or rewrite embedded wheel metadata consistently. The current release job renames the filename only; a local build still emits `Root-Is-Purelib: true` and `Tag: py3-none-any`.
- Status: resolved in 0.3.10 (`cibuildwheel` builds Linux platform wheels and repair retags wheel metadata)

### 9) CI integration tests depend on live third-party network and remote tile/style services
- Location: `tests/test_render.py:34-39`, `tests/test_render.py:85-95`, `.github/workflows/ci.yml:138-222`, `CONTRIBUTING.md`
- Category: complexity
- Reference: ASVS `v5.0.0-15.1.3`; grugbrain.dev
- Recommendation: Move CI to local fixtures, a pinned test style, or a local mock tile server. Current smoke/integration coverage is useful, but it is also coupled to OpenFreeMap availability and network latency.
- Status: open

### 10) Test container still bootstraps toolchain code via `curl | sh`
- Location: `Dockerfile.test:21`
- Category: security
- Reference: ASVS `v5.0.0-15.2.4`
- Recommendation: Pin a checksum or versioned installer artifact, or use a trusted package source instead of piping a live script directly into `sh`.
- Status: open

### 11) Release provenance action digest is already stale per local Renovate lookup
- Location: `.github/workflows/release.yml:161-163`, `.github/workflows/release.yml:200-202`, `renovate.json:1-3`
- Category: security
- Reference: ASVS `v5.0.0-15.1.1`, `v5.0.0-15.2.1`
- Recommendation: Refresh `actions/attest-build-provenance` to digest `a2bbfa25375fe432b6a289bc6b6cd05ecd0c4c32` and keep digest refreshes within the repo’s documented remediation window.
- Status: resolved in 0.3.10

## Resolved log
- Example servers now bind to loopback by default instead of `0.0.0.0` (`examples/fastapi_server.py:112`, `examples/web_test_server.py:165`).
- Native binary lookup now prefers packaged binaries and requires explicit opt-in for `PATH` fallback (`mlnative/_bridge.py:101-110`, `tests/test_bridge.py:33-57`).
- The old binary download helper now fails closed instead of downloading and executing an unverified artifact (`scripts/download-binary.py:36-53`).
- CI security scanning is wired back in via `uv run --frozen --with pip-audit pip-audit` (`.github/workflows/ci.yml`).
- `fit_bounds()` now enforces Web Mercator-safe latitude bounds and fails with `MlnativeError` instead of raw projection errors (`mlnative/map.py:333-352`).
- `geopy` is no longer a core runtime dependency; it lives in the optional `geo` extra (`pyproject.toml:26-33`).
