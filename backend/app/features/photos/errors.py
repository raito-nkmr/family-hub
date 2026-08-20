from uuid import UUID


class PhotoNotFoundError(Exception):
    def __init__(self, photo_id: UUID) -> None:
        super().__init__(f"Photo {photo_id} was not found")
        self.photo_id = photo_id


class PhotoUpdateForbiddenError(Exception):
    pass


class PhotoUpdateConflictError(Exception):
    pass


class PhotoUpdatePersistenceError(Exception):
    pass


class PhotoUpdateStorageError(Exception):
    pass


class PhotoContentUnavailableError(Exception):
    def __init__(self, photo_id: UUID) -> None:
        super().__init__(f"Content for photo {photo_id} is unavailable")
        self.photo_id = photo_id


class InvalidPhotoSharingError(Exception):
    pass


class PhotoBulkSelectionError(Exception):
    pass


class PhotoExportSelectionError(Exception):
    pass


class PhotoDeleteStorageError(Exception):
    pass


class PhotoDeletePersistenceError(Exception):
    pass


class PhotoPurgeNotDueError(Exception):
    pass


class InvalidTrashCursorError(ValueError):
    pass
