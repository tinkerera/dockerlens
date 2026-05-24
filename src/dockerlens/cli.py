import argparse
import sys
from typing import Optional

from dockerlens import ImageAnalyzer
from dockerlens.exceptions import DockerLensError, ImageNotFound


def main(args: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Programmatic Docker image layer analysis, auditing, and diffing."
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    subparsers.required = True

    analyze_parser = subparsers.add_parser("analyze", help="Analyze a Docker image")
    analyze_parser.add_argument(
        "image", help="Name/tag of the Docker image (e.g. nginx:latest)"
    )
    analyze_parser.add_argument(
        "--format",
        choices=["text", "json", "markdown", "html"],
        default="text",
        help="Output format",
    )
    analyze_parser.add_argument(
        "--remote",
        action="store_true",
        help="Scan image directly from remote registry without pulling",
    )

    diff_parser = subparsers.add_parser("diff", help="Compare two Docker images")
    diff_parser.add_argument("image_a", help="First image to compare")
    diff_parser.add_argument("image_b", help="Second image to compare")

    parsed_args = parser.parse_args(args)

    try:
        if parsed_args.command == "analyze":
            analyzer = ImageAnalyzer(parsed_args.image, remote=parsed_args.remote)
            if parsed_args.format == "text":
                analyzer.print_layers()
                analyzer.print_audit()
            else:
                report = analyzer.report()
                if parsed_args.format == "json":
                    print(report.to_json())
                elif parsed_args.format == "markdown":
                    print(report.to_markdown())
                elif parsed_args.format == "html":
                    print(report.to_html())

        elif parsed_args.command == "diff":
            analyzer = ImageAnalyzer(parsed_args.image_a)
            analyzer.print_diff(parsed_args.image_b)

    except ImageNotFound as e:
        if getattr(parsed_args, "remote", False):
            print(f"Error: {e}", file=sys.stderr)
        else:
            print(
                f"Error: Image not found locally: {e.image_name!r}.\n"
                f"Pull it first with `docker pull {e.image_name}` or "
                f"use the `--remote` flag to scan online.",
                file=sys.stderr,
            )
        return 1
    except DockerLensError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
