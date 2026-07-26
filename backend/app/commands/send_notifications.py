import argparse

from sqlalchemy.orm import Session

from app.core.config import get_management_settings
from app.database.session import create_database_engine
from app.features.notifications.worker import NotificationWorker


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Deliver pending Family Hub Web Push notifications")
    parser.add_argument("--limit", type=int, default=100, choices=range(1, 1001), metavar="1-1000")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    settings = get_management_settings()
    if (
        not settings.push_vapid_private_key_file
        or not settings.push_vapid_public_key
        or not settings.push_vapid_subject
    ):
        raise SystemExit("Web Push is not configured")
    engine = create_database_engine(settings)
    try:
        with Session(engine, expire_on_commit=False) as session:
            processed = NotificationWorker(session, settings).process(limit=args.limit)
    finally:
        engine.dispose()
    print(f"Processed {processed} notification(s)")


if __name__ == "__main__":
    main()
