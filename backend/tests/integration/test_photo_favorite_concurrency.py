import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from threading import Event
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, delete, func, select
from sqlalchemy.orm import Session

from app.features.auth.models import SystemRole, User
from app.features.photos.access_service import PhotoAccessService
from app.features.photos.models import Photo, PhotoFavorite, PhotoLifecycleState
from app.features.photos.storage import PhotoStorage

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(TEST_DATABASE_URL is None, reason="TEST_DATABASE_URL is not configured"),
]


def test_concurrent_favorite_registration_is_idempotent() -> None:
    assert TEST_DATABASE_URL is not None
    engine = create_engine(TEST_DATABASE_URL, connect_args={"options": "-c timezone=UTC"})
    user_id = uuid4()
    photo_id = uuid4()
    now = datetime.now(UTC)

    with Session(engine) as session:
        session.add_all(
            [
                User(
                    id=user_id,
                    username=f"favorite-race-{user_id.hex}",
                    password_hash="unused",
                    is_active=True,
                    system_role=SystemRole.USER,
                    created_at=now,
                    password_changed_at=now,
                ),
                Photo(
                    id=photo_id,
                    uploaded_by_user_id=user_id,
                    uploaded_by_username=f"favorite-race-{user_id.hex}",
                    original_filename="favorite.jpg",
                    storage_key=f"originals/2026/08/{photo_id}.jpg",
                    content_type="image/jpeg",
                    size_bytes=1,
                    sha256="b" * 64,
                    width=1,
                    height=1,
                    captured_at_original=None,
                    uploaded_at=now,
                    effective_captured_at=now,
                    lifecycle_state=PhotoLifecycleState.ACTIVE,
                ),
            ]
        )
        session.commit()

    start = Event()

    def set_favorite() -> str:
        assert start.wait(timeout=5)
        with Session(engine) as session:
            PhotoAccessService(session, MagicMock(spec=PhotoStorage)).set_favorite(photo_id, user_id, True)
        return "ok"

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(set_favorite), executor.submit(set_favorite)]
            start.set()
            assert [future.result(timeout=10) for future in futures] == ["ok", "ok"]

        with Session(engine) as session:
            assert (
                session.scalar(
                    select(func.count())
                    .select_from(PhotoFavorite)
                    .where(PhotoFavorite.user_id == user_id, PhotoFavorite.photo_id == photo_id)
                )
                == 1
            )
    finally:
        with Session(engine) as session:
            session.execute(delete(Photo).where(Photo.id == photo_id))
            session.execute(delete(User).where(User.id == user_id))
            session.commit()
        engine.dispose()
