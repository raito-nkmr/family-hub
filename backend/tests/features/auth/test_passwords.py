from app.features.auth.passwords import hash_password, verify_password


def test_passwords_are_hashed_with_argon2id() -> None:
    password_hash = hash_password("a sufficiently long test password")

    assert password_hash.startswith("$argon2id$")
    assert verify_password("a sufficiently long test password", password_hash) is True
    assert verify_password("the wrong password", password_hash) is False
