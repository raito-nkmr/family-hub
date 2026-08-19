import argparse
from getpass import getpass
from uuid import uuid4

from sqlalchemy import Connection, select

from app.core.config import get_management_settings
from app.database.session import create_database_engine
from app.features.auth.models import SystemRole, User
from app.features.auth.passwords import MAXIMUM_PASSWORD_LENGTH, MINIMUM_PASSWORD_LENGTH, hash_password
from app.features.auth.schemas import normalize_username


def create_user(connection: Connection, username: str, password_hash: str, system_role: SystemRole) -> None:
    if connection.execute(select(User.id).where(User.username == username)).scalar_one_or_none() is not None:
        raise SystemExit(f"User '{username}' already exists")
    if system_role is SystemRole.USER:
        active_admin_exists = connection.execute(
            select(User.id).where(User.system_role == SystemRole.ADMIN, User.is_active.is_(True)).limit(1)
        ).scalar_one_or_none()
        if active_admin_exists is None:
            raise SystemExit("Cannot create a regular user before an active system administrator exists")
    connection.execute(
        User.__table__.insert().values(
            id=uuid4(),
            username=username,
            password_hash=password_hash,
            is_active=True,
            system_role=system_role,
            must_change_password=False,
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a photo storage user")
    parser.add_argument("--username", required=True)
    parser.add_argument("--system-role", choices=[role.value for role in SystemRole], default=SystemRole.USER.value)
    arguments = parser.parse_args()
    username = normalize_username(arguments.username)

    password = getpass("Password: ")
    confirmation = getpass("Confirm password: ")
    if password != confirmation:
        raise SystemExit("Passwords do not match")
    if not MINIMUM_PASSWORD_LENGTH <= len(password) <= MAXIMUM_PASSWORD_LENGTH:
        raise SystemExit(
            f"Password must contain between {MINIMUM_PASSWORD_LENGTH} and {MAXIMUM_PASSWORD_LENGTH} characters"
        )

    engine = create_database_engine(get_management_settings())
    try:
        with engine.begin() as connection:
            create_user(connection, username, hash_password(password), SystemRole(arguments.system_role))
    finally:
        engine.dispose()
    print(f"Created user '{username}'")


if __name__ == "__main__":
    main()
