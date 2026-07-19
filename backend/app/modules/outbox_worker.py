import argparse
import time

from sqlmodel import Session

from app.core.db import engine
from app.modules.outbox import dispatch_pending_events


def main() -> None:
    parser = argparse.ArgumentParser(description="Dispatch transactional outbox events")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--poll-seconds", type=float, default=1.0)
    args = parser.parse_args()
    while True:
        with Session(engine) as session:
            delivered, failed = dispatch_pending_events(session=session)
            session.commit()
        if args.once:
            return
        if delivered == 0 and failed == 0:
            time.sleep(max(0.1, args.poll_seconds))


if __name__ == "__main__":
    main()
