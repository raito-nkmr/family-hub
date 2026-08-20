from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    PrimaryKeyConstraint,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class PhotoVisibility(StrEnum):
    PRIVATE = "private"
    SHARED = "shared"


class PhotoLifecycleState(StrEnum):
    ACTIVE = "active"
    TRASHED = "trashed"
    PURGE_PENDING = "purge_pending"


class PhotoDerivativeKind(StrEnum):
    THUMBNAIL = "thumbnail"


class PhotoActivityEventType(StrEnum):
    UPLOADED = "uploaded"
    SHARED = "shared"


class UploadBatchStatus(StrEnum):
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELED = "canceled"


class UploadItemStatus(StrEnum):
    QUEUED = "queued"
    UPLOADING = "uploading"
    PROCESSING = "processing"
    SUCCEEDED = "succeeded"
    DUPLICATE = "duplicate"
    FAILED = "failed"


class Photo(Base):
    __tablename__ = "photos"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_photos"),
        UniqueConstraint("storage_key", name="uq_photos_storage_key"),
        UniqueConstraint(
            "uploaded_by_user_id",
            "sha256",
            name="uq_photos_uploaded_by_user_id_sha256",
        ),
        CheckConstraint("size_bytes > 0", name="ck_photos_size_bytes_positive"),
        CheckConstraint("sha256 ~ '^[0-9a-f]{64}$'", name="ck_photos_sha256_lower_hex"),
        CheckConstraint("width > 0 AND height > 0", name="ck_photos_dimensions"),
        CheckConstraint(
            "lifecycle_state IN ('active', 'trashed', 'purge_pending')",
            name="ck_photos_lifecycle_state",
        ),
        CheckConstraint(
            "(lifecycle_state = 'active' AND trashed_at IS NULL AND trashed_by_user_id IS NULL "
            "AND purge_after IS NULL AND purge_requested_at IS NULL) OR "
            "(lifecycle_state = 'trashed' AND trashed_at IS NOT NULL AND trashed_by_user_id IS NOT NULL "
            "AND purge_after IS NOT NULL AND purge_requested_at IS NULL) OR "
            "(lifecycle_state = 'purge_pending' AND trashed_at IS NOT NULL AND trashed_by_user_id IS NOT NULL "
            "AND purge_after IS NOT NULL AND purge_requested_at IS NOT NULL)",
            name="ck_photos_lifecycle_fields",
        ),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    uploaded_by_user_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT", name="fk_photos_uploaded_by_user_id_users"),
    )
    uploaded_by_username: Mapped[str] = mapped_column(String(64))
    original_filename: Mapped[str] = mapped_column(Text)
    storage_key: Mapped[str] = mapped_column(Text)
    content_type: Mapped[str] = mapped_column(Text)
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    sha256: Mapped[str] = mapped_column(String(64))
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    captured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.current_timestamp())
    lifecycle_state: Mapped[str] = mapped_column(
        String(16), default=PhotoLifecycleState.ACTIVE, server_default=PhotoLifecycleState.ACTIVE.value
    )
    trashed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    trashed_by_user_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT", name="fk_photos_trashed_by_user_id_users"),
    )
    purge_after: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    purge_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    metadata_record: Mapped["PhotoMetadata"] = relationship(
        back_populates="photo",
        cascade="all, delete-orphan",
        lazy="selectin",
        uselist=False,
    )
    shares: Mapped[list["PhotoShare"]] = relationship(
        back_populates="photo",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    derivatives: Mapped[list["PhotoDerivative"]] = relationship(
        back_populates="photo",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    @property
    def memo(self) -> str | None:
        return self.metadata_record.memo

    @property
    def metadata_version(self) -> int:
        return self.metadata_record.version

    @property
    def memo_updated_by_user_id(self) -> UUID:
        return self.metadata_record.memo_updated_by_user_id

    @property
    def memo_updated_by_username(self) -> str:
        return self.metadata_record.memo_updated_by_username

    @property
    def memo_updated_at(self) -> datetime:
        return self.metadata_record.memo_updated_at

    @property
    def is_favorite(self) -> bool:
        """Default for contexts that do not have a viewer-specific favorite lookup."""
        return False

    @property
    def visibility(self) -> PhotoVisibility:
        if self.shares:
            return PhotoVisibility.SHARED
        return PhotoVisibility.PRIVATE

    @property
    def sharing(self) -> dict[str, object]:
        return {
            "type": self.visibility,
            "group_ids": sorted((share.group_id for share in self.shares), key=str),
        }

    def get_derivative(self, kind: PhotoDerivativeKind) -> "PhotoDerivative | None":
        return next((derivative for derivative in self.derivatives if derivative.kind == kind), None)


Index(
    "ix_photos_sort_date_id",
    func.coalesce(Photo.captured_at, Photo.uploaded_at).desc(),
    Photo.id.desc(),
)
Index("ix_photos_uploaded_by_user_id", Photo.uploaded_by_user_id)
Index("ix_photos_trashed_by_user_id", Photo.trashed_by_user_id)
Index("ix_photos_lifecycle_purge_after", Photo.lifecycle_state, Photo.purge_after)
Index(
    "ix_photos_original_filename_trgm",
    Photo.original_filename,
    postgresql_using="gin",
    postgresql_ops={"original_filename": "gin_trgm_ops"},
)


class PhotoDerivative(Base):
    __tablename__ = "photo_derivatives"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_photo_derivatives"),
        UniqueConstraint("storage_key", name="uq_photo_derivatives_storage_key"),
        UniqueConstraint("photo_id", "kind", name="uq_photo_derivatives_photo_id_kind"),
        CheckConstraint("kind IN ('thumbnail')", name="ck_photo_derivatives_kind"),
        CheckConstraint("width > 0 AND height > 0", name="ck_photo_derivatives_dimensions"),
        CheckConstraint("size_bytes > 0", name="ck_photo_derivatives_size_bytes_positive"),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    photo_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("photos.id", ondelete="CASCADE", name="fk_photo_derivatives_photo_id_photos"),
    )
    kind: Mapped[str] = mapped_column(String(16))
    storage_key: Mapped[str] = mapped_column(Text)
    content_type: Mapped[str] = mapped_column(String(64))
    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.current_timestamp())
    photo: Mapped[Photo] = relationship(back_populates="derivatives")


