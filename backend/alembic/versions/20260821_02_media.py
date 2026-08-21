"""Create the media, activity, upload, and album schema.

Revision ID: 20260821_02_media
Revises: 20260821_01_core
Create Date: 2026-08-21

"""

# Alembic operations are kept explicit so this revision remains independent
# from the evolving SQLAlchemy model definitions.
# ruff: noqa: E501

import sqlalchemy as sa

from alembic import op

revision: str = "20260821_02_media"
down_revision: str | None = "20260821_01_core"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "photos",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("uploaded_by_user_id", sa.UUID(), nullable=False),
        sa.Column("uploaded_by_username", sa.String(length=64), nullable=False),
        sa.Column("original_filename", sa.Text(), nullable=False),
        sa.Column("storage_key", sa.Text(), nullable=False),
        sa.Column("content_type", sa.Text(), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "uploaded_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.Column("effective_captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lifecycle_state", sa.String(length=16), server_default="active", nullable=False),
        sa.Column("trashed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("trashed_by_user_id", sa.UUID(), nullable=True),
        sa.Column("purge_after", sa.DateTime(timezone=True), nullable=True),
        sa.Column("purge_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "(lifecycle_state = 'active' AND trashed_at IS NULL AND trashed_by_user_id IS NULL AND purge_after IS NULL AND purge_requested_at IS NULL) OR (lifecycle_state = 'trashed' AND trashed_at IS NOT NULL AND trashed_by_user_id IS NOT NULL AND purge_after IS NOT NULL AND purge_requested_at IS NULL) OR (lifecycle_state = 'purge_pending' AND trashed_at IS NOT NULL AND trashed_by_user_id IS NOT NULL AND purge_after IS NOT NULL AND purge_requested_at IS NOT NULL)",
            name="ck_photos_lifecycle_fields",
        ),
        sa.CheckConstraint(
            "lifecycle_state IN ('active', 'trashed', 'purge_pending')", name="ck_photos_lifecycle_state"
        ),
        sa.CheckConstraint("sha256 ~ '^[0-9a-f]{64}$'", name="ck_photos_sha256_lower_hex"),
        sa.CheckConstraint("width > 0 AND height > 0", name="ck_photos_dimensions"),
        sa.CheckConstraint("size_bytes > 0", name="ck_photos_size_bytes_positive"),
        sa.PrimaryKeyConstraint("id", name="pk_photos"),
        sa.UniqueConstraint("storage_key", name="uq_photos_storage_key"),
        sa.UniqueConstraint("uploaded_by_user_id", "sha256", name="uq_photos_uploaded_by_user_id_sha256"),
    )
    op.create_index("ix_photos_lifecycle_purge_after", "photos", ["lifecycle_state", "purge_after"], unique=False)
    op.create_index(
        "ix_photos_original_filename_trgm",
        "photos",
        ["original_filename"],
        unique=False,
        postgresql_using="gin",
        postgresql_ops={"original_filename": "gin_trgm_ops"},
    )
    op.create_index(
        "ix_photos_sort_date_id",
        "photos",
        [sa.literal_column("effective_captured_at DESC"), sa.literal_column("id DESC")],
        unique=False,
    )
    op.create_index("ix_photos_uploaded_by_user_id", "photos", ["uploaded_by_user_id"], unique=False)
    op.create_index("ix_photos_trashed_by_user_id", "photos", ["trashed_by_user_id"], unique=False)
    op.create_table(
        "photo_metadata",
        sa.Column("photo_id", sa.UUID(), nullable=False),
        sa.Column("memo", sa.Text(), nullable=True),
        sa.Column("memo_updated_by_user_id", sa.UUID(), nullable=False),
        sa.Column("memo_updated_by_username", sa.String(length=64), nullable=False),
        sa.Column("memo_updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("captured_at_override", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.CheckConstraint("memo IS NULL OR char_length(memo) <= 2000", name="ck_photo_metadata_memo_length"),
        sa.CheckConstraint("version > 0", name="ck_photo_metadata_version_positive"),
        sa.PrimaryKeyConstraint("photo_id", name="pk_photo_metadata"),
    )
    op.create_index(
        "ix_photo_metadata_memo_trgm",
        "photo_metadata",
        ["memo"],
        unique=False,
        postgresql_using="gin",
        postgresql_ops={"memo": "gin_trgm_ops"},
    )
    op.create_index(
        "ix_photo_metadata_memo_updated_by_user_id", "photo_metadata", ["memo_updated_by_user_id"], unique=False
    )
    op.create_table(
        "photo_derivatives",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("photo_id", sa.UUID(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("storage_key", sa.Text(), nullable=False),
        sa.Column("content_type", sa.String(length=64), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.CheckConstraint("kind IN ('thumbnail')", name="ck_photo_derivatives_kind"),
        sa.CheckConstraint("size_bytes > 0", name="ck_photo_derivatives_size_bytes_positive"),
        sa.CheckConstraint("width > 0 AND height > 0", name="ck_photo_derivatives_dimensions"),
        sa.PrimaryKeyConstraint("id", name="pk_photo_derivatives"),
        sa.UniqueConstraint("photo_id", "kind", name="uq_photo_derivatives_photo_id_kind"),
        sa.UniqueConstraint("storage_key", name="uq_photo_derivatives_storage_key"),
    )
    op.create_index("ix_photo_derivatives_photo_id", "photo_derivatives", ["photo_id"], unique=False)
    op.create_table(
        "photo_shares",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("photo_id", sa.UUID(), nullable=False),
        sa.Column("group_id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name="pk_photo_shares"),
        sa.UniqueConstraint("photo_id", "group_id", name="uq_photo_shares_photo_id_group_id"),
    )
    op.create_index("ix_photo_shares_group_id_photo_id", "photo_shares", ["group_id", "photo_id"], unique=False)
    op.create_table(
        "photo_favorites",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("photo_id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.PrimaryKeyConstraint("user_id", "photo_id", name="pk_photo_favorites"),
    )
    op.create_index("ix_photo_favorites_photo_id", "photo_favorites", ["photo_id"], unique=False)
    op.create_table(
        "photo_activity_events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("photo_id", sa.UUID(), nullable=False),
        sa.Column("actor_user_id", sa.UUID(), nullable=False),
        sa.Column("actor_username", sa.String(length=64), nullable=False),
        sa.Column("event_type", sa.String(length=16), nullable=False),
        sa.Column("operation_id", sa.UUID(), nullable=False),
        sa.Column(
            "occurred_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.CheckConstraint("event_type IN ('uploaded', 'shared')", name="ck_photo_activity_events_event_type"),
        sa.PrimaryKeyConstraint("id", name="pk_photo_activity_events"),
    )
    op.create_index(
        "ix_photo_activity_events_occurred_at_id",
        "photo_activity_events",
        [sa.literal_column("occurred_at DESC"), sa.literal_column("id DESC")],
        unique=False,
    )
    op.create_index("ix_photo_activity_events_operation_id", "photo_activity_events", ["operation_id"], unique=False)
    op.create_index("ix_photo_activity_events_photo_id", "photo_activity_events", ["photo_id"], unique=False)
    op.create_table(
        "photo_activity_event_groups",
        sa.Column("event_id", sa.UUID(), nullable=False),
        sa.Column("group_id", sa.UUID(), nullable=False),
        sa.PrimaryKeyConstraint("event_id", "group_id", name="pk_photo_activity_event_groups"),
    )
    op.create_index(
        "ix_photo_activity_event_groups_group_id", "photo_activity_event_groups", ["group_id", "event_id"], unique=False
    )

    # Add foreign keys after all tables exist, including the album/photo cycle.
    op.create_table(
        "photo_activity_states",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("seen_through_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("seen_through_event_id", sa.UUID(), nullable=False),
        sa.PrimaryKeyConstraint("user_id", name="pk_photo_activity_states"),
    )
    op.create_table(
        "upload_batches",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("owner_user_id", sa.UUID(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('active', 'completed', 'canceled')", name="ck_upload_batches_status"),
        sa.CheckConstraint(
            "(status = 'active' AND completed_at IS NULL) OR (status <> 'active' AND completed_at IS NOT NULL)",
            name="ck_upload_batches_completed_at",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_upload_batches"),
    )
    op.create_index(
        "ix_upload_batches_owner_user_id_created_at",
        "upload_batches",
        ["owner_user_id", sa.literal_column("created_at DESC")],
        unique=False,
    )
    op.create_table(
        "upload_batch_group_shares",
        sa.Column("batch_id", sa.UUID(), nullable=False),
        sa.Column("group_id", sa.UUID(), nullable=False),
        sa.PrimaryKeyConstraint("batch_id", "group_id", name="pk_upload_batch_group_shares"),
    )
    op.create_index(
        "ix_upload_batch_group_shares_group_id",
        "upload_batch_group_shares",
        ["group_id"],
        unique=False,
    )
    op.create_table(
        "upload_items",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("batch_id", sa.UUID(), nullable=False),
        sa.Column("client_id", sa.String(length=64), nullable=False),
        sa.Column("original_filename", sa.Text(), nullable=False),
        sa.Column("declared_content_type", sa.String(length=64), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("received_bytes", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("error_code", sa.String(length=32), nullable=True),
        sa.Column("photo_id", sa.UUID(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('queued', 'uploading', 'processing', 'succeeded', 'duplicate', 'failed')",
            name="ck_upload_items_status",
        ),
        sa.CheckConstraint(
            "received_bytes >= 0 AND received_bytes <= size_bytes", name="ck_upload_items_received_bytes"
        ),
        sa.CheckConstraint(
            "(status IN ('queued', 'uploading', 'processing') AND completed_at IS NULL "
            "AND photo_id IS NULL AND error_code IS NULL) OR "
            "(status = 'succeeded' AND completed_at IS NOT NULL AND error_code IS NULL) OR "
            "(status = 'duplicate' AND completed_at IS NOT NULL AND photo_id IS NULL "
            "AND error_code = 'duplicate') OR "
            "(status = 'failed' AND completed_at IS NOT NULL AND photo_id IS NULL "
            "AND error_code IS NOT NULL)",
            name="ck_upload_items_lifecycle_fields",
        ),
        sa.CheckConstraint("size_bytes > 0", name="ck_upload_items_size_bytes_positive"),
        sa.PrimaryKeyConstraint("id", name="pk_upload_items"),
        sa.UniqueConstraint("batch_id", "client_id", name="uq_upload_items_batch_id_client_id"),
    )
    op.create_index("ix_upload_items_batch_id", "upload_items", ["batch_id"], unique=False)
    op.create_index("ix_upload_items_photo_id", "upload_items", ["photo_id"], unique=False)
    op.create_table(
        "album_photos",
        sa.Column("album_id", sa.UUID(), nullable=False),
        sa.Column("photo_id", sa.UUID(), nullable=False),
        sa.Column("added_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("album_id", "photo_id", name="pk_album_photos"),
    )
    op.create_index("ix_album_photos_photo_id", "album_photos", ["photo_id"], unique=False)
    op.create_table(
        "albums",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", sa.UUID(), nullable=False),
        sa.Column("created_by_username", sa.String(length=64), nullable=False),
        sa.Column("group_id", sa.UUID(), nullable=False),
        sa.Column("cover_photo_id", sa.UUID(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.CheckConstraint("char_length(title) BETWEEN 1 AND 120", name="ck_albums_title_length"),
        sa.CheckConstraint(
            "description IS NULL OR char_length(description) <= 2000", name="ck_albums_description_length"
        ),
        sa.CheckConstraint("title = btrim(title)", name="ck_albums_title_trimmed"),
        sa.PrimaryKeyConstraint("id", name="pk_albums"),
    )
    op.create_index("ix_albums_created_by_user_id", "albums", ["created_by_user_id"], unique=False)
    op.create_index("ix_albums_group_id", "albums", ["group_id"], unique=False)
    op.create_index(
        "ix_albums_updated_at_id",
        "albums",
        [sa.literal_column("updated_at DESC"), sa.literal_column("id DESC")],
        unique=False,
    )
    op.create_foreign_key(
        "fk_photo_activity_states_user_id_users",
        "photo_activity_states",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_photos_trashed_by_user_id_users", "photos", "users", ["trashed_by_user_id"], ["id"], ondelete="RESTRICT"
    )
    op.create_foreign_key(
        "fk_photos_uploaded_by_user_id_users", "photos", "users", ["uploaded_by_user_id"], ["id"], ondelete="RESTRICT"
    )
    op.create_foreign_key(
        "fk_upload_batches_owner_user_id_users",
        "upload_batches",
        "users",
        ["owner_user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_photo_activity_events_actor_user_id_users",
        "photo_activity_events",
        "users",
        ["actor_user_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_photo_activity_events_photo_id_photos",
        "photo_activity_events",
        "photos",
        ["photo_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_photo_derivatives_photo_id_photos", "photo_derivatives", "photos", ["photo_id"], ["id"], ondelete="CASCADE"
    )
    op.create_foreign_key(
        "fk_photo_favorites_photo_id_photos", "photo_favorites", "photos", ["photo_id"], ["id"], ondelete="CASCADE"
    )
    op.create_foreign_key(
        "fk_photo_favorites_user_id_users", "photo_favorites", "users", ["user_id"], ["id"], ondelete="CASCADE"
    )
    op.create_foreign_key(
        "fk_photo_metadata_memo_updated_by_user_id_users",
        "photo_metadata",
        "users",
        ["memo_updated_by_user_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_photo_metadata_photo_id_photos", "photo_metadata", "photos", ["photo_id"], ["id"], ondelete="CASCADE"
    )
    op.create_foreign_key(
        "fk_photo_shares_group_id_family_groups",
        "photo_shares",
        "family_groups",
        ["group_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_photo_shares_photo_id_photos", "photo_shares", "photos", ["photo_id"], ["id"], ondelete="CASCADE"
    )
    op.create_foreign_key(
        "fk_upload_batch_group_shares_batch_id_upload_batches",
        "upload_batch_group_shares",
        "upload_batches",
        ["batch_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_upload_batch_group_shares_group_id_family_groups",
        "upload_batch_group_shares",
        "family_groups",
        ["group_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_upload_items_batch_id_upload_batches",
        "upload_items",
        "upload_batches",
        ["batch_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_upload_items_photo_id_photos", "upload_items", "photos", ["photo_id"], ["id"], ondelete="SET NULL"
    )
    op.create_foreign_key(
        "fk_photo_activity_event_groups_event_id_photo_activity_events",
        "photo_activity_event_groups",
        "photo_activity_events",
        ["event_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_photo_activity_event_groups_group_id_family_groups",
        "photo_activity_event_groups",
        "family_groups",
        ["group_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_album_photos_album_id_albums", "album_photos", "albums", ["album_id"], ["id"], ondelete="CASCADE"
    )
    op.create_foreign_key(
        "fk_album_photos_photo_id_photos", "album_photos", "photos", ["photo_id"], ["id"], ondelete="CASCADE"
    )
    op.create_foreign_key(
        "fk_albums_created_by_user_id_users", "albums", "users", ["created_by_user_id"], ["id"], ondelete="RESTRICT"
    )
    op.create_foreign_key(
        "fk_albums_group_id_family_groups", "albums", "family_groups", ["group_id"], ["id"], ondelete="CASCADE"
    )
    op.create_foreign_key(
        "fk_albums_cover_album_photos",
        "albums",
        "album_photos",
        ["id", "cover_photo_id"],
        ["album_id", "photo_id"],
        deferrable=True,
        initially="DEFERRED",
    )


def downgrade() -> None:
    op.drop_constraint("fk_albums_cover_album_photos", "albums", type_="foreignkey")
    op.drop_constraint("fk_albums_group_id_family_groups", "albums", type_="foreignkey")
    op.drop_constraint("fk_albums_created_by_user_id_users", "albums", type_="foreignkey")
    op.drop_constraint("fk_album_photos_photo_id_photos", "album_photos", type_="foreignkey")
    op.drop_constraint("fk_album_photos_album_id_albums", "album_photos", type_="foreignkey")
    op.drop_index("ix_albums_updated_at_id", table_name="albums")
    op.drop_index("ix_albums_group_id", table_name="albums")
    op.drop_index("ix_albums_created_by_user_id", table_name="albums")
    op.drop_table("albums")
    op.drop_index("ix_album_photos_photo_id", table_name="album_photos")
    op.drop_table("album_photos")
    op.drop_constraint(
        "fk_photo_activity_event_groups_group_id_family_groups", "photo_activity_event_groups", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_photo_activity_event_groups_event_id_photo_activity_events",
        "photo_activity_event_groups",
        type_="foreignkey",
    )
    op.drop_constraint("fk_upload_items_photo_id_photos", "upload_items", type_="foreignkey")
    op.drop_constraint("fk_upload_items_batch_id_upload_batches", "upload_items", type_="foreignkey")
    op.drop_constraint(
        "fk_upload_batch_group_shares_group_id_family_groups", "upload_batch_group_shares", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_upload_batch_group_shares_batch_id_upload_batches", "upload_batch_group_shares", type_="foreignkey"
    )
    op.drop_constraint("fk_photo_shares_photo_id_photos", "photo_shares", type_="foreignkey")
    op.drop_constraint("fk_photo_shares_group_id_family_groups", "photo_shares", type_="foreignkey")
    op.drop_constraint("fk_photo_metadata_photo_id_photos", "photo_metadata", type_="foreignkey")
    op.drop_constraint("fk_photo_metadata_memo_updated_by_user_id_users", "photo_metadata", type_="foreignkey")
    op.drop_constraint("fk_photo_favorites_user_id_users", "photo_favorites", type_="foreignkey")
    op.drop_constraint("fk_photo_favorites_photo_id_photos", "photo_favorites", type_="foreignkey")
    op.drop_constraint("fk_photo_derivatives_photo_id_photos", "photo_derivatives", type_="foreignkey")
    op.drop_constraint("fk_photo_activity_events_photo_id_photos", "photo_activity_events", type_="foreignkey")
    op.drop_constraint("fk_photo_activity_events_actor_user_id_users", "photo_activity_events", type_="foreignkey")
    op.drop_constraint("fk_upload_batches_owner_user_id_users", "upload_batches", type_="foreignkey")
    op.drop_constraint("fk_photos_uploaded_by_user_id_users", "photos", type_="foreignkey")
    op.drop_constraint("fk_photos_trashed_by_user_id_users", "photos", type_="foreignkey")
    op.drop_constraint("fk_photo_activity_states_user_id_users", "photo_activity_states", type_="foreignkey")
    op.drop_index("ix_photo_activity_event_groups_group_id", table_name="photo_activity_event_groups")
    op.drop_table("photo_activity_event_groups")
    op.drop_index("ix_upload_items_batch_id", table_name="upload_items")
    op.drop_table("upload_items")
    op.drop_index("ix_upload_batch_group_shares_group_id", table_name="upload_batch_group_shares")
    op.drop_table("upload_batch_group_shares")
    op.drop_index("ix_photo_shares_group_id_photo_id", table_name="photo_shares")
    op.drop_table("photo_shares")
    op.drop_index("ix_photo_metadata_memo_updated_by_user_id", table_name="photo_metadata")
    op.drop_index(
        "ix_photo_metadata_memo_trgm",
        table_name="photo_metadata",
        postgresql_using="gin",
        postgresql_ops={"memo": "gin_trgm_ops"},
    )
    op.drop_table("photo_metadata")
    op.drop_index("ix_photo_favorites_photo_id", table_name="photo_favorites")
    op.drop_table("photo_favorites")
    op.drop_index("ix_photo_derivatives_photo_id", table_name="photo_derivatives")
    op.drop_table("photo_derivatives")
    op.drop_index("ix_photo_activity_events_photo_id", table_name="photo_activity_events")
    op.drop_index("ix_photo_activity_events_operation_id", table_name="photo_activity_events")
    op.drop_index("ix_photo_activity_events_occurred_at_id", table_name="photo_activity_events")
    op.drop_table("photo_activity_events")
    op.drop_index("ix_upload_batches_owner_user_id_created_at", table_name="upload_batches")
    op.drop_table("upload_batches")
    op.drop_index("ix_photos_uploaded_by_user_id", table_name="photos")
    op.drop_index("ix_photos_sort_date_id", table_name="photos")
    op.drop_index(
        "ix_photos_original_filename_trgm",
        table_name="photos",
        postgresql_using="gin",
        postgresql_ops={"original_filename": "gin_trgm_ops"},
    )
    op.drop_index("ix_photos_lifecycle_purge_after", table_name="photos")
    op.drop_table("photos")
    op.drop_table("photo_activity_states")
