"""cibuildwheel helpers for platform wheels.

The package is pure Python plus a platform-specific renderer executable. Hatch
correctly builds the package contents, but the wheel metadata needs platform
tags because the embedded executable is not portable. This script is used by
cibuildwheel to build the binary before packaging and retag the wheel during
the repair step.
"""

from __future__ import annotations

import base64
import hashlib
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BIN_DIR = ROOT / "mlnative" / "bin"
RUST_DIR = ROOT / "rust"

PLATFORM_TAGS = {
    "x86_64": ("linux-x64", "manylinux_2_28_x86_64"),
    "aarch64": ("linux-arm64", "manylinux_2_28_aarch64"),
}


def _target_platform() -> tuple[str, str]:
    arch = os.environ.get("AUDITWHEEL_ARCH") or os.uname().machine
    try:
        return PLATFORM_TAGS[arch]
    except KeyError as e:
        supported = ", ".join(sorted(PLATFORM_TAGS))
        raise SystemExit(
            f"Unsupported cibuildwheel architecture '{arch}'. Supported: {supported}"
        ) from e


def _run(cmd: list[str], cwd: Path = ROOT) -> None:
    subprocess.run(cmd, cwd=cwd, check=True)


def _build_binary(platform: str) -> None:
    _run(["cargo", "build", "--release", "--locked"], cwd=RUST_DIR)
    BIN_DIR.mkdir(parents=True, exist_ok=True)
    for old_binary in BIN_DIR.glob("mlnative-render-*"):
        old_binary.unlink()
    source = RUST_DIR / "target" / "release" / "mlnative-render"
    target = BIN_DIR / f"mlnative-render-{platform}"
    shutil.copy2(source, target)
    target.chmod(0o755)


def _rewrite_wheel_tag(wheel: Path, platform_tag: str) -> Path:
    pure_suffix = "-py3-none-any.whl"
    if not wheel.name.endswith(pure_suffix):
        raise SystemExit(f"Unexpected wheel name from hatch build: {wheel.name}")

    tagged_wheel = wheel.with_name(wheel.name.replace(pure_suffix, f"-py3-none-{platform_tag}.whl"))
    record_path: str | None = None
    records: list[str] = []

    with (
        zipfile.ZipFile(wheel, "r") as src,
        zipfile.ZipFile(
            tagged_wheel,
            "w",
            compression=zipfile.ZIP_DEFLATED,
        ) as dst,
    ):
        for item in src.infolist():
            if item.filename.endswith(".dist-info/RECORD"):
                record_path = item.filename
                continue

            data = src.read(item.filename)
            if item.filename.endswith(".dist-info/WHEEL"):
                text = data.decode("utf-8")
                text = text.replace("Root-Is-Purelib: true", "Root-Is-Purelib: false")
                text = text.replace("Tag: py3-none-any", f"Tag: py3-none-{platform_tag}")
                data = text.encode("utf-8")
            dst.writestr(item, data)
            digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode()
            records.append(f"{item.filename},sha256={digest},{len(data)}")

        if record_path is None:
            raise SystemExit(f"Wheel RECORD file not found in {wheel}")
        records.append(f"{record_path},,")
        dst.writestr(record_path, "\n".join(records) + "\n")

    wheel.unlink()
    return tagged_wheel


def _build_binary_command() -> None:
    platform, platform_tag = _target_platform()
    del platform_tag
    _build_binary(platform)


def _retag_command(wheel: Path, dest_dir: Path) -> None:
    _platform, platform_tag = _target_platform()
    dest_dir.mkdir(parents=True, exist_ok=True)
    work_wheel = dest_dir / wheel.name
    shutil.copy2(wheel, work_wheel)
    tagged = _rewrite_wheel_tag(work_wheel, platform_tag)
    print(f"Created platform wheel: {tagged}")


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("Usage: build_cibw_wheel.py build-binary|retag <wheel> <dest_dir>")

    command = sys.argv[1]
    if command == "build-binary":
        _build_binary_command()
        return

    if command == "retag":
        if len(sys.argv) != 4:
            raise SystemExit("Usage: build_cibw_wheel.py retag <wheel> <dest_dir>")
        _retag_command(Path(sys.argv[2]), Path(sys.argv[3]))
        return

    raise SystemExit(f"Unknown command: {command}")


if __name__ == "__main__":
    main()
