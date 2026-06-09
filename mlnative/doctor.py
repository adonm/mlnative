"""Runtime diagnostics for mlnative installations."""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass

from ._bridge import PATH_BINARY_OPT_IN_ENV, _get_platform_info, _get_timeout, get_binary_path
from .exceptions import MlnativeError
from .map import Map


@dataclass(frozen=True)
class CheckResult:
    """One diagnostic check result."""

    name: str
    ok: bool
    detail: str


def _check_platform() -> CheckResult:
    try:
        platform, arch = _get_platform_info()
    except MlnativeError as e:
        return CheckResult("platform", False, str(e))
    return CheckResult("platform", True, f"{platform}-{arch}")


def _check_timeout(timeout: float | None) -> CheckResult:
    try:
        value = _get_timeout(timeout)
    except MlnativeError as e:
        return CheckResult("timeout", False, str(e))
    return CheckResult("timeout", True, f"{value:g}s")


def _check_binary() -> CheckResult:
    try:
        path = get_binary_path()
    except MlnativeError as e:
        return CheckResult("binary", False, str(e).splitlines()[0])

    executable = os.access(path, os.X_OK) if sys.platform != "win32" else True
    if not executable:
        return CheckResult("binary", False, f"found but not executable: {path}")
    return CheckResult("binary", True, str(path))


def _check_render(timeout: float | None) -> CheckResult:
    style = {"version": 8, "sources": {}, "layers": []}
    try:
        with Map(64, 64, timeout=timeout) as map_renderer:
            map_renderer.load_style(style)
            png = map_renderer.render(center=(0, 0), zoom=0)
    except MlnativeError as e:
        return CheckResult("render", False, str(e))
    except Exception as e:
        return CheckResult("render", False, f"unexpected render check failure: {e}")

    if not png.startswith(b"\x89PNG"):
        return CheckResult("render", False, "renderer returned non-PNG bytes")
    return CheckResult("render", True, f"rendered {len(png)} bytes")


def run_checks(*, render: bool = False, timeout: float | None = None) -> list[CheckResult]:
    """Run installation diagnostics without raising on expected failures."""
    checks = [_check_platform(), _check_timeout(timeout), _check_binary()]
    if render:
        checks.append(_check_render(timeout))
    return checks


def _format_result(result: CheckResult) -> str:
    marker = "ok" if result.ok else "fail"
    return f"[{marker}] {result.name}: {result.detail}"


def main(argv: list[str] | None = None) -> int:
    """Run the diagnostic CLI."""
    parser = argparse.ArgumentParser(description="Check an mlnative installation")
    parser.add_argument(
        "--render",
        action="store_true",
        help="also start the renderer and render a tiny local-style PNG",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=None,
        help="renderer timeout in seconds for checks that start the daemon",
    )
    args = parser.parse_args(argv)

    results = run_checks(render=args.render, timeout=args.timeout)
    for result in results:
        print(_format_result(result))

    if not all(result.ok for result in results):
        print(
            f"Hint: packaged wheels include the native renderer. Set {PATH_BINARY_OPT_IN_ENV}=1 "
            "only if you intentionally want PATH binary lookup."
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
