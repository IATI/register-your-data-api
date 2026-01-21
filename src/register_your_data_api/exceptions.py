from .auth.models import UserAndCredentials


class RYDException(Exception):
    """Base class for all app errors."""

    pass


class RYDUserException(RYDException):
    """Base class for all app errors that occur after the user has been authenticated."""

    def __init__(
        self,
        user: UserAndCredentials,
        status_code: int,
        app_msg: str | None,
        audit_msg: str | None,
        public_msg: str | None,
    ):
        self.user: UserAndCredentials = user
        self.status_code: int = status_code
        self.app_msg: str | None = app_msg
        self.audit_msg: str | None = audit_msg
        self.public_msg: str | None = public_msg