Index("ix_photo_derivatives_photo_id", PhotoDerivative.photo_id)


class PhotoMetadata(Base):
    __tablename__ = "photo_metadata"
    __table_args__ = (
        PrimaryKeyConstraint("photo_id", name="pk_photo_metadata"),
        CheckConstraint("memo IS NULL OR char_length(memo) <= 2000", name="ck_photo_metadata_memo_length"),
        CheckConstraint("version > 0", name="ck_photo_metadata_version_positive"),
    )

    photo_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("photos.id", ondelete="CASCADE", name="fk_photo_metadata_photo_id_photos"),
        primary_key=True,
    )
    memo: Mapped[str | None] = mapped_column(Text)
    memo_updated_by_user_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT", name="fk_photo_metadata_memo_updated_by_user_id_users"),
    )
    memo_updated_by_username: Mapped[str] = mapped_column(String(64))
    memo_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    captured_at_override: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.current_timestamp())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.current_timestamp())
    photo: Mapped[Photo] = relationship(back_populates="metadata_record")


class PhotoShare(Base):
    __tablename__ = "photo_shares"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_photo_shares"),
        UniqueConstraint("photo_id", "group_id", name="uq_photo_shares_photo_id_group_id"),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    photo_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("photos.id", ondelete="CASCADE", name="fk_photo_shares_photo_id_photos"),
    )
    group_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("family_groups.id", ondelete="CASCADE", name="fk_photo_shares_group_id_family_groups"),
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.current_timestamp())
    photo: Mapped[Photo] = relationship(back_populates="shares")


Index(
    "ix_photo_metadata_memo_trgm",
    PhotoMetadata.memo,
    postgresql_using="gin",
    postgresql_ops={"memo": "gin_trgm_ops"},
)
Index("ix_photo_metadata_memo_updated_by_user_id", PhotoMetadata.memo_updated_by_user_id)


Index("ix_photo_shares_group_id_photo_id", PhotoShare.group_id, PhotoShare.photo_id)


class PhotoFavorite(Base):
    __tablename__ = "photo_favorites"
    __table_args__ = (PrimaryKeyConstraint("user_id", "photo_id", name="pk_photo_favorites"),)

    user_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE", name="fk_photo_favorites_user_id_users"),
        primary_key=True,
    )
    photo_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("photos.id", ondelete="CASCADE", name="fk_photo_favorites_photo_id_photos"),
        primary_key=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.current_timestamp())


Index("ix_photo_favorites_photo_id", PhotoFavorite.photo_id)


class PhotoActivityEvent(Base):
    __tablename__ = "photo_activity_events"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_photo_activity_events"),
        CheckConstraint("event_type IN ('uploaded', 'shared')", name="ck_photo_activity_events_event_type"),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    photo_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("photos.id", ondelete="CASCADE", name="fk_photo_activity_events_photo_id_photos"),
    )
    actor_user_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT", name="fk_photo_activity_events_actor_user_id_users"),
    )
    actor_username: Mapped[str] = mapped_column(String(64))
    event_type: Mapped[str] = mapped_column(String(16))
    operation_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.current_timestamp())
    groups: Mapped[list["PhotoActivityEventGroup"]] = relationship(cascade="all, delete-orphan", lazy="selectin")


