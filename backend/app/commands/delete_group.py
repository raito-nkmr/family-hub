import argparse
import sys
from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import get_management_settings
from app.database.session import create_database_engine
from app.features.albums.models import Album, AlbumPhoto
from app.features.audit.public import record_administrative_event
from app.features.chores.models import ChoreCompletion, ChoreTask
from app.features.groups.models import FamilyGroup, FamilyGroupMember, FamilyGroupMembershipInvitation
from app.features.photos.models import (
    Photo,
    PhotoActivityEventGroup,
    PhotoShare,
    UploadBatchGroupShare,
)
from app.features.photos.registration import build_sidecar_metadata
from app.features.photos.storage import PhotoStorage, PhotoStorageError
from app.features.shopping.models import ShoppingItem


class GroupDeletionNotFoundError(Exception):
    pass


class GroupDeletionHasRelatedDataError(Exception):
    pass


class GroupDeletionChangedError(Exception):
    pass


class GroupDeletionConfirmationError(Exception):
    pass


class GroupDeletionPersistenceError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class GroupDeletionImpact:
    group_id: UUID
    name: str
    member_count: int
    album_count: int
    album_photo_count: int
    chore_task_count: int
    chore_completion_count: int
    shopping_item_count: int
    photo_share_count: int
    photo_activity_group_count: int
    upload_batch_group_share_count: int
    membership_invitation_count: int

    @property
    def has_related_data(self) -> bool:
        return any(
            (
                self.album_count,
                self.album_photo_count,
                self.chore_task_count,
                self.chore_completion_count,
                self.shopping_item_count,
                self.photo_share_count,
                self.photo_activity_group_count,
                self.upload_batch_group_share_count,
                self.membership_invitation_count,
            )
        )


def get_group_deletion_impact(session: Session, group_id: UUID, *, lock: bool = False) -> GroupDeletionImpact:
    statement = select(
        FamilyGroup.name,
        _count(FamilyGroupMember, FamilyGroupMember.group_id == group_id).label("member_count"),
        _count(Album, Album.group_id == group_id).label("album_count"),
        _count(AlbumPhoto, AlbumPhoto.album_id == Album.id, Album.group_id == group_id).label("album_photo_count"),
        _count(ChoreTask, ChoreTask.group_id == group_id).label("chore_task_count"),
        _count(
            ChoreCompletion,
            ChoreCompletion.task_id == ChoreTask.id,
            ChoreTask.group_id == group_id,
        ).label("chore_completion_count"),
        _count(ShoppingItem, ShoppingItem.group_id == group_id).label("shopping_item_count"),
        _count(PhotoShare, PhotoShare.group_id == group_id).label("photo_share_count"),
        _count(PhotoActivityEventGroup, PhotoActivityEventGroup.group_id == group_id).label(
            "photo_activity_group_count"
        ),
        _count(UploadBatchGroupShare, UploadBatchGroupShare.group_id == group_id).label(
            "upload_batch_group_share_count"
        ),
        _count(
            FamilyGroupMembershipInvitation,
            FamilyGroupMembershipInvitation.group_id == group_id,
        ).label("membership_invitation_count"),
    ).where(FamilyGroup.id == group_id)
    if lock:
        statement = statement.with_for_update(of=FamilyGroup)

    row = session.execute(statement).one_or_none()
    if row is None:
        raise GroupDeletionNotFoundError(group_id)
    return GroupDeletionImpact(group_id, *row)


def delete_group(
    session: Session,
    expected_impact: GroupDeletionImpact,
    *,
    include_related_data: bool,
) -> tuple[UUID, ...]:
    try:
        actual_impact = get_group_deletion_impact(session, expected_impact.group_id, lock=True)
        if actual_impact != expected_impact:
            raise GroupDeletionChangedError
        if actual_impact.has_related_data and not include_related_data:
            raise GroupDeletionHasRelatedDataError

        affected_photo_ids = tuple(
            session.scalars(
                select(PhotoShare.photo_id)
                .where(PhotoShare.group_id == expected_impact.group_id)
                .order_by(PhotoShare.photo_id)
            ).all()
        )
        record_administrative_event(
            session,
            scope="system",
            action="group.deleted",
            actor_user_id=None,
            actor_username="system-command",
            group_id=expected_impact.group_id,
            target_type="group",
            target_id=str(expected_impact.group_id),
            details={
                "name": expected_impact.name,
                "include_related_data": include_related_data,
                "member_count": expected_impact.member_count,
                "photo_share_count": expected_impact.photo_share_count,
            },
        )
        session.execute(delete(FamilyGroup).where(FamilyGroup.id == expected_impact.group_id))
        session.commit()
        return affected_photo_ids
    except (
        GroupDeletionNotFoundError,
        GroupDeletionChangedError,
        GroupDeletionHasRelatedDataError,
    ):
        session.rollback()
        raise
    except SQLAlchemyError as error:
        session.rollback()
        raise GroupDeletionPersistenceError from error


