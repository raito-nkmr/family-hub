import argparse
from getpass import getpass
from uuid import uuid4

from sqlalchemy import select

from app.core.config import get_management_settings
from app.database.session import create_database_engine
from app.features.auth.models import SystemRole, User
from app.features.auth.passwords import MAXIMUM_PASSWORD_LENGTH, MINIMUM_PASSWORD_LENGTH, hash_password
from app.features.auth.schemas import normalize_username


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
            if connection.execute(select(User.id).where(User.username == username)).scalar_one_or_none() is not None:
                raise SystemExit(f"User '{username}' already exists")
            connection.execute(
                User.__table__.insert().values(
                    id=uuid4(),
                    username=username,
                    password_hash=hash_password(password),
                    is_active=True,
                    system_role=arguments.system_role,
                    must_change_password=False,
                )
            )
    finally:
        engine.dispose()
    print(f"Created user '{username}'")


if __name__ == "__main__":
    main()
