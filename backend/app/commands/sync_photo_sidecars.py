from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_management_settings
from app.database.session import create_database_engine
from app.features.photos.models import Photo
from app.features.photos.registration import build_sidecar_metadata
from app.features.photos.storage import PhotoStorage


def sync_photo_sidecars(session: Session, storage: PhotoStorage) -> int:
    photos = session.scalars(select(Photo).order_by(Photo.id)).all()
    for photo in photos:
        storage.update_sidecar(build_sidecar_metadata(photo))
    return len(photos)


def main() -> None:
    settings = get_management_settings()
    engine = create_database_engine(settings)
    try:
        with Session(engine) as session:
            synced_count = sync_photo_sidecars(session, PhotoStorage(settings))
    finally:
        engine.dispose()
    print(f"Synchronized {synced_count} photo sidecar(s)")


if __name__ == "__main__":
    main()
