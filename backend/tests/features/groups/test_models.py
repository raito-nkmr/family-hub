from sqlalchemy import CheckConstraint, ForeignKeyConstraint, UniqueConstraint

from app.features.groups.models import FamilyGroup, FamilyGroupMember, FamilyGroupMembershipInvitation


def test_family_group_table_has_expected_constraints_and_indexes() -> None:
    constraints = {constraint.name: constraint for constraint in FamilyGroup.__table__.constraints}

    assert set(constraints) == {
        "ck_family_groups_name_length",
        "ck_family_groups_name_trimmed",
        "ck_family_groups_timezone_length",
        "ck_family_groups_timezone_trimmed",
        "fk_family_groups_created_by_user_id_users",
        "pk_family_groups",
        "uq_family_groups_name",
    }
    assert isinstance(constraints["ck_family_groups_name_length"], CheckConstraint)
    assert isinstance(constraints["ck_family_groups_timezone_length"], CheckConstraint)
    assert isinstance(constraints["fk_family_groups_created_by_user_id_users"], ForeignKeyConstraint)
    assert isinstance(constraints["uq_family_groups_name"], UniqueConstraint)
    assert {index.name for index in FamilyGroup.__table__.indexes} == {"ix_family_groups_created_by_user_id"}


def test_family_group_member_table_has_role_and_foreign_key_constraints() -> None:
    constraints = {constraint.name: constraint for constraint in FamilyGroupMember.__table__.constraints}

    assert set(constraints) == {
        "ck_family_group_members_role",
        "fk_family_group_members_group_id_family_groups",
        "fk_family_group_members_user_id_users",
        "pk_family_group_members",
    }
    assert constraints["fk_family_group_members_group_id_family_groups"].elements[0].ondelete == "CASCADE"
    assert constraints["fk_family_group_members_user_id_users"].elements[0].ondelete == "RESTRICT"
    assert {index.name for index in FamilyGroupMember.__table__.indexes} == {"ix_family_group_members_user_id"}


def test_family_group_membership_invitation_table_uses_family_names() -> None:
    constraints = {constraint.name for constraint in FamilyGroupMembershipInvitation.__table__.constraints}
    indexes = {index.name for index in FamilyGroupMembershipInvitation.__table__.indexes}

    assert constraints == {
        "ck_family_group_membership_invitations_responded_at",
        "ck_family_group_membership_invitations_role",
        "ck_family_group_membership_invitations_status",
        "fk_family_group_membership_invitations_group_id_family_groups",
        "fk_family_group_membership_invitations_invitee_user_id_users",
        "fk_family_group_membership_invitations_invited_by_user_id_users",
        "pk_family_group_membership_invitations",
    }
    assert indexes == {
        "ix_family_group_membership_invitations_group_id",
        "ix_family_group_membership_invitations_invitee_status",
        "ix_family_group_membership_invitations_invited_by_user_id",
        "uq_family_group_membership_invitations_pending",
    }
