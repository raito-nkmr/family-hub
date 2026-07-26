from app.database.base import Base, get_model_metadata
from app.features.albums.models import Album, AlbumPhoto
from app.features.auth.models import User, UserInvitation, UserSession
from app.features.cleaning.models import CleaningCompletion, CleaningTask
from app.features.groups.models import FamilyGroup, FamilyGroupMember
from app.features.photos.models import Photo, PhotoDerivative, UploadBatch, UploadItem


def test_get_model_metadata_registers_application_models() -> None:
    metadata = get_model_metadata()

    assert metadata is Base.metadata
    assert metadata.tables["albums"] is Album.__table__
    assert metadata.tables["album_photos"] is AlbumPhoto.__table__
    assert metadata.tables["cleaning_tasks"] is CleaningTask.__table__
    assert metadata.tables["cleaning_completions"] is CleaningCompletion.__table__
    assert metadata.tables["family_groups"] is FamilyGroup.__table__
    assert metadata.tables["family_group_members"] is FamilyGroupMember.__table__
    assert metadata.tables["photos"] is Photo.__table__
    assert metadata.tables["photo_derivatives"] is PhotoDerivative.__table__
    assert metadata.tables["upload_batches"] is UploadBatch.__table__
    assert metadata.tables["upload_items"] is UploadItem.__table__
    assert metadata.tables["users"] is User.__table__
    assert metadata.tables["user_sessions"] is UserSession.__table__
    assert metadata.tables["user_invitations"] is UserInvitation.__table__
