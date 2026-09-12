from sqlalchemy import CheckConstraint, ForeignKeyConstraint

from app.features.albums.models import Album, AlbumGroupShare, AlbumPhoto


def test_album_table_has_expected_constraints_and_indexes() -> None:
    constraints = {constraint.name: constraint for constraint in Album.__table__.constraints}
    indexes = {index.name for index in Album.__table__.indexes}

    assert set(constraints) == {
        "ck_albums_description_length",
        "ck_albums_title_length",
        "ck_albums_title_trimmed",
        "fk_albums_created_by_user_id_users",
        "fk_albums_cover_album_photos",
        "pk_albums",
    }
    assert isinstance(constraints["ck_albums_title_length"], CheckConstraint)
    assert isinstance(constraints["fk_albums_created_by_user_id_users"], ForeignKeyConstraint)
    assert indexes == {"ix_albums_created_by_user_id", "ix_albums_updated_at_id"}


def test_album_group_share_table_has_cascading_foreign_keys() -> None:
    constraints = {constraint.name: constraint for constraint in AlbumGroupShare.__table__.constraints}

    assert set(constraints) == {
        "fk_album_group_shares_album_id_albums",
        "fk_album_group_shares_group_id_family_groups",
        "pk_album_group_shares",
    }
    assert constraints["fk_album_group_shares_album_id_albums"].elements[0].ondelete == "CASCADE"
    assert constraints["fk_album_group_shares_group_id_family_groups"].elements[0].ondelete == "CASCADE"
    assert {index.name for index in AlbumGroupShare.__table__.indexes} == {"ix_album_group_shares_group_id_album_id"}


def test_album_photo_table_has_cascading_foreign_keys() -> None:
    constraints = {constraint.name: constraint for constraint in AlbumPhoto.__table__.constraints}

    assert set(constraints) == {
        "fk_album_photos_album_id_albums",
        "fk_album_photos_photo_id_photos",
        "pk_album_photos",
    }
    assert constraints["fk_album_photos_album_id_albums"].elements[0].ondelete == "CASCADE"
    assert constraints["fk_album_photos_photo_id_photos"].elements[0].ondelete == "CASCADE"
    assert {index.name for index in AlbumPhoto.__table__.indexes} == {"ix_album_photos_photo_id"}
