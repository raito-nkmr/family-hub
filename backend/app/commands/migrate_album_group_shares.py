"""Copy legacy single-group album ownership into album group shares."""

import argparse

from sqlalchemy import insert, select, text
from sqlalchemy.orm import Session

from app.core.config import get_management_settings
from app.database.session import create_database_engine
from app.features.albums.models import AlbumGroupShare


def migrate(session: Session, *, apply: bool) -> int:
    legacy_rows = session.execute(text("SELECT id, group_id FROM albums WHERE group_id IS NOT NULL ORDER BY id")).all()
    migrated = 0
    for album_id, group_id in legacy_rows:
        existing = session.scalar(
            select(AlbumGroupShare.album_id).where(
                AlbumGroupShare.album_id == album_id,
                AlbumGroupShare.group_id == group_id,
            )
        )
        if existing is not None:
            continue
        session.execute(
            insert(AlbumGroupShare).values(
                album_id=album_id,
                group_id=group_id,
            )
        )
        migrated += 1
    if apply:
        session.commit()
    else:
        session.rollback()
    return migrated


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate legacy album group associations")
    parser.add_argument("--apply", action="store_true", help="Commit the migration")
    arguments = parser.parse_args()
    settings = get_management_settings()
    engine = create_database_engine(settings)
    try:
        with Session(engine, expire_on_commit=False) as session:
            migrated = migrate(session, apply=arguments.apply)
    finally:
        engine.dispose()
    action = "Migrated" if arguments.apply else "Would migrate"
    print(f"{action} {migrated} album group share(s)")


if __name__ == "__main__":
    main()
