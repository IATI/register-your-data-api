class RYDException(Exception):
    """Base class for all app errors."""

    pass


class RYDUserException(RYDException):
    """Base class for all app errors that occur after the user has been authenticated."""

    def __init__(
        self,
        user_id: str | None,
        client_id: str | None,
        status_code: int,
        app_msg: str | None,
        audit_msg: str | None,
        public_msg: str | None,
    ):
        self.user_id: str | None = user_id
        self.client_id: str | None = client_id
        self.status_code: int = status_code
        self.app_msg: str | None = app_msg
        self.audit_msg: str | None = audit_msg
        self.public_msg: str | None = public_msg
