import argparse
from datetime import UTC, datetime
from getpass import getpass

from sqlalchemy import Connection, select

from app.core.config import get_management_settings
from app.database.session import create_database_engine
from app.features.auth.models import User, UserSession
from app.features.auth.passwords import MAXIMUM_PASSWORD_LENGTH, MINIMUM_PASSWORD_LENGTH, hash_password
from app.features.auth.schemas import normalize_username


class UserNotFoundError(Exception):
    pass


def read_password() -> str:
    password = getpass("Temporary password: ")
    confirmation = getpass("Confirm temporary password: ")
    if password != confirmation:
        raise SystemExit("Passwords do not match")
    if not MINIMUM_PASSWORD_LENGTH <= len(password) <= MAXIMUM_PASSWORD_LENGTH:
        raise SystemExit(
            f"Password must contain between {MINIMUM_PASSWORD_LENGTH} and {MAXIMUM_PASSWORD_LENGTH} characters"
        )
    return password


def reset_user_password(
    connection: Connection,
    username: str,
    password: str,
    *,
    changed_at: datetime | None = None,
) -> int:
    user_id = connection.execute(
        select(User.id).where(User.username == username).with_for_update()
    ).scalar_one_or_none()
    if user_id is None:
        raise UserNotFoundError(username)

    reset_at = changed_at or datetime.now(UTC)
    connection.execute(
        User.__table__.update()
        .where(User.id == user_id)
        .values(
            password_hash=hash_password(password),
            password_changed_at=reset_at,
            must_change_password=True,
        )
    )
    revoked = connection.execute(
        UserSession.__table__.update()
        .where(UserSession.user_id == user_id, UserSession.revoked_at.is_(None))
        .values(revoked_at=reset_at)
    )
    return revoked.rowcount


def main() -> None:
    parser = argparse.ArgumentParser(description="Reset an existing Family Hub user's password")
    parser.add_argument("--username", required=True)
    arguments = parser.parse_args()
    username = normalize_username(arguments.username)
    password = read_password()

    engine = create_database_engine(get_management_settings())
    try:
        with engine.begin() as connection:
            try:
                revoked_count = reset_user_password(connection, username, password)
            except UserNotFoundError as error:
                raise SystemExit(f"User '{username}' does not exist") from error
    finally:
        engine.dispose()

    print(f"Reset password for '{username}' and revoked {revoked_count} active session(s)")
    print("Ask the user to sign in with the temporary password and change it immediately")


if __name__ == "__main__":
    main()
