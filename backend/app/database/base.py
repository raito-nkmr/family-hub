from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


def get_model_metadata() -> MetaData:
    from app.features.albums.models import Album, AlbumPhoto
    from app.features.audit.models import AdministrativeAuditEvent
    from app.features.auth.models import User, UserInvitation, UserSession
    from app.features.cleaning.models import CleaningCompletion, CleaningTask
    from app.features.groups.models import FamilyGroup, FamilyGroupMember, FamilyGroupMembershipInvitation
    from app.features.maintenance.models import MaintenanceRun
    from app.features.notifications.models import (
        NotificationDelivery,
        NotificationOutbox,
        NotificationPreference,
        PushSubscription,
    )
    from app.features.photos.models import (
        Photo,
        PhotoActivityEvent,
        PhotoActivityEventGroup,
        PhotoActivityState,
        PhotoDerivative,
        PhotoFavorite,
        PhotoMetadata,
        PhotoShare,
        UploadBatch,
        UploadBatchGroupShare,
        UploadItem,
    )
    from app.features.shopping.models import ShoppingItem

    for model in (
        Album,
        AlbumPhoto,
        AdministrativeAuditEvent,
        CleaningCompletion,
        CleaningTask,
        FamilyGroup,
        FamilyGroupMember,
        FamilyGroupMembershipInvitation,
        MaintenanceRun,
        NotificationDelivery,
        NotificationOutbox,
        NotificationPreference,
        Photo,
        PhotoActivityEvent,
        PhotoActivityEventGroup,
        PhotoActivityState,
        PhotoDerivative,
        PhotoFavorite,
        PhotoMetadata,
        PhotoShare,
        PushSubscription,
        ShoppingItem,
        UploadBatch,
        UploadBatchGroupShare,
        UploadItem,
        User,
        UserInvitation,
        UserSession,
    ):
        if model.metadata is not Base.metadata:
            raise RuntimeError(f"{model.__name__} model is registered with unexpected metadata")
    return Base.metadata
