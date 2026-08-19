from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, aliased

from app.features.audit.public import AdministrativeAuditEvent, record_administrative_event
from app.features.auth.models import SystemRole, User, UserSession
from app.features.auth.passwords import verify_password
from app.features.groups.public import FamilyGroup, FamilyGroupMember, GroupRole, lock_administrator_mutations


class AdministrativeUserNotFoundError(Exception):
    pass


class AdministrativeReauthenticationError(Exception):
    pass


class LastSystemAdministratorError(Exception):
    pass


class UserOwnsGroupsWithoutAnotherAdminError(Exception):
    def __init__(self, group_names: list[str]) -> None:
        self.group_names = group_names


class AdministrativePersistenceError(Exception):
    pass


class AdministrativeGroupMemberError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class AdministrativeUserSummary:
    id: UUID
    username: str
    is_active: bool
    system_role: SystemRole
    created_at: datetime
    active_session_count: int
    group_names: list[str]
    group_admin_group_names: list[str]


@dataclass(frozen=True, slots=True)
class AdministrativeGroupHealth:
    id: UUID
    name: str
    member_count: int
    active_admin_count: int
    updated_at: datetime


class AdministrativeService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_users(self) -> list[AdministrativeUserSummary]:
        now = datetime.now(UTC)
        users = list(self._session.scalars(select(User).order_by(User.username)).all())
        rows = self._session.execute(
            select(FamilyGroupMember.user_id, FamilyGroup.name, FamilyGroupMember.role)
            .join(FamilyGroup, FamilyGroup.id == FamilyGroupMember.group_id)
            .order_by(FamilyGroup.name)
        ).all()
        groups: dict[UUID, list[str]] = {}
        group_admin_groups: dict[UUID, list[str]] = {}
        for user_id, name, role in rows:
            groups.setdefault(user_id, []).append(name)
            if GroupRole(role) is GroupRole.ADMIN:
                group_admin_groups.setdefault(user_id, []).append(name)
        session_counts = dict(
            self._session.execute(
                select(UserSession.user_id, func.count())
                .where(UserSession.revoked_at.is_(None), UserSession.expires_at > now)
                .group_by(UserSession.user_id)
            ).all()
        )
        return [
            AdministrativeUserSummary(
                id=user.id,
                username=user.username,
                is_active=user.is_active,
                system_role=SystemRole(user.system_role),
                created_at=user.created_at,
                active_session_count=int(session_counts.get(user.id, 0)),
                group_names=groups.get(user.id, []),
                group_admin_group_names=group_admin_groups.get(user.id, []),
            )
            for user in users
        ]

    def list_group_health(self) -> list[AdministrativeGroupHealth]:
        member = aliased(FamilyGroupMember)
        admin_member = aliased(FamilyGroupMember)
        admin_user = aliased(User)
        statement = (
            select(
                FamilyGroup,
                func.count(func.distinct(member.user_id)),
                func.count(func.distinct(admin_user.id)),
            )
            .outerjoin(member, member.group_id == FamilyGroup.id)
            .outerjoin(
                admin_member,
                (admin_member.group_id == FamilyGroup.id) & (admin_member.role == GroupRole.ADMIN),
            )
            .outerjoin(
                admin_user,
                (admin_user.id == admin_member.user_id) & admin_user.is_active.is_(True),
            )
            .group_by(FamilyGroup.id)
            .order_by(FamilyGroup.name)
        )
        return [
            AdministrativeGroupHealth(group.id, group.name, int(member_count), int(admin_count), group.updated_at)
            for group, member_count, admin_count in self._session.execute(statement)
        ]

    def list_audit_events(self, limit: int = 100) -> list[AdministrativeAuditEvent]:
        return list(
            self._session.scalars(
                select(AdministrativeAuditEvent)
                .order_by(AdministrativeAuditEvent.created_at.desc(), AdministrativeAuditEvent.id.desc())
                .limit(limit)
            ).all()
        )

    def update_user_status(
        self,
        target_user_id: UUID,
        is_active: bool,
        administrator_id: UUID,
        administrator_username: str,
        current_password: str,
    ) -> None:
        lock_administrator_mutations(self._session)
        administrator = self._reauthenticate(administrator_id, current_password)
        target = self._lock_user(target_user_id)
        if target.is_active == is_active:
            return
        if not is_active:
            if target.system_role == SystemRole.ADMIN:
                self._require_another_system_admin(target.id)
            orphaned = self._groups_without_another_active_admin(target.id)
            if orphaned:
                raise UserOwnsGroupsWithoutAnotherAdminError(orphaned)
        previous = target.is_active
        target.is_active = is_active
        self._session.execute(
            update(UserSession)
            .where(UserSession.user_id == target.id, UserSession.revoked_at.is_(None))
            .values(revoked_at=datetime.now(UTC))
        )
        record_administrative_event(
            self._session,
            scope="system",
            action="user.activated" if is_active else "user.deactivated",
            actor_user_id=administrator.id,
            actor_username=administrator_username,
            target_type="user",
            target_id=str(target.id),
            details={"username": target.username, "previous_is_active": previous},
        )
        self._commit()

    def update_user_role(
        self,
        target_user_id: UUID,
        role: SystemRole,
        administrator_id: UUID,
        administrator_username: str,
        current_password: str,
    ) -> None:
        lock_administrator_mutations(self._session)
        administrator = self._reauthenticate(administrator_id, current_password)
        target = self._lock_user(target_user_id)
        previous = SystemRole(target.system_role)
        if previous is role:
            return
        if previous is SystemRole.ADMIN and role is SystemRole.USER:
            self._require_another_system_admin(target.id)
        target.system_role = role
        self._session.execute(
            update(UserSession)
            .where(UserSession.user_id == target.id, UserSession.revoked_at.is_(None))
            .values(revoked_at=datetime.now(UTC))
        )
        record_administrative_event(
            self._session,
            scope="system",
            action="user.role_changed",
            actor_user_id=administrator.id,
            actor_username=administrator_username,
            target_type="user",
            target_id=str(target.id),
            details={"username": target.username, "previous_role": previous.value, "role": role.value},
        )
        self._commit()

    def assign_group_administrator(
        self,
        group_id: UUID,
        target_user_id: UUID,
        administrator_id: UUID,
        administrator_username: str,
        current_password: str,
    ) -> None:
        lock_administrator_mutations(self._session)
        administrator = self._reauthenticate(administrator_id, current_password)
        group = self._session.scalar(select(FamilyGroup).where(FamilyGroup.id == group_id).with_for_update())
        membership = self._session.get(FamilyGroupMember, (group_id, target_user_id))
        target = self._session.get(User, target_user_id)
        if group is None or membership is None or target is None or not target.is_active:
            raise AdministrativeGroupMemberError
        previous = GroupRole(membership.role)
        if previous is GroupRole.ADMIN:
            return
        membership.role = GroupRole.ADMIN
        group.updated_at = datetime.now(UTC)
        record_administrative_event(
            self._session,
            scope="system",
            action="group.administrator_assigned",
            actor_user_id=administrator.id,
            actor_username=administrator_username,
            group_id=group.id,
            target_type="user",
            target_id=str(target.id),
            details={"username": target.username, "previous_role": previous.value},
        )
        self._commit()

    def _reauthenticate(self, administrator_id: UUID, password: str) -> User:
        administrator = self._session.get(User, administrator_id)
        if (
            administrator is None
            or not administrator.is_active
            or administrator.system_role != SystemRole.ADMIN
            or not verify_password(password, administrator.password_hash)
        ):
            raise AdministrativeReauthenticationError
        return administrator

    def _lock_user(self, user_id: UUID) -> User:
        user = self._session.scalar(select(User).where(User.id == user_id).with_for_update())
        if user is None:
            raise AdministrativeUserNotFoundError
        return user

    def _require_another_system_admin(self, excluded_user_id: UUID) -> None:
        count = self._session.scalar(
            select(func.count())
            .select_from(User)
            .where(User.system_role == SystemRole.ADMIN, User.is_active.is_(True), User.id != excluded_user_id)
        )
        if not count:
            raise LastSystemAdministratorError

    def _groups_without_another_active_admin(self, user_id: UUID) -> list[str]:
        other_member = aliased(FamilyGroupMember)
        other_user = aliased(User)
        other_active_admin = (
            select(other_member.group_id)
            .join(other_user, other_user.id == other_member.user_id)
            .where(
                other_member.group_id == FamilyGroup.id,
                other_member.user_id != user_id,
                other_member.role == GroupRole.ADMIN,
                other_user.is_active.is_(True),
            )
            .exists()
        )
        return list(
            self._session.scalars(
                select(FamilyGroup.name)
                .join(FamilyGroupMember, FamilyGroupMember.group_id == FamilyGroup.id)
                .where(
                    FamilyGroupMember.user_id == user_id,
                    FamilyGroupMember.role == GroupRole.ADMIN,
                    ~other_active_admin,
                )
                .order_by(FamilyGroup.name)
            ).all()
        )

    def _commit(self) -> None:
        try:
            self._session.commit()
        except SQLAlchemyError as error:
            self._session.rollback()
            raise AdministrativePersistenceError from error
