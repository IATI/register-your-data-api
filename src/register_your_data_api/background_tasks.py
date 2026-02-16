import functools
import hashlib
import inspect
import logging
from enum import Enum, auto
from typing import Any, Awaitable, Callable, ParamSpec, TypeVar, cast

from email_validator import EmailNotValidError, validate_email
from fastapi import BackgroundTasks

from register_your_data_api.email_generator import Email
from register_your_data_api.email_sender import EmailSender

P = ParamSpec("P")
R = TypeVar("R")


class ActionType(Enum):
    SEND_EMAIL = auto()


app_logger: logging.Logger = logging.getLogger("ryd-api")
audit_logger: logging.Logger = logging.getLogger("ryd-api-audit")


def background_task_handler(func: Callable[P, R] | Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
    """Decorator that wraps background tasks with error handling and logging."""

    @functools.wraps(func)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:  # type: ignore
        try:
            app_logger.info(f"Starting task: {func.__name__}")
            result = func(*args, **kwargs)
            if inspect.isawaitable(result):
                return await cast(Awaitable[R], result)
            return result
        except Exception as e:
            app_logger.error(f"Failed task {func.__name__}: {e}", exc_info=True)

    return wrapper


def enqueue_task(background_tasks: BackgroundTasks, action: ActionType, *args: Any, **kwargs: Any) -> None:
    """Add a task to the background task processor"""

    if action == ActionType.SEND_EMAIL:
        background_tasks.add_task(send_email_async, *args, **kwargs)
    else:
        raise ValueError(f"Error: request to add an unknown action type to the background task queue: {action}")


@background_task_handler  # type: ignore
async def send_email_async(email_sender: EmailSender, trace_id: str, email: Email) -> None:
    """Sends an email to the Azure Communication Services for sending asynchronously"""

    try:
        validate_email(email.to_email, check_deliverability=False)
    except EmailNotValidError:
        app_logger.info(
            f"send_email_async() - Email address is invalid - trace id: {trace_id} - subject: {email.subject}"
        )
        audit_logger.info(
            f"send_email_async() - Email address is invalid - trace id: {trace_id} - "
            f"recipient: {email.to_email} - subject: {email.subject}"
        )
        return

    recipient_email_hashed = hashlib.sha256(email.to_email.encode()).hexdigest()

    app_logger.debug(
        f"send_email_async() - Sending email to Azure comms service - trace id: {trace_id} - "
        f"recipient: {recipient_email_hashed}"
    )

    audit_logger.info(
        f"send_email_async() - Sending email to Azure comms service - trace id: {trace_id} - "
        f"recipient: {email.to_email} - subject: {email.subject}"
    )
    audit_logger.debug(
        f"send_email_async() - Sending email to Azure comms service - trace id: {trace_id} - "
        f"recipient: {email.to_email} - subject: {email.subject}"
        f"recipient name: {email.to_name}"
    )

    email_sender.send(email)
