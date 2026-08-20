import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Event
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import Session

from app.features.auth.models import SystemRole, User
from app.features.auth.passwords import hash_password
from app.features.photos.models import UploadBatch, UploadBatchStatus, UploadItem, UploadItemStatus
from app.features.photos.storage import PhotoStorage
from app.features.photos.uploads import UploadBatchService

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(TEST_DATABASE_URL is None, reason="TEST_DATABASE_URL is not configured"),
]


def test_expiration_cleanup_waits_for_an_existing_upload_row_lock() -> None:
    assert TEST_DATABASE_URL is not None
    engine = create_engine(TEST_DATABASE_URL, connect_args={"options": "-c timezone=UTC"})
    now = datetime.now(UTC)
    user_id = uuid4()
    batch_id = uuid4()
    item_id = uuid4()
    user = User(
        id=user_id,
        username=f"upload-lock-{user_id.hex}",
        password_hash=hash_password("unused-password"),
        is_active=True,
        system_role=SystemRole.USER,
        created_at=now,
        password_changed_at=now,
    )
    batch = UploadBatch(
        id=batch_id,
        owner_user_id=user_id,
        status=UploadBatchStatus.ACTIVE,
        created_at=now - timedelta(hours=1),
        expires_at=now - timedelta(minutes=1),
        completed_at=None,
    )
    item = UploadItem(
        id=item_id,
        batch_id=batch_id,
        client_id="upload-lock-item",
        original_filename="photo.jpg",
        declared_content_type="image/jpeg",
        size_bytes=5,
        received_bytes=3,
        status=UploadItemStatus.UPLOADING,
        error_code=None,
        photo_id=None,
        created_at=now - timedelta(hours=1),
        completed_at=None,
    )

    with Session(engine) as session:
        session.add_all([user, batch, item])
        session.commit()

    lock_acquired = Event()
    release_lock = Event()
    expiration_started = Event()
    cleanup_called = Event()

    def hold_upload_lock() -> None:
        with Session(engine) as session:
            session.execute(
                select(UploadBatch, UploadItem)
                .join(UploadItem, UploadItem.batch_id == UploadBatch.id)
                .where(UploadItem.id == item_id, UploadBatch.owner_user_id == user_id)
                .with_for_update()
            ).one()
            lock_acquired.set()
            assert release_lock.wait(timeout=5)
            session.commit()

    def expire_batches() -> None:
        storage = MagicMock(spec=PhotoStorage)
        storage.cleanup_resumable.side_effect = lambda _: cleanup_called.set()
        expiration_service = UploadBatchService(
            Session(engine),
            storage,
            "Asia/Tokyo",
        )
        try:
            expiration_started.set()
            expiration_service._expire_stale_batches()
        finally:
            expiration_service._session.close()

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            lock_future = executor.submit(hold_upload_lock)
            assert lock_acquired.wait(timeout=5)
            expiration_future = executor.submit(expire_batches)
            assert expiration_started.wait(timeout=5)
            assert not cleanup_called.wait(timeout=0.2)
            release_lock.set()
            lock_future.result(timeout=5)
            expiration_future.result(timeout=5)

        assert cleanup_called.is_set()
        with Session(engine) as session:
            refreshed_batch = session.get(UploadBatch, batch_id)
            refreshed_item = session.get(UploadItem, item_id)
            assert refreshed_batch is not None
            assert refreshed_item is not None
            assert refreshed_batch.status == UploadBatchStatus.CANCELED
            assert refreshed_item.status == UploadItemStatus.FAILED
    finally:
        release_lock.set()
        with Session(engine) as session:
            session.execute(delete(User).where(User.id == user_id))
            session.commit()
        engine.dispose()
