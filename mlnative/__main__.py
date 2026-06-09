"""Command line entry point for `python -m mlnative`."""

from __future__ import annotations

import argparse

from .doctor import main as doctor_main


def main() -> int:
    """Dispatch mlnative subcommands."""
    parser = argparse.ArgumentParser(prog="python -m mlnative")
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("doctor", help="check the local mlnative installation")
    args, remaining = parser.parse_known_args()

    if args.command == "doctor":
        return doctor_main(remaining)

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
