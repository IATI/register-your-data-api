import re
from pathlib import Path

from register_your_data_api.email_generator import Email, EmailGenerator, EmailType


def _template_variables(template_path: Path) -> list[str]:
    template_text = template_path.read_text(encoding="utf-8")
    return re.findall(r"{{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*}}", template_text)


def _assert_template_variables_replaced(content: str, template_path: Path, values: dict[str, str]) -> None:
    for variable in _template_variables(template_path):
        assert variable in values
        assert values[variable] in content


def test_generate_email_content_user_requested_to_join_org() -> None:
    templates_dir = Path(__file__).resolve().parents[2] / "email_templates"
    generator = EmailGenerator(str(templates_dir))

    template_values = {
        "from_name": "IATI Registry",
        "from_email": "support@iatistandard.org",
        "to_name": "Alex Admin",
        "to_email": "alex.admin@example.org",
        "user_requesting_join_name": "Sam User",
        "user_requesting_join_email": "sam.user@example.org",
        "org_name": "Example Org",
        "site_url": "https://account.iatistandard.org",
        "org_id": "EX-123",
    }

    result = generator.generate_email_content(
        EmailType.USER_REQUESTED_TO_JOIN_ORG,
        **template_values,
    )

    assert isinstance(result, Email)
    _assert_template_variables_replaced(
        result.subject,
        templates_dir / "user_requested_to_join_org_subject.txt",
        template_values,
    )
    _assert_template_variables_replaced(
        result.content_text,
        templates_dir / "user_requested_to_join_org.txt",
        template_values,
    )
    _assert_template_variables_replaced(
        result.content_html,
        templates_dir / "user_requested_to_join_org.html",
        template_values,
    )


def test_generate_email_content_new_org_needs_approval() -> None:
    templates_dir = Path(__file__).resolve().parents[2] / "email_templates"
    generator = EmailGenerator(str(templates_dir))

    template_values = {
        "from_name": "IATI Registry",
        "from_email": "support@iatistandard.org",
        "to_name": "IATI Support Team",
        "to_email": "support@iatistandard.org",
        "org_name": "Example Org",
        "org_short_name": "example-org",
        "org_human_readable_name": "Example Organisation",
        "org_id": "EX-123",
        "site_url": "https://account.iatistandard.org",
        "user_name": "Alex Admin",
        "user_email": "alex.admin@example.org",
        "user_id": "USER-456",
        "creation_date": "2026-01-28",
    }

    result = generator.generate_email_content(
        EmailType.NEW_ORG_NEEDS_APPROVAL,
        **template_values,
    )

    assert isinstance(result, Email)
    _assert_template_variables_replaced(
        result.subject,
        templates_dir / "new_org_needs_approval_subject.txt",
        template_values,
    )
    _assert_template_variables_replaced(
        result.content_text,
        templates_dir / "new_org_needs_approval.txt",
        template_values,
    )
    _assert_template_variables_replaced(
        result.content_html,
        templates_dir / "new_org_needs_approval.html",
        template_values,
    )
