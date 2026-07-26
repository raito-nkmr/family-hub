from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, aliased

from app.features.albums.public import Album
from app.features.audit.public import AdministrativeAuditEvent, record_administrative_event
from app.features.auth.public import PublicUser, UserDirectory
from app.features.cleaning.public import CleaningTask
from app.features.groups.models import (
    FamilyGroup,
    FamilyGroupMember,
    FamilyGroupMembershipInvitation,
    GroupRole,
)
from app.features.photos.public import PhotoShare
from app.features.shopping.public import ShoppingItem


class GroupNotFoundError(Exception):
    def __init__(self, group_id: UUID) -> None:
        super().__init__(f"Group {group_id} was not found")
        self.group_id = group_id


class GroupPersistenceError(Exception):
    pass


class GroupNameAlreadyExistsError(Exception):
    pass


class GroupForbiddenError(Exception):
    pass


class GroupMemberNotFoundError(Exception):
    pass


class GroupMemberAlreadyExistsError(Exception):
    pass


class GroupUserNotFoundError(Exception):
    pass


class LastGroupAdminError(Exception):
    pass


class GroupMembershipInvitationError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class GroupSummary:
    id: UUID
    name: str
    created_by_user_id: UUID
    created_at: datetime
    updated_at: datetime
    current_user_role: GroupRole
    member_count: int


@dataclass(frozen=True, slots=True)
class GroupMemberSummary:
    user_id: UUID
    username: str
    is_active: bool
    role: GroupRole
    joined_at: datetime


@dataclass(frozen=True, slots=True)
class GroupDetail:
    group: GroupSummary
    members: list[GroupMemberSummary]


