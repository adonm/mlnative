# Audit Issues

- Date: 2026-04-02
- Commit: `2ad80ce49f12`
- Codebase summary (`sloc`): 49 files, 2,470 code LOC, 1,290 documentation LOC, 5,670 total lines; main languages: Python 1,654 LOC, YAML 353 LOC, Rust 249 LOC.
- Scope: Python wrapper (`mlnative/`), Rust renderer (`rust/`), example servers (`examples/`), CI/release workflows (`.github/workflows/`), and helper scripts (`scripts/`).
- Audit references: [OWASP ASVS 5.0](https://owasp.org/www-project-application-security-verification-standard/) with emphasis on [V15 Secure Coding and Architecture](https://raw.githubusercontent.com/OWASP/ASVS/v5.0.0/5.0/en/0x24-V15-Secure-Coding-and-Architecture.md), [V16 Security Logging and Error Handling](https://raw.githubusercontent.com/OWASP/ASVS/v5.0.0/5.0/en/0x25-V16-Security-Logging-and-Error-Handling.md), and [grugbrain.dev](https://grugbrain.dev/).

## Prioritized findings

### 1) User-controlled `style` reaches network and filesystem loaders
- Location: `examples/fastapi_server.py:42-76`, `examples/web_test_server.py:43-126`, `mlnative/map.py:118-136`, `rust/src/main.rs:82-97`
- Category: security
- Reference: ASVS `v5.0.0-15.3.2`, `v5.0.0-15.2.5`
- Recommendation: Do not accept arbitrary style URLs/paths from request data. Expose style IDs from an allowlist, reject local paths/`file://` in server contexts, and keep redirect behavior explicit.
- Status: open

### 2) Example render endpoints are expensive, unauthenticated, and bind publicly by default
- Location: `examples/fastapi_server.py:33-101`, `examples/web_test_server.py:96-155`
- Category: security
- Reference: ASVS `v5.0.0-15.1.3`, `v5.0.0-15.2.2`
- Recommendation: Keep demo servers on `127.0.0.1` by default and add auth, rate limits, concurrency caps, request budgets, and caching before any non-local exposure.
- Status: open

### 3) Errors are leaked to clients while renderer stderr is discarded
- Location: `examples/fastapi_server.py:82-83`, `examples/web_test_server.py:132-140`, `mlnative/_bridge.py:114-120`
- Category: security
- Reference: ASVS `v5.0.0-16.5.1`, `v5.0.0-16.3.4`
- Recommendation: Return generic client errors, log structured exceptions server-side, and retain renderer stderr behind a debug/logging path instead of dropping it.
- Status: open

### 4) Native binary resolution still trusts the first `PATH` hit
- Location: `mlnative/_bridge.py:70-92`
- Category: security
- Reference: ASVS `v5.0.0-15.2.4`, `v5.0.0-15.2.5`
- Recommendation: Prefer packaged binaries only by default. If overrides are needed, gate them behind explicit opt-in and verify ownership/hash/signature.
- Status: open

### 5) Binary download helper executes unverified release artifacts
- Location: `scripts/download-binary.py:36-74`
- Category: security
- Reference: ASVS `v5.0.0-15.2.4`
- Recommendation: Verify checksums/signatures before `chmod +x`, or remove the helper and rely on trusted package distribution only.
- Status: open

### 6) CI dependency scanning is currently broken; maintenance updates are also pending
- Location: `.github/workflows/ci.yml:77-91`, `pyproject.toml:23-40`, `.mise.toml:1-5`, `rust/Cargo.toml:9-15`
- Category: security
- Reference: ASVS `v5.0.0-15.1.1`, `v5.0.0-15.2.1`
- Recommendation: Make the scan runnable in CI (`uvx pip-audit`, or add `pip-audit` to the CI environment) and review the local Renovate lookup deltas, notably `tempfile 3.23→3.27`, `rust 1.90.0→1.94.1`, `just 1.46.0→1.48.1`, `python 3.12→3.14.3`, and the `actions/attest-build-provenance` digest refresh.
- Status: open

### 7) `fit_bounds()` accepts `-90` latitude then falls into a raw `math domain error`
- Location: `mlnative/map.py:317-344`
- Category: security
- Reference: ASVS `v5.0.0-16.5.3`
- Recommendation: Reject/clamp to Web Mercator-safe latitude bounds before projection and convert failures to `MlnativeError` consistently.
- Status: open

### 8) Batch rendering has no request cap and buffers all PNGs in memory at once
- Location: `mlnative/map.py:229-278`, `mlnative/_bridge.py:166-176`, `rust/src/main.rs:287-327`
- Category: performance
- Reference: ASVS `v5.0.0-15.1.3`, `v5.0.0-15.2.2`
- Recommendation: Add view-count/output-size limits and prefer streaming or chunked framing over whole-batch buffering for large jobs.
- Status: open

### 9) JSON style reloads leak temp files for the daemon lifetime
- Location: `rust/src/main.rs:65-94`, `rust/src/main.rs:140-146`
- Category: performance
- Reference: ASVS `v5.0.0-15.1.3`
- Recommendation: Reuse a single temp style file or drop old `NamedTempFile`s before pushing new ones; repeated `reload_style()`/`set_geojson()` currently grows file descriptors and temp storage monotonically.
- Status: open

### 10) `set_geojson()` reloads the entire style for each source update
- Location: `mlnative/map.py:413-451`
- Category: complexity
- Reference: ASVS `v5.0.0-15.1.3`; grugbrain.dev (“complexity very, very bad”)
- Recommendation: Add source-level mutation in Rust, or clearly document/cap the full-style reload cost for update-heavy workloads.
- Status: open

### 11) `geopy` is a required runtime dependency even though the library core does not use it
- Location: `pyproject.toml:24-29`, `README.md:21-25`, `examples/address_rendering.py:1-26`
- Category: complexity
- Reference: ASVS `v5.0.0-15.2.3`; grugbrain.dev
- Recommendation: Move geocoding dependencies into an example/extra (for example `geo` or `examples`) so the core renderer ships with a smaller attack and maintenance surface.
- Status: open

## Resolved log
- Previously flagged workflow action drift is resolved in the current tree: committed workflow YAML is digest-pinned (`.github/workflows/ci.yml`, `.github/workflows/release.yml`).
- Previously flagged predictable temp style filenames are resolved: the Rust daemon now uses `tempfile::NamedTempFile` (`rust/src/main.rs`).
- Previously flagged unit-test selection drift is resolved: `just test-unit` now excludes only `integration` tests (`Justfile:34-36`).
- Previously flagged floating tool versions are resolved: `.mise.toml` now pins Python, Rust, Just, and uv (`.mise.toml:1-5`).
- Previously flagged dead vendored Node renderer surface is resolved in the current tree: the tracked JS renderer/vendor files are gone from `mlnative/`.
- Previously flagged Rust patch lag is resolved: `maplibre_native` and `image` are already at the looked-up current versions in `rust/Cargo.toml`.
- Previously flagged PNG base64 transport/thread-per-command issues are resolved: the current bridge uses a persistent reader thread and raw binary payload framing (`mlnative/_bridge.py`, `rust/src/main.rs`).
