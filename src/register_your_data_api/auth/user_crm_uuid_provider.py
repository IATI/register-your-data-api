from abc import ABC, abstractmethod

from .models import UserAndCredentials


class UserCRMUUIDProvider(ABC):

    _configuration_str: str

    def __init__(self, configuration_str: str) -> None:
        self._configuration_str = configuration_str

    @abstractmethod
    def get_crm_uuid(self, user: UserAndCredentials) -> str:
        """Returns the user's CRM ID"""
        raise NotImplementedError
