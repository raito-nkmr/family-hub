from sqlalchemy import CheckConstraint, ForeignKeyConstraint, UniqueConstraint

from app.features.photos.models import (
    Photo,
    PhotoActivityEvent,
    PhotoActivityEventGroup,
    PhotoActivityState,
    PhotoDerivative,
    PhotoMetadata,
    PhotoShare,
    UploadBatch,
)


def test_photo_table_has_expected_constraints() -> None:
    constraints = {constraint.name: constraint for constraint in Photo.__table__.constraints}

    assert set(constraints) == {
        "ck_photos_dimensions",
        "ck_photos_lifecycle_fields",
        "ck_photos_lifecycle_state",
        "ck_photos_sha256_lower_hex",
        "ck_photos_size_bytes_positive",
        "fk_photos_uploaded_by_user_id_users",
        "fk_photos_trashed_by_user_id_users",
        "pk_photos",
        "uq_photos_uploaded_by_user_id_sha256",
        "uq_photos_storage_key",
    }
    assert isinstance(constraints["ck_photos_dimensions"], CheckConstraint)
    assert str(constraints["ck_photos_dimensions"].sqltext) == "width > 0 AND height > 0"
    assert Photo.__table__.c.width.nullable is False
    assert Photo.__table__.c.height.nullable is False
    assert Photo.__table__.c.effective_captured_at.nullable is False
    assert isinstance(constraints["fk_photos_uploaded_by_user_id_users"], ForeignKeyConstraint)
    duplicate_constraint = constraints["uq_photos_uploaded_by_user_id_sha256"]
    assert isinstance(duplicate_constraint, UniqueConstraint)
    assert [column.name for column in duplicate_constraint.columns] == ["uploaded_by_user_id", "sha256"]


def test_photo_table_has_sort_index() -> None:
    indexes = {index.name: index for index in Photo.__table__.indexes}

    assert set(indexes) == {
        "ix_photos_original_filename_trgm",
        "ix_photos_lifecycle_purge_after",
        "ix_photos_sort_date_id",
        "ix_photos_uploaded_by_user_id",
        "ix_photos_trashed_by_user_id",
    }
    assert len(indexes["ix_photos_sort_date_id"].expressions) == 2
    assert str(indexes["ix_photos_sort_date_id"].expressions[0]) == "photos.effective_captured_at DESC"


def test_photo_metadata_and_sharing_tables_have_expected_constraints() -> None:
    metadata_constraints = {constraint.name for constraint in PhotoMetadata.__table__.constraints}
    share_constraints = {constraint.name for constraint in PhotoShare.__table__.constraints}

    assert "ck_photo_metadata_memo_length" in metadata_constraints
    assert "ck_photo_metadata_version_positive" in metadata_constraints
    assert {index.name for index in PhotoMetadata.__table__.indexes} == {
        "ix_photo_metadata_memo_trgm",
        "ix_photo_metadata_memo_updated_by_user_id",
    }
    assert "uq_photo_shares_photo_id_group_id" in share_constraints
    assert "ck_upload_batches_visibility" not in {constraint.name for constraint in UploadBatch.__table__.constraints}


def test_photo_derivative_table_has_expected_constraints() -> None:
    constraints = {constraint.name for constraint in PhotoDerivative.__table__.constraints}

    assert "ck_photo_derivatives_kind" in constraints
    assert "ck_photo_derivatives_dimensions" in constraints
    assert "uq_photo_derivatives_photo_id_kind" in constraints
    assert "uq_photo_derivatives_storage_key" in constraints


def test_photo_activity_tables_have_expected_constraints_and_indexes() -> None:
    event_constraints = {constraint.name for constraint in PhotoActivityEvent.__table__.constraints}

    assert "ck_photo_activity_events_event_type" in event_constraints
    assert "fk_photo_activity_events_photo_id_photos" in event_constraints
    assert {index.name for index in PhotoActivityEvent.__table__.indexes} == {
        "ix_photo_activity_events_occurred_at_id",
        "ix_photo_activity_events_photo_id",
        "ix_photo_activity_events_operation_id",
    }
    assert {constraint.name for constraint in PhotoActivityEventGroup.__table__.constraints} >= {
        "pk_photo_activity_event_groups",
        "fk_photo_activity_event_groups_group_id_family_groups",
    }
    assert {constraint.name for constraint in PhotoActivityState.__table__.constraints} >= {
        "pk_photo_activity_states",
        "fk_photo_activity_states_user_id_users",
    }
