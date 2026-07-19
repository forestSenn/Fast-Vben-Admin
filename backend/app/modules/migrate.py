import argparse

from app.core.config import settings
from app.modules.migrations import migrate_edition


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate an edition under the module orchestrator")
    parser.add_argument("--edition", default=settings.APP_EDITION)
    args = parser.parse_args()
    migrate_edition(edition=args.edition)


if __name__ == "__main__":
    main()
