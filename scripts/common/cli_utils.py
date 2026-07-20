"""CLI argument helpers for crawler scripts."""

import argparse


def add_rate_limit_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--rate-limit",
        choices=["auto", "off", "fixed", "adaptive"],
        default="auto",
        help="Rate limiting mode (default: auto)",
    )


def add_output_arg(parser: argparse.ArgumentParser, default: str = ".") -> None:
    parser.add_argument("-o", "--output", default=default, help="Output directory")


def add_no_cache_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--no-cache", action="store_true", help="Disable cache")


def add_common_cli_args(parser: argparse.ArgumentParser) -> None:
    add_rate_limit_arg(parser)
    add_output_arg(parser)
    add_no_cache_arg(parser)
