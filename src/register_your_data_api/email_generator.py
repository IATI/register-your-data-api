"""Email content generation using Jinja2 templates"""

from dataclasses import dataclass
from enum import Enum

from jinja2 import Environment, FileSystemLoader, select_autoescape


@dataclass
class Email:
    """Container for generated email content"""

    from_name: str
    from_email: str
    to_name: str
    to_email: str
    subject: str
    content_text: str
    content_html: str


class EmailType(Enum):
    """Types of emails that can be generated"""

    USER_REQUESTED_TO_JOIN_ORG = "user_requested_to_join_org"
    NEW_ORG_NEEDS_APPROVAL = "new_org_needs_approval"


class EmailGenerator:
    """Generates email content from Jinja2 templates"""

    def __init__(self, templates_dir: str) -> None:
        """
        Initialize the email generator.

        Args:
            templates_dir: Path to the directory containing email templates
        """
        self._templates_dir = templates_dir

    def _get_jinja_env(self) -> Environment:
        """Create and return a Jinja2 environment configured for email templates"""
        return Environment(loader=FileSystemLoader(self._templates_dir), autoescape=select_autoescape(["html"]))

    def generate_email_content(
        self,
        email_type: EmailType,
        from_name: str,
        from_email: str,
        to_name: str,
        to_email: str,
        **template_vars: str,
    ) -> Email:
        """
        Generate email content using Jinja2 templates.

        Args:
            email_type: The type of email to generate
            from_name: The name of the sender
            from_email: The email address of the sender
            to_name: The name of the recipient
            to_email: The email address of the recipient
            **template_vars: Additional template variables specific to the email type

        Returns:
            An Email object containing subject, text content, and HTML content
        """
        template_base_name = email_type.value

        # Combine standard variables with any additional template-specific variables
        context = {
            "from_name": from_name,
            "from_email": from_email,
            "to_name": to_name,
            "to_email": to_email,
            **template_vars,
        }

        # Render subject (no autoescape)
        text_env = self._get_jinja_env()
        subject_template = text_env.get_template(f"{template_base_name}_subject.txt")
        subject = subject_template.render(**context).strip()

        # Render text version (no autoescape)
        text_template = text_env.get_template(f"{template_base_name}.txt")
        text_content = text_template.render(**context)

        # Render HTML version (with autoescape)
        html_env = self._get_jinja_env()
        html_template = html_env.get_template(f"{template_base_name}.html")
        html_content = html_template.render(**context)

        return Email(
            from_name=from_name,
            from_email=from_email,
            to_name=to_name,
            to_email=to_email,
            subject=subject,
            content_text=text_content,
            content_html=html_content,
        )
