import argparse
from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.config import get_management_settings
from app.database.session import create_database_engine
from app.features.audit.public import record_administrative_event
from app.features.auth.models import SystemRole, User, UserSession
from app.features.auth.schemas import normalize_username
from app.features.groups.public import lock_administrator_mutations


def set_user_role(session: Session, username: str, role: SystemRole) -> None:
    lock_administrator_mutations(session)
    user = session.scalar(select(User).where(User.username == username).with_for_update())
    if user is None:
        raise SystemExit(f"User '{username}' does not exist")
    previous = SystemRole(user.system_role)
    if previous is role:
        return
    if previous is SystemRole.ADMIN and role is SystemRole.USER:
        other_admin_count = session.scalar(
            select(func.count())
            .select_from(User)
            .where(User.system_role == SystemRole.ADMIN, User.is_active.is_(True), User.id != user.id)
        )
        if not other_admin_count:
            raise SystemExit("Cannot demote the last active system administrator")
    user.system_role = role
    session.execute(
        update(UserSession)
        .where(UserSession.user_id == user.id, UserSession.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
    )
    record_administrative_event(
        session,
        scope="system",
        action="user.role_changed",
        actor_user_id=None,
        actor_username="system-command",
        target_type="user",
        target_id=str(user.id),
        details={"username": user.username, "previous_role": previous.value, "role": role.value},
    )
    session.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description="Change a photo storage user's system role")
    parser.add_argument("--username", required=True)
    parser.add_argument("--system-role", required=True, choices=[role.value for role in SystemRole])
    arguments = parser.parse_args()
    username = normalize_username(arguments.username)

    engine = create_database_engine(get_management_settings())
    try:
        with Session(engine) as session:
            set_user_role(session, username, SystemRole(arguments.system_role))
    finally:
        engine.dispose()
    print(f"Changed '{username}' to system role '{arguments.system_role}'")


if __name__ == "__main__":
    main()