class PhotoActivityEventGroup(Base):
    __tablename__ = "photo_activity_event_groups"
    __table_args__ = (PrimaryKeyConstraint("event_id", "group_id", name="pk_photo_activity_event_groups"),)

    event_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "photo_activity_events.id",
            ondelete="CASCADE",
            name="fk_photo_activity_event_groups_event_id_photo_activity_events",
        ),
        primary_key=True,
    )
    group_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "family_groups.id",
            ondelete="CASCADE",
            name="fk_photo_activity_event_groups_group_id_family_groups",
        ),
        primary_key=True,
    )


class PhotoActivityState(Base):
    __tablename__ = "photo_activity_states"
    __table_args__ = (PrimaryKeyConstraint("user_id", name="pk_photo_activity_states"),)

    user_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE", name="fk_photo_activity_states_user_id_users"),
        primary_key=True,
    )
    seen_through_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    seen_through_event_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True))


Index(
    "ix_photo_activity_events_occurred_at_id",
    PhotoActivityEvent.occurred_at.desc(),
    PhotoActivityEvent.id.desc(),
)
Index("ix_photo_activity_events_photo_id", PhotoActivityEvent.photo_id)
Index("ix_photo_activity_events_operation_id", PhotoActivityEvent.operation_id)
Index("ix_photo_activity_event_groups_group_id", PhotoActivityEventGroup.group_id, PhotoActivityEventGroup.event_id)


class UploadBatch(Base):
    __tablename__ = "upload_batches"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_upload_batches"),
        CheckConstraint("status IN ('active', 'completed', 'canceled')", name="ck_upload_batches_status"),
        CheckConstraint(
            "(status = 'active' AND completed_at IS NULL) OR (status <> 'active' AND completed_at IS NOT NULL)",
            name="ck_upload_batches_completed_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE", name="fk_upload_batches_owner_user_id_users"),
    )
    status: Mapped[str] = mapped_column(String(16), default=UploadBatchStatus.ACTIVE)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.current_timestamp())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    group_shares: Mapped[list["UploadBatchGroupShare"]] = relationship(
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    @property
    def group_ids(self) -> list[UUID]:
        return sorted((share.group_id for share in self.group_shares), key=str)

    @property
    def visibility(self) -> PhotoVisibility:
        return PhotoVisibility.SHARED if self.group_shares else PhotoVisibility.PRIVATE


class UploadBatchGroupShare(Base):
    __tablename__ = "upload_batch_group_shares"
    __table_args__ = (PrimaryKeyConstraint("batch_id", "group_id", name="pk_upload_batch_group_shares"),)

    batch_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "upload_batches.id",
            ondelete="CASCADE",
            name="fk_upload_batch_group_shares_batch_id_upload_batches",
        ),
        primary_key=True,
    )
    group_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("family_groups.id", ondelete="CASCADE", name="fk_upload_batch_group_shares_group_id_family_groups"),
        primary_key=True,
    )


class UploadItem(Base):
    __tablename__ = "upload_items"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_upload_items"),
        UniqueConstraint("batch_id", "client_id", name="uq_upload_items_batch_id_client_id"),
        CheckConstraint(
            "status IN ('queued', 'uploading', 'processing', 'succeeded', 'duplicate', 'failed')",
            name="ck_upload_items_status",
        ),
        CheckConstraint("size_bytes > 0", name="ck_upload_items_size_bytes_positive"),
        CheckConstraint("received_bytes >= 0 AND received_bytes <= size_bytes", name="ck_upload_items_received_bytes"),
        CheckConstraint(
            "(status IN ('queued', 'uploading', 'processing') AND completed_at IS NULL "
            "AND photo_id IS NULL AND error_code IS NULL) OR "
            "(status = 'succeeded' AND completed_at IS NOT NULL AND error_code IS NULL) OR "
            "(status = 'duplicate' AND completed_at IS NOT NULL AND photo_id IS NULL "
            "AND error_code = 'duplicate') OR "
            "(status = 'failed' AND completed_at IS NOT NULL AND photo_id IS NULL "
            "AND error_code IS NOT NULL)",
            name="ck_upload_items_lifecycle_fields",
        ),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    batch_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("upload_batches.id", ondelete="CASCADE", name="fk_upload_items_batch_id_upload_batches"),
    )
    client_id: Mapped[str] = mapped_column(String(64))
    original_filename: Mapped[str] = mapped_column(Text)
    declared_content_type: Mapped[str] = mapped_column(String(64))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    received_bytes: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
    status: Mapped[str] = mapped_column(String(16), default=UploadItemStatus.QUEUED)
    error_code: Mapped[str | None] = mapped_column(String(32))
    photo_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("photos.id", ondelete="SET NULL", name="fk_upload_items_photo_id_photos"),
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.current_timestamp())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


Index("ix_upload_batches_owner_user_id_created_at", UploadBatch.owner_user_id, UploadBatch.created_at.desc())
Index("ix_upload_batch_group_shares_group_id", UploadBatchGroupShare.group_id)
Index("ix_upload_items_batch_id", UploadItem.batch_id)
Index("ix_upload_items_photo_id", UploadItem.photo_id)