class GroupService:
    def __init__(self, session: Session, user_directory: UserDirectory) -> None:
        self._session = session
        self._user_directory = user_directory

    def list_groups(self, user_id: UUID) -> list[GroupSummary]:
        member = aliased(FamilyGroupMember)
        all_members = aliased(FamilyGroupMember)
        statement = (
            select(FamilyGroup, member.role, func.count(all_members.user_id))
            .join(member, member.group_id == FamilyGroup.id)
            .outerjoin(all_members, all_members.group_id == FamilyGroup.id)
            .where(member.user_id == user_id)
            .group_by(FamilyGroup.id, member.role)
            .order_by(FamilyGroup.updated_at.desc(), FamilyGroup.id.desc())
        )
        return [
            self._summary(group, role, member_count) for group, role, member_count in self._session.execute(statement)
        ]

    def get_group(self, group_id: UUID, user_id: UUID) -> GroupDetail:
        statement = (
            select(FamilyGroup, FamilyGroupMember.role)
            .join(FamilyGroupMember, FamilyGroupMember.group_id == FamilyGroup.id)
            .where(FamilyGroup.id == group_id, FamilyGroupMember.user_id == user_id)
        )
        row = self._session.execute(statement).one_or_none()
        if row is None:
            raise GroupNotFoundError(group_id)
        group, current_user_role = row
        memberships = list(
            self._session.scalars(
                select(FamilyGroupMember)
                .where(FamilyGroupMember.group_id == group_id)
                .order_by(FamilyGroupMember.joined_at.asc(), FamilyGroupMember.user_id.asc())
            ).all()
        )
        users = self._user_directory.list_by_ids({membership.user_id for membership in memberships})
        members = [
            GroupMemberSummary(
                user_id=membership.user_id,
                username=users[membership.user_id].username,
                is_active=users[membership.user_id].is_active,
                role=GroupRole(membership.role),
                joined_at=membership.joined_at,
            )
            for membership in memberships
            if membership.user_id in users
        ]
        return GroupDetail(
            group=self._summary(group, current_user_role, len(members)),
            members=members,
        )

    def create_group(
        self,
        name: str,
        creator_user_id: UUID,
        creator_username: str = "unknown",
    ) -> GroupDetail:
        if self._session.scalar(select(FamilyGroup.id).where(FamilyGroup.name == name)) is not None:
            raise GroupNameAlreadyExistsError

        group_id = uuid4()
        now = datetime.now(UTC)
        group = FamilyGroup(
            id=group_id,
            name=name,
            created_by_user_id=creator_user_id,
            created_at=now,
            updated_at=now,
        )
        membership = FamilyGroupMember(
            group_id=group_id,
            user_id=creator_user_id,
            role=GroupRole.ADMIN,
            joined_at=now,
        )
        self._session.add_all([group, membership])
        if creator_username != "unknown":
            record_administrative_event(
                self._session,
                scope="group",
                action="group.created",
                actor_user_id=creator_user_id,
                actor_username=creator_username,
                group_id=group.id,
                target_type="group",
                target_id=str(group.id),
                details={"name": name},
            )
        try:
            self._session.commit()
        except IntegrityError as error:
            self._session.rollback()
            if self._constraint_name(error) == "uq_family_groups_name":
                raise GroupNameAlreadyExistsError from error
            raise GroupPersistenceError("Could not create group") from error
        except SQLAlchemyError as error:
            self._session.rollback()
            raise GroupPersistenceError("Could not create group") from error
        creator = self._user_directory.list_by_ids({creator_user_id})[creator_user_id]
        summary = self._summary(group, GroupRole.ADMIN, 1)
        return GroupDetail(
            group=summary,
            members=[
                GroupMemberSummary(
                    user_id=creator.id,
                    username=creator.username,
                    is_active=creator.is_active,
                    role=GroupRole.ADMIN,
                    joined_at=membership.joined_at,
                )
            ],
        )

    def rename_group(
        self,
        group_id: UUID,
        actor_user_id: UUID,
        actor_username: str,
        name: str,
    ) -> GroupDetail:
        group = self._get_group_for_admin(group_id, actor_user_id)
        previous_name = group.name
        group.name = name
        group.updated_at = datetime.now(UTC)
        record_administrative_event(
            self._session,
            scope="group",
            action="group.renamed",
            actor_user_id=actor_user_id,
            actor_username=actor_username,
            group_id=group.id,
            target_type="group",
            target_id=str(group.id),
            details={"previous_name": previous_name, "name": name},
        )
        try:
            self._session.commit()
        except IntegrityError as error:
            self._session.rollback()
            if self._constraint_name(error) == "uq_family_groups_name":
                raise GroupNameAlreadyExistsError from error
            raise GroupPersistenceError("Could not rename group") from error
        return self.get_group(group_id, actor_user_id)

    def administration_overview(self, group_id: UUID, actor_user_id: UUID) -> dict[str, int]:
        self._get_group_for_admin(group_id, actor_user_id, lock=False)
        users = self._user_directory.list_by_ids(
            set(
                self._session.scalars(
                    select(FamilyGroupMember.user_id).where(
                        FamilyGroupMember.group_id == group_id,
                        FamilyGroupMember.role == GroupRole.ADMIN,
                    )
                ).all()
            )
        )
        return {
            "album_count": self._count(Album, Album.group_id == group_id),
            "shared_photo_count": self._count(PhotoShare, PhotoShare.group_id == group_id),
            "cleaning_task_count": self._count(CleaningTask, CleaningTask.group_id == group_id),
            "shopping_item_count": self._count(ShoppingItem, ShoppingItem.group_id == group_id),
            "active_admin_count": sum(user.is_active for user in users.values()),
        }

    def member_removal_impact(
        self,
        group_id: UUID,
        target_user_id: UUID,
        actor_user_id: UUID,
    ) -> dict[str, object]:
        self._get_group_for_admin(group_id, actor_user_id, lock=False)
        membership = self._session.get(FamilyGroupMember, (group_id, target_user_id))
        user = self._user_directory.list_by_ids({target_user_id}).get(target_user_id)
        if membership is None or user is None:
            raise GroupMemberNotFoundError
        return {
            "user_id": target_user_id,
            "username": user.username,
            "shared_photo_count": int(
                self._session.scalar(
                    select(func.count())
                    .select_from(PhotoShare)
                    .join(PhotoShare.photo)
                    .where(PhotoShare.group_id == group_id, PhotoShare.photo.has(uploaded_by_user_id=target_user_id))
                )
                or 0
            ),
            "created_album_count": self._count(
                Album,
                Album.group_id == group_id,
                Album.created_by_user_id == target_user_id,
            ),
            "created_cleaning_task_count": self._count(
                CleaningTask,
                CleaningTask.group_id == group_id,
                CleaningTask.created_by_user_id == target_user_id,
            ),
            "created_shopping_item_count": self._count(
                ShoppingItem,
                ShoppingItem.group_id == group_id,
                ShoppingItem.created_by_user_id == target_user_id,
            ),
        }

    def invite_member(
        self,
        group_id: UUID,
        actor_user_id: UUID,
        actor_username: str,
        user_id: UUID,
        role: GroupRole,
    ) -> tuple[FamilyGroupMembershipInvitation, PublicUser]:
        self._get_group_for_admin(group_id, actor_user_id)
        user = self._user_directory.list_by_ids({user_id}).get(user_id)
        if user is None or not user.is_active:
            raise GroupUserNotFoundError
        if self._session.get(FamilyGroupMember, (group_id, user_id)) is not None:
            raise GroupMemberAlreadyExistsError
        invitation = FamilyGroupMembershipInvitation(
            id=uuid4(),
            group_id=group_id,
            user_id=user_id,
            requested_by_user_id=actor_user_id,
            role=role,
            status="pending",
            created_at=datetime.now(UTC),
            responded_at=None,
        )
        self._session.add(invitation)
        record_administrative_event(
            self._session,
            scope="group",
            action="membership.invited",
            actor_user_id=actor_user_id,
            actor_username=actor_username,
            group_id=group_id,
            target_type="user",
            target_id=str(user_id),
            details={"username": user.username, "role": role.value},
        )
        try:
            self._session.commit()
        except IntegrityError as error:
            self._session.rollback()
            raise GroupMembershipInvitationError from error
        return invitation, user

    def list_my_membership_invitations(self, user_id: UUID) -> list[tuple[FamilyGroupMembershipInvitation, str]]:
        return list(
            self._session.execute(
                select(FamilyGroupMembershipInvitation, FamilyGroup.name)
                .join(FamilyGroup, FamilyGroup.id == FamilyGroupMembershipInvitation.group_id)
                .where(
                    FamilyGroupMembershipInvitation.user_id == user_id,
                    FamilyGroupMembershipInvitation.status == "pending",
                )
                .order_by(FamilyGroupMembershipInvitation.created_at.desc())
            )
        )

    def decide_membership_invitation(
        self,
        invitation_id: UUID,
        user_id: UUID,
        username: str,
        accept: bool,
    ) -> None:
        invitation = self._session.scalar(
            select(FamilyGroupMembershipInvitation)
            .where(
                FamilyGroupMembershipInvitation.id == invitation_id,
                FamilyGroupMembershipInvitation.user_id == user_id,
                FamilyGroupMembershipInvitation.status == "pending",
            )
            .with_for_update()
        )
        if invitation is None:
            raise GroupMembershipInvitationError
        invitation.status = "accepted" if accept else "rejected"
        invitation.responded_at = datetime.now(UTC)
        if accept:
            self._session.add(
                FamilyGroupMember(
                    group_id=invitation.group_id,
                    user_id=user_id,
                    role=invitation.role,
                    joined_at=invitation.responded_at,
                )
            )
        record_administrative_event(
            self._session,
            scope="group",
            action="membership.accepted" if accept else "membership.rejected",
            actor_user_id=user_id,
            actor_username=username,
            group_id=invitation.group_id,
            target_type="membership_invitation",
            target_id=str(invitation.id),
        )
        self._commit("Could not respond to group invitation")

    def list_group_audit_events(self, group_id: UUID, actor_user_id: UUID) -> list[AdministrativeAuditEvent]:
        self._get_group_for_admin(group_id, actor_user_id, lock=False)
        return list(
            self._session.scalars(
                select(AdministrativeAuditEvent)
                .where(AdministrativeAuditEvent.group_id == group_id)
                .order_by(AdministrativeAuditEvent.created_at.desc(), AdministrativeAuditEvent.id.desc())
                .limit(100)
            ).all()
        )

    def list_member_candidates(self, group_id: UUID, actor_user_id: UUID) -> list[PublicUser]:
        self._get_group_for_admin(group_id, actor_user_id, lock=False)
        member_ids = set(
            self._session.scalars(select(FamilyGroupMember.user_id).where(FamilyGroupMember.group_id == group_id)).all()
        )
        return [user for user in self._user_directory.list_active() if user.id not in member_ids]

    def add_member(
        self,
        group_id: UUID,
        actor_user_id: UUID,
        user_id: UUID,
        role: GroupRole,
        actor_username: str = "unknown",
    ) -> GroupDetail:
        group = self._get_group_for_admin(group_id, actor_user_id)
        users = self._user_directory.list_by_ids({user_id})
        user = users.get(user_id)
        if user is None or not user.is_active:
            raise GroupUserNotFoundError
        if self._session.get(FamilyGroupMember, (group_id, user.id)) is not None:
            raise GroupMemberAlreadyExistsError

        now = datetime.now(UTC)
        self._session.add(
            FamilyGroupMember(
                group_id=group_id,
                user_id=user.id,
                role=role,
                joined_at=now,
            )
        )
        pending_invitation = self._session.scalar(
            select(FamilyGroupMembershipInvitation).where(
                FamilyGroupMembershipInvitation.group_id == group_id,
                FamilyGroupMembershipInvitation.user_id == user.id,
                FamilyGroupMembershipInvitation.status == "pending",
            )
        )
        if pending_invitation is not None:
            pending_invitation.status = "canceled"
            pending_invitation.responded_at = now
        group.updated_at = now
        if actor_username != "unknown":
            record_administrative_event(
                self._session,
                scope="group",
                action="membership.added",
                actor_user_id=actor_user_id,
                actor_username=actor_username,
                group_id=group_id,
                target_type="user",
                target_id=str(user.id),
                details={"username": user.username, "role": role.value},
            )
        self._commit("Could not add group member")
        return self.get_group(group_id, actor_user_id)

    def update_member_role(
        self,
        group_id: UUID,
        target_user_id: UUID,
        actor_user_id: UUID,
        role: GroupRole,
        actor_username: str = "unknown",
    ) -> GroupDetail:
        group = self._get_group_for_admin(group_id, actor_user_id)
        membership = self._session.get(FamilyGroupMember, (group_id, target_user_id))
        if membership is None:
            raise GroupMemberNotFoundError
        if GroupRole(membership.role) is GroupRole.ADMIN and role is GroupRole.MEMBER:
            self._require_another_active_admin(group_id, target_user_id)

        membership.role = role
        group.updated_at = datetime.now(UTC)
        if actor_username != "unknown":
            record_administrative_event(
                self._session,
                scope="group",
                action="membership.role_changed",
                actor_user_id=actor_user_id,
                actor_username=actor_username,
                group_id=group_id,
                target_type="user",
                target_id=str(target_user_id),
                details={"role": role.value},
            )
        self._commit("Could not update group member role")
        return self.get_group(group_id, actor_user_id)

    def remove_member(
        self,
        group_id: UUID,
        target_user_id: UUID,
        actor_user_id: UUID,
        actor_username: str = "unknown",
    ) -> None:
        group = self._get_group_for_admin(group_id, actor_user_id)
        membership = self._session.get(FamilyGroupMember, (group_id, target_user_id))
        if membership is None:
            raise GroupMemberNotFoundError
        if GroupRole(membership.role) is GroupRole.ADMIN:
            self._require_another_active_admin(group_id, target_user_id)

        self._session.delete(membership)
        group.updated_at = datetime.now(UTC)
        if actor_username != "unknown":
            record_administrative_event(
                self._session,
                scope="group",
                action="membership.removed",
                actor_user_id=actor_user_id,
                actor_username=actor_username,
                group_id=group_id,
                target_type="user",
                target_id=str(target_user_id),
            )
        self._commit("Could not remove group member")

    def _get_group_for_admin(self, group_id: UUID, actor_user_id: UUID, *, lock: bool = True) -> FamilyGroup:
        statement = select(FamilyGroup).where(FamilyGroup.id == group_id)
        if lock:
            statement = statement.with_for_update()
        group = self._session.scalar(statement)
        if group is None:
            raise GroupNotFoundError(group_id)
        membership = self._session.get(FamilyGroupMember, (group_id, actor_user_id))
        if membership is None:
            raise GroupNotFoundError(group_id)
        if GroupRole(membership.role) is not GroupRole.ADMIN:
            raise GroupForbiddenError
        return group

    def _require_another_active_admin(self, group_id: UUID, excluded_user_id: UUID) -> None:
        admin_memberships = list(
            self._session.scalars(
                select(FamilyGroupMember)
                .where(
                    FamilyGroupMember.group_id == group_id,
                    FamilyGroupMember.role == GroupRole.ADMIN,
                )
                .with_for_update()
            ).all()
        )
        users = self._user_directory.list_by_ids({membership.user_id for membership in admin_memberships})
        has_another_active_admin = any(
            membership.user_id != excluded_user_id
            and (user := users.get(membership.user_id)) is not None
            and user.is_active
            for membership in admin_memberships
        )
        if not has_another_active_admin:
            raise LastGroupAdminError

    def _commit(self, message: str) -> None:
        try:
            self._session.commit()
        except SQLAlchemyError as error:
            self._session.rollback()
            raise GroupPersistenceError(message) from error

    @staticmethod
    def _summary(group: FamilyGroup, role: str, member_count: int) -> GroupSummary:
        return GroupSummary(
            id=group.id,
            name=group.name,
            created_by_user_id=group.created_by_user_id,
            created_at=group.created_at,
            updated_at=group.updated_at,
            current_user_role=GroupRole(role),
            member_count=member_count,
        )

    @staticmethod
    def _constraint_name(error: IntegrityError) -> str | None:
        diagnostic = getattr(error.orig, "diag", None)
        return getattr(diagnostic, "constraint_name", None)

    def _count(self, model: type[object], *criteria: object) -> int:
        return int(self._session.scalar(select(func.count()).select_from(model).where(*criteria)) or 0)