def confirm_group_deletion(
    impact: GroupDeletionImpact,
    *,
    read_confirmation: Callable[[str], str] = input,
) -> None:
    response = read_confirmation(f'Type the group name "{impact.name}" to confirm permanent deletion: ')
    if response != impact.name:
        raise GroupDeletionConfirmationError


def sync_affected_photo_sidecars(
    session: Session,
    storage: PhotoStorage,
    photo_ids: tuple[UUID, ...],
) -> int:
    if not photo_ids:
        return 0
    photos = session.scalars(select(Photo).where(Photo.id.in_(photo_ids)).order_by(Photo.id)).all()
    for photo in photos:
        storage.update_sidecar(build_sidecar_metadata(photo))
    return len(photos)


def print_deletion_impact(impact: GroupDeletionImpact) -> None:
    print(f"Group: {impact.name} ({impact.group_id})")
    print("The following records will be permanently deleted:")
    print(f"  Members: {impact.member_count}")
    print(f"  Albums: {impact.album_count}")
    print(f"  Album photo associations: {impact.album_photo_count}")
    print(f"  Chore tasks: {impact.chore_task_count}")
    print(f"  Chore completions: {impact.chore_completion_count}")
    print(f"  Shopping items: {impact.shopping_item_count}")
    print(f"  Photo shares: {impact.photo_share_count}")
    print(f"  Photo activity group associations: {impact.photo_activity_group_count}")
    print(f"  Upload batch group shares: {impact.upload_batch_group_share_count}")
    print(f"  Pending and historical membership invitations: {impact.membership_invitation_count}")
    print("Photo records and original photo files will not be deleted.")


def _count(model: type[object], *criteria: object):
    return select(func.count()).select_from(model).where(*criteria).scalar_subquery()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Permanently delete a family group")
    parser.add_argument("--group-id", type=UUID, required=True)
    parser.add_argument(
        "--include-related-data",
        action="store_true",
        help="Allow deletion when the group contains albums, tasks, shopping items, or sharing records",
    )
    return parser.parse_args()


def main() -> None:
    arguments = _parse_args()
    settings = get_management_settings()
    engine = create_database_engine(settings)
    try:
        with Session(engine, expire_on_commit=False) as session:
            try:
                impact = get_group_deletion_impact(session, arguments.group_id)
            except GroupDeletionNotFoundError as error:
                raise SystemExit(f"Group '{arguments.group_id}' does not exist") from error

            print_deletion_impact(impact)
            if impact.has_related_data and not arguments.include_related_data:
                raise SystemExit(
                    "The group contains related data. Review the counts and rerun with "
                    "--include-related-data to allow its deletion."
                )
            try:
                confirm_group_deletion(impact)
            except GroupDeletionConfirmationError as error:
                raise SystemExit("Confirmation did not match the group name; nothing was deleted") from error

            try:
                affected_photo_ids = delete_group(
                    session,
                    impact,
                    include_related_data=arguments.include_related_data,
                )
            except GroupDeletionChangedError as error:
                raise SystemExit(
                    "The group changed after the preview; rerun the command and review it again"
                ) from error
            except GroupDeletionNotFoundError as error:
                raise SystemExit("The group was deleted by another operation; nothing was changed") from error
            except GroupDeletionPersistenceError as error:
                raise SystemExit("Could not delete the group; the database transaction was rolled back") from error

            try:
                synced_count = sync_affected_photo_sidecars(session, PhotoStorage(settings), affected_photo_ids)
            except PhotoStorageError as error:
                print(
                    "The group was deleted, but one or more photo sidecars could not be synchronized. "
                    "Run `python -m app.commands.sync_photo_sidecars` after fixing storage access.",
                    file=sys.stderr,
                )
                raise SystemExit(1) from error
    finally:
        engine.dispose()

    print(f"Permanently deleted group '{impact.name}' ({impact.group_id})")
    print(f"Synchronized {synced_count} affected photo sidecar(s)")


if __name__ == "__main__":
    main()
