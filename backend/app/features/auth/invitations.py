import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import and_, func, select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.features.audit.public import record_administrative_event
from app.features.auth.models import SystemRole, User, UserInvitation
from app.features.auth.passwords import hash_password


class InvitationNotFoundError(Exception):
    pass


class InvitationUnavailableError(Exception):
    pass


class InvitationUsernameUnavailableError(Exception):
    pass


class InvitationPersistenceError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class InvitationSummary:
    id: UUID
    username: str
    created_by_username: str
    created_at: datetime
    expires_at: datetime
    status: str


@dataclass(frozen=True, slots=True)
class CreatedInvitation:
    invitation: InvitationSummary
    token: str


def hash_invitation_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class InvitationService:
    def __init__(self, session: Session, settings: Settings) -> None:
        self._session = session
        self._settings = settings

    def list_invitations(
        self,
        query: str | None = None,
        invitation_status: str | None = None,
    ) -> list[InvitationSummary]:
        now = datetime.now(UTC)
        conditions = []
        if query:
            conditions.append(func.lower(UserInvitation.username).contains(query.casefold(), autoescape=True))
        if invitation_status:
            status_condition = {
                "used": UserInvitation.used_at.is_not(None),
                "revoked": and_(
                    UserInvitation.used_at.is_(None),
                    UserInvitation.revoked_at.is_not(None),
                ),
                "expired": and_(
                    UserInvitation.used_at.is_(None),
                    UserInvitation.revoked_at.is_(None),
                    UserInvitation.expires_at <= now,
                ),
                "pending": and_(
                    UserInvitation.used_at.is_(None),
                    UserInvitation.revoked_at.is_(None),
                    UserInvitation.expires_at > now,
                ),
            }.get(invitation_status)
            if status_condition is None:
                return []
            conditions.append(status_condition)
        statement = (
            select(UserInvitation, User.username)
            .join(User, User.id == UserInvitation.created_by_user_id)
            .where(*conditions)
            .order_by(UserInvitation.created_at.desc(), UserInvitation.id.desc())
        )
        return [
            self._summary(invitation, creator_username, now)
            for invitation, creator_username in self._session.execute(statement)
        ]

    def create_invitation(
        self,
        username: str,
        creator_user_id: UUID,
        creator_username: str,
        expires_in_hours: int = 24,
    ) -> CreatedInvitation:
        if self._session.scalar(select(User.id).where(User.username == username)) is not None:
            raise InvitationUsernameUnavailableError

        now = datetime.now(UTC)
        self._session.execute(
            update(UserInvitation)
            .where(
                UserInvitation.username == username,
                UserInvitation.used_at.is_(None),
                UserInvitation.revoked_at.is_(None),
            )
            .values(revoked_at=now)
        )
        token = secrets.token_urlsafe(32)
        invitation = UserInvitation(
            id=uuid4(),
            username=username,
            token_hash=hash_invitation_token(token),
            created_by_user_id=creator_user_id,
            created_at=now,
            expires_at=now + timedelta(hours=expires_in_hours),
            used_at=None,
            revoked_at=None,
        )
        self._session.add(invitation)
        record_administrative_event(
            self._session,
            scope="system",
            action="invitation.created",
            actor_user_id=creator_user_id,
            actor_username=creator_username,
            target_type="user_invitation",
            target_id=str(invitation.id),
            details={"username": username, "expires_in_hours": expires_in_hours},
        )
        try:
            self._session.commit()
        except IntegrityError as error:
            self._session.rollback()
            raise InvitationUsernameUnavailableError from error
        except SQLAlchemyError as error:
            self._session.rollback()
            raise InvitationPersistenceError from error
        return CreatedInvitation(self._summary(invitation, creator_username, now), token)

    def revoke_invitation(
        self,
        invitation_id: UUID,
        actor_user_id: UUID | None = None,
        actor_username: str | None = None,
    ) -> None:
        invitation = self._session.scalar(
            select(UserInvitation).where(UserInvitation.id == invitation_id).with_for_update()
        )
        if invitation is None:
            raise InvitationNotFoundError
        if invitation.used_at is not None:
            raise InvitationUnavailableError
        if invitation.revoked_at is None:
            invitation.revoked_at = datetime.now(UTC)
            if actor_username is not None:
                record_administrative_event(
                    self._session,
                    scope="system",
                    action="invitation.revoked",
                    actor_user_id=actor_user_id,
                    actor_username=actor_username,
                    target_type="user_invitation",
                    target_id=str(invitation.id),
                    details={"username": invitation.username},
                )
            self._commit()

    def remove_invitation_history(
        self,
        invitation_id: UUID,
        actor_user_id: UUID,
        actor_username: str,
    ) -> None:
        invitation = self._session.scalar(
            select(UserInvitation).where(UserInvitation.id == invitation_id).with_for_update()
        )
        if invitation is None:
            raise InvitationNotFoundError
        record_administrative_event(
            self._session,
            scope="system",
            action="invitation.removed",
            actor_user_id=actor_user_id,
            actor_username=actor_username,
            target_type="user_invitation",
            target_id=str(invitation.id),
            details={
                "username": invitation.username,
                "was_pending": (
                    invitation.used_at is None
                    and invitation.revoked_at is None
                    and invitation.expires_at > datetime.now(UTC)
                ),
            },
        )
        self._session.delete(invitation)
        self._commit()

    def accept_invitation(self, token: str, password: str) -> User:
        now = datetime.now(UTC)
        invitation = self._session.scalar(
            select(UserInvitation).where(UserInvitation.token_hash == hash_invitation_token(token)).with_for_update()
        )
        if (
            invitation is None
            or invitation.used_at is not None
            or invitation.revoked_at is not None
            or invitation.expires_at <= now
        ):
            raise InvitationUnavailableError
        if self._session.scalar(select(User.id).where(User.username == invitation.username)) is not None:
            raise InvitationUnavailableError

        user = User(
            id=uuid4(),
            username=invitation.username,
            password_hash=hash_password(password),
            is_active=True,
            system_role=SystemRole.USER,
            created_at=now,
            password_changed_at=now,
            must_change_password=False,
        )
        invitation.used_at = now
        self._session.add(user)
        try:
            self._session.commit()
        except IntegrityError as error:
            self._session.rollback()
            raise InvitationUnavailableError from error
        except SQLAlchemyError as error:
            self._session.rollback()
            raise InvitationPersistenceError from error
        return user

    def _commit(self) -> None:
        try:
            self._session.commit()
        except SQLAlchemyError as error:
            self._session.rollback()
            raise InvitationPersistenceError from error

    @staticmethod
    def _summary(invitation: UserInvitation, creator_username: str, now: datetime) -> InvitationSummary:
        if invitation.used_at is not None:
            status = "used"
        elif invitation.revoked_at is not None:
            status = "revoked"
        elif invitation.expires_at <= now:
            status = "expired"
        else:
            status = "pending"
        return InvitationSummary(
            id=invitation.id,
            username=invitation.username,
            created_by_username=creator_username,
            created_at=invitation.created_at,
            expires_at=invitation.expires_at,
            status=status,
        )
