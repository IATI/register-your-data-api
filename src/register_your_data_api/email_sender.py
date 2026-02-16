"""Email sending abstractions and Azure implementation."""

from abc import ABC, abstractmethod

from azure.communication.email import EmailClient

from register_your_data_api.email_generator import Email


class EmailSender(ABC):
    """Abstract email sender for an Email object."""

    @abstractmethod
    def send(self, email: Email) -> None:
        """Send the email."""
        raise NotImplementedError


class AzureEmailSender(EmailSender):
    """Send emails using Azure Communication Services EmailClient."""

    def __init__(self, connection_string: str) -> None:
        self._client = EmailClient.from_connection_string(connection_string)

    def send(self, email: Email) -> None:
        message = {
            "senderAddress": email.from_email,
            "replyTo": [{"address": email.from_email, "displayName": email.from_name}],
            "recipients": {"to": [{"address": email.to_email, "displayName": email.to_name}]},
            "content": {
                "subject": email.subject,
                "plainText": email.content_text,
                "html": email.content_html,
            },
        }
        self._client.begin_send(message)
