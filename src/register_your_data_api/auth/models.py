import pydantic

from .fga.fga_validator import FineGrainedAuthorisationUserValidator


class UserAndCredentials(pydantic.BaseModel):
    """Class to contain user information and credentials obtained from the access token, CRM and identity service"""

    access_token: str  # Store the raw access token b/c we need to use to make requests to Asgardeo
    sub: str  # User ID in the identity service.
    user_id_crm: str | None  # ID of Person in the CRM.
    scopes: str  # Scopes that the access token has (from the identity service).
    audience: list[str]  # Audience from the access token (from the identity service).
    fga_user_validator: FineGrainedAuthorisationUserValidator | None

    @property
    def validator(self) -> FineGrainedAuthorisationUserValidator:
        if self.fga_user_validator is None:
            raise ValueError
        return self.fga_user_validator
