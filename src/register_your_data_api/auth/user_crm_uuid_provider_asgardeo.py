import json

import requests

from .models import UserAndCredentials
from .user_crm_uuid_provider import UserCRMUUIDProvider


class UserCRMUUIDProviderAsgardeo(UserCRMUUIDProvider):

    def get_crm_uuid(self, user: UserAndCredentials) -> str:
        """Returns the user's CRM ID"""

        response = requests.get(self._configuration_str, headers={"Authorization": "Bearer " + user.access_token})

        response_payload = json.loads(response.content)

        return str(response_payload["externalId"])
