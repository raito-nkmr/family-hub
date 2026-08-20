from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.features.auth.dependencies import AuthenticatedUser
from app.features.photos.service import PhotoPurgeNotDueError
from app.features.photos.trash_router import permanently_delete_photo


def test_permanent_delete_maps_not_due_to_conflict() -> None:
    service = MagicMock()
    service.permanently_delete_photo.side_effect = PhotoPurgeNotDueError

    with pytest.raises(HTTPException) as error:
        permanently_delete_photo(
            uuid4(),
            AuthenticatedUser(id=uuid4(), username="owner"),
            service,
        )

    assert error.value.status_code == 409
    assert error.value.detail == "Photo retention period has not elapsed"
