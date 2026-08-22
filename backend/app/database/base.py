from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


def get_model_metadata() -> MetaData:
    from app.features.albums.models import Album, AlbumPhoto
    from app.features.audit.models import AdministrativeAuditEvent
    from app.features.auth.models import User, UserInvitation, UserSession
    from app.features.chores.models import ChoreCategory, ChoreCompletion, ChoreTask
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
    from app.features.shopping.models import ShoppingCategory, ShoppingItem, ShoppingPurchase, ShoppingTrip

    for model in (
        Album,
        AlbumPhoto,
        AdministrativeAuditEvent,
        ChoreCategory,
        ChoreCompletion,
        ChoreTask,
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
        ShoppingCategory,
        ShoppingItem,
        ShoppingPurchase,
        ShoppingTrip,
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
