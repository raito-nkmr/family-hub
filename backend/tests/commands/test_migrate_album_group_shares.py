from unittest.mock import MagicMock
from uuid import uuid4

from sqlalchemy.dialects import postgresql

from app.commands.migrate_album_group_shares import migrate
from app.features.albums.models import AlbumGroupShare


def test_migrate_album_group_shares_is_idempotent_and_dry_run_rolls_back() -> None:
    session = MagicMock()
    album_id = uuid4()
    group_id = uuid4()
    session.execute.return_value.all.return_value = [(album_id, group_id)]
    session.scalar.side_effect = [None, album_id]

    assert migrate(session, apply=False) == 1
    insert_statement = session.execute.call_args_list[1].args[0]
    assert insert_statement.table.name == AlbumGroupShare.__tablename__
    assert "INSERT INTO album_group_shares" in str(
        insert_statement.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True})
    )
    assert "IS NOT NULL" in str(session.execute.call_args_list[0].args[0])
    session.rollback.assert_called_once_with()
    session.commit.assert_not_called()

    assert migrate(session, apply=True) == 0
    session.commit.assert_called_once_with()
