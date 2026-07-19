import argparse
from pathlib import Path

from app.modules.manifest import write_manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate an edition build manifest")
    parser.add_argument("--edition", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    write_manifest(edition=args.edition, output=args.output)


if __name__ == "__main__":
    main()
