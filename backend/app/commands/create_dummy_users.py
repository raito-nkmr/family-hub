import argparse
from collections.abc import Sequence
from dataclasses import dataclass
from getpass import getpass
from uuid import uuid4

from sqlalchemy import Connection, select

from app.core.config import Settings, get_management_settings
from app.database.session import create_database_engine
from app.features.auth.models import SystemRole, User
from app.features.auth.passwords import MAXIMUM_PASSWORD_LENGTH, MINIMUM_PASSWORD_LENGTH, hash_password
from app.features.auth.schemas import normalize_username

DEFAULT_USER_COUNT = 5
MAXIMUM_USER_COUNT = 100


@dataclass(frozen=True, slots=True)
class DummyUserSpec:
    username: str
    system_role: SystemRole


@dataclass(frozen=True, slots=True)
class CreationResult:
    created_usernames: tuple[str, ...]
    skipped_usernames: tuple[str, ...]


def positive_user_count(value: str) -> int:
    count = int(value)
    if not 1 <= count <= MAXIMUM_USER_COUNT:
        raise argparse.ArgumentTypeError(f"count must be between 1 and {MAXIMUM_USER_COUNT}")
    return count


def build_dummy_user_specs(count: int, username_prefix: str, admin_username: str) -> tuple[DummyUserSpec, ...]:
    normalized_admin_username = normalize_username(admin_username)
    normalized_username_prefix = normalize_username(username_prefix)
    normalized_usernames = tuple(
        normalize_username(f"{normalized_username_prefix}-{index:02d}") for index in range(1, count + 1)
    )
    if normalized_admin_username in normalized_usernames or len(set(normalized_usernames)) != len(normalized_usernames):
        raise ValueError("dummy usernames must be unique")
    return (
        DummyUserSpec(username=normalized_admin_username, system_role=SystemRole.ADMIN),
        *(DummyUserSpec(username=username, system_role=SystemRole.USER) for username in normalized_usernames),
    )


def create_dummy_users(connection: Connection, specs: Sequence[DummyUserSpec], password: str) -> CreationResult:
    usernames = [spec.username for spec in specs]
    existing_usernames = set(connection.execute(select(User.username).where(User.username.in_(usernames))).scalars())
    created_usernames: list[str] = []

    for spec in specs:
        if spec.username in existing_usernames:
            continue
        connection.execute(
            User.__table__.insert().values(
                id=uuid4(),
                username=spec.username,
                password_hash=hash_password(password),
                is_active=True,
                system_role=spec.system_role,
            )
        )
        created_usernames.append(spec.username)

    return CreationResult(
        created_usernames=tuple(created_usernames),
        skipped_usernames=tuple(username for username in usernames if username in existing_usernames),
    )


def validate_development_environment(settings: Settings) -> None:
    if settings.app_env != "development":
        raise SystemExit("This command is available only when APP_ENV=development")


def read_password() -> str:
    password = getpass("Shared dummy-user password: ")
    confirmation = getpass("Confirm password: ")
    if password != confirmation:
        raise SystemExit("Passwords do not match")
    if not MINIMUM_PASSWORD_LENGTH <= len(password) <= MAXIMUM_PASSWORD_LENGTH:
        raise SystemExit(
            f"Password must contain between {MINIMUM_PASSWORD_LENGTH} and {MAXIMUM_PASSWORD_LENGTH} characters"
        )
    return password


def main() -> None:
    parser = argparse.ArgumentParser(description="Create development-only dummy users")
    parser.add_argument("--count", type=positive_user_count, default=DEFAULT_USER_COUNT)
    parser.add_argument("--username-prefix", default="dummy-user")
    parser.add_argument("--admin-username", default="dummy-admin")
    arguments = parser.parse_args()

    settings = get_management_settings()
    validate_development_environment(settings)
    try:
        specs = build_dummy_user_specs(arguments.count, arguments.username_prefix, arguments.admin_username)
    except ValueError as error:
        parser.error(str(error))
    password = read_password()

    engine = create_database_engine(settings)
    try:
        with engine.begin() as connection:
            result = create_dummy_users(connection, specs, password)
    finally:
        engine.dispose()

    print(f"Created {len(result.created_usernames)} user(s): {', '.join(result.created_usernames) or 'none'}")
    if result.skipped_usernames:
        print(f"Skipped {len(result.skipped_usernames)} existing user(s): {', '.join(result.skipped_usernames)}")


if __name__ == "__main__":
    main()
