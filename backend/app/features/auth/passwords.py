from functools import lru_cache

from pwdlib import PasswordHash

MINIMUM_PASSWORD_LENGTH = 8
MAXIMUM_PASSWORD_LENGTH = 128


@lru_cache
def _get_password_hasher() -> PasswordHash:
    return PasswordHash.recommended()


@lru_cache
def _get_dummy_hash() -> str:
    return _get_password_hasher().hash("this-password-is-only-used-for-timing-protection")


def hash_password(password: str) -> str:
    return _get_password_hasher().hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return _get_password_hasher().verify(password, password_hash)


def verify_dummy_password(password: str) -> None:
    _get_password_hasher().verify(password, _get_dummy_hash())
