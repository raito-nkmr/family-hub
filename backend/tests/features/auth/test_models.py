from sqlalchemy.dialects import postgresql

from app.features.auth.models import User, UserInvitation, UserSession


def test_authentication_models_use_expected_tables_and_constraints() -> None:
    assert User.__tablename__ == "users"
    assert UserSession.__tablename__ == "user_sessions"
    assert {constraint.name for constraint in User.__table__.constraints} >= {
        "pk_users",
        "uq_users_username",
        "ck_users_username_lowercase",
        "ck_users_system_role",
    }
    assert {constraint.name for constraint in UserInvitation.__table__.constraints} >= {
        "pk_user_invitations",
        "uq_user_invitations_token_hash",
        "ck_user_invitations_username_lowercase",
        "ck_user_invitations_token_hash_lower_hex",
        "fk_user_invitations_created_by_user_id_users",
    }
    assert {constraint.name for constraint in UserSession.__table__.constraints} >= {
        "pk_user_sessions",
        "uq_user_sessions_token_hash",
        "ck_user_sessions_token_hash_lower_hex",
        "ck_user_sessions_csrf_token",
        "fk_user_sessions_user_id_users",
    }


def test_authentication_models_compile_for_postgresql() -> None:
    assert str(User.__table__.select().compile(dialect=postgresql.dialect()))
    assert str(UserSession.__table__.select().compile(dialect=postgresql.dialect()))
    assert str(UserInvitation.__table__.select().compile(dialect=postgresql.dialect()))
