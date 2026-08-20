from datetime import UTC, datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.features.photos.models import PhotoVisibility
from app.features.photos.schemas import (
    BulkPhotoSharingAdd,
    PhotoExportRequest,
    PhotoListQuery,
    PhotoSharing,
    PhotoUpdate,
    photo_response_from_model,
)
from tests.features.photos.factories import make_photo


def test_photo_response_normalizes_datetimes_to_utc() -> None:
    photo = make_photo()
    photo.captured_at = datetime(2026, 7, 14, 12, tzinfo=timezone(timedelta(hours=9)))

    response = photo_response_from_model(photo, visible_group_ids=set(), is_favorite=False)

    assert response.captured_at == datetime(2026, 7, 14, 3, tzinfo=UTC)
    assert response.uploaded_by_user_id == photo.uploaded_by_user_id
    assert response.uploaded_by_username == "owner"
    assert response.memo is None
    assert response.memo_updated_by_user_id == photo.uploaded_by_user_id
    assert response.memo_updated_by_username == photo.uploaded_by_username
    assert response.memo_updated_at == photo.uploaded_at
    assert response.metadata_version == 1
    assert response.sharing.type is PhotoVisibility.PRIVATE
    assert '"captured_at":"2026-07-14T03:00:00Z"' in response.model_dump_json()


def test_photo_response_rejects_naive_datetime() -> None:
    photo = make_photo()
    photo.uploaded_at = datetime(2026, 7, 14, 4)

    with pytest.raises(ValidationError, match="photo datetimes must be timezone-aware"):
        photo_response_from_model(photo, visible_group_ids=set(), is_favorite=False)


@pytest.mark.parametrize(("width", "height"), [(None, 480), (640, None), (0, 480), (640, 0), (-1, 480), (640, -1)])
def test_photo_response_requires_positive_dimensions(width: int | None, height: int | None) -> None:
    photo = make_photo()
    photo.width = width  # type: ignore[assignment]
    photo.height = height  # type: ignore[assignment]

    with pytest.raises(ValidationError):
        photo_response_from_model(photo, visible_group_ids=set(), is_favorite=False)


def test_photo_response_only_contains_share_groups_visible_to_viewer() -> None:
    photo = make_photo(visibility=PhotoVisibility.SHARED)
    hidden_group_id = photo.shares[0].group_id

    response = photo_response_from_model(photo, visible_group_ids=set(), is_favorite=False)

    assert response.sharing.type is PhotoVisibility.SHARED
    assert response.sharing.group_ids == []
    assert hidden_group_id not in response.sharing.group_ids


def test_photo_update_normalizes_memo_and_requires_a_change() -> None:
    update = PhotoUpdate(
        memo="  北海道旅行\n",
        sharing=PhotoSharing(
            type=PhotoVisibility.SHARED,
            group_ids=["00000000-0000-4000-8000-000000000001"],
        ),
        version=1,
    )

    assert update.memo == "北海道旅行"

    with pytest.raises(ValidationError, match="memo, sharing, or captured_at_override"):
        PhotoUpdate(version=1)

    with pytest.raises(ValidationError, match="shared photos require at least one group"):
        PhotoSharing(type=PhotoVisibility.SHARED)


def test_photo_list_query_normalizes_search_and_validates_combinations() -> None:
    query = PhotoListQuery(q="  北海道旅行 ")

    assert query.q == "北海道旅行"

    with pytest.raises(ValidationError, match="date_from must not be after date_to"):
        PhotoListQuery(date_from="2026-08-01", date_to="2026-07-01")
    with pytest.raises(ValidationError, match="mine_only and uploader_id"):
        PhotoListQuery(mine_only=True, uploader_id="00000000-0000-4000-8000-000000000001")
    with pytest.raises(ValidationError, match="album_id and exclude_album_id"):
        PhotoListQuery(
            album_id="00000000-0000-4000-8000-000000000001",
            exclude_album_id="00000000-0000-4000-8000-000000000002",
        )


def test_bulk_photo_sharing_requires_unique_bounded_photo_ids() -> None:
    photo_id = "00000000-0000-4000-8000-000000000001"
    group_id = "00000000-0000-4000-8000-000000000002"

    with pytest.raises(ValidationError, match="identifiers must not contain duplicates"):
        BulkPhotoSharingAdd(photo_ids=[photo_id, photo_id], add_group_ids=[group_id])
    with pytest.raises(ValidationError):
        BulkPhotoSharingAdd(
            photo_ids=[str(index).zfill(8) + "-0000-4000-8000-000000000001" for index in range(101)],
            add_group_ids=[group_id],
        )


def test_photo_export_requires_unique_photo_ids() -> None:
    photo_id = "00000000-0000-4000-8000-000000000001"

    with pytest.raises(ValidationError, match="photo_ids must not contain duplicates"):
        PhotoExportRequest(photo_ids=[photo_id, photo_id])
