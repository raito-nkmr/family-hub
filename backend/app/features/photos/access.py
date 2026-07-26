from uuid import UUID

from sqlalchemy import and_, exists, or_, select

from app.features.groups.public import FamilyGroupMember
from app.features.photos.models import Photo, PhotoLifecycleState, PhotoShare


def photo_is_shared():
    return exists(
        select(PhotoShare.id).where(
            PhotoShare.photo_id == Photo.id,
        )
    )


def photo_is_shared_with_group_member(viewer_user_id: UUID):
    return exists(
        select(PhotoShare.id)
        .join(FamilyGroupMember, FamilyGroupMember.group_id == PhotoShare.group_id)
        .where(
            PhotoShare.photo_id == Photo.id,
            PhotoShare.group_id == FamilyGroupMember.group_id,
            FamilyGroupMember.user_id == viewer_user_id,
        )
    )


def photo_is_in_library(viewer_user_id: UUID):
    return and_(
        Photo.lifecycle_state == PhotoLifecycleState.ACTIVE,
        or_(
            Photo.uploaded_by_user_id == viewer_user_id,
            photo_is_shared_with_group_member(viewer_user_id),
        ),
    )
