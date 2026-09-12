from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    PrimaryKeyConstraint,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class Album(Base):
    __tablename__ = "albums"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_albums"),
        CheckConstraint("title = btrim(title)", name="ck_albums_title_trimmed"),
        CheckConstraint("char_length(title) BETWEEN 1 AND 120", name="ck_albums_title_length"),
        CheckConstraint(
            "description IS NULL OR char_length(description) <= 2000",
            name="ck_albums_description_length",
        ),
        ForeignKeyConstraint(
            ["id", "cover_photo_id"],
            ["album_photos.album_id", "album_photos.photo_id"],
            name="fk_albums_cover_album_photos",
            deferrable=True,
            initially="DEFERRED",
        ),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    title: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text)
    created_by_user_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT", name="fk_albums_created_by_user_id_users"),
    )
    created_by_username: Mapped[str] = mapped_column(String(64))
    cover_photo_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.current_timestamp())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.current_timestamp())


class AlbumPhoto(Base):
    __tablename__ = "album_photos"
    __table_args__ = (PrimaryKeyConstraint("album_id", "photo_id", name="pk_album_photos"),)

    album_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("albums.id", ondelete="CASCADE", name="fk_album_photos_album_id_albums"),
        primary_key=True,
    )
    photo_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("photos.id", ondelete="CASCADE", name="fk_album_photos_photo_id_photos"),
        primary_key=True,
    )
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.current_timestamp())


class AlbumGroupShare(Base):
    __tablename__ = "album_group_shares"
    __table_args__ = (PrimaryKeyConstraint("album_id", "group_id", name="pk_album_group_shares"),)

    album_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("albums.id", ondelete="CASCADE", name="fk_album_group_shares_album_id_albums"),
        primary_key=True,
    )
    group_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("family_groups.id", ondelete="CASCADE", name="fk_album_group_shares_group_id_family_groups"),
        primary_key=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.current_timestamp())


Index("ix_albums_created_by_user_id", Album.created_by_user_id)
Index("ix_albums_updated_at_id", Album.updated_at.desc(), Album.id.desc())
Index("ix_album_photos_photo_id", AlbumPhoto.photo_id)
Index("ix_album_group_shares_group_id_album_id", AlbumGroupShare.group_id, AlbumGroupShare.album_id)
