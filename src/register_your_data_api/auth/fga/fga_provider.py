from abc import ABC, abstractmethod
from uuid import UUID

from .models import FineGrainedAuthorisationRoleAssociation


class FineGrainedAuthorisationProvider(ABC):

    @abstractmethod
    def setup(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def get_user_fine_grained_permissions(self, user: UUID) -> list[FineGrainedAuthorisationRoleAssociation]:
        """Returns a list of all the user's fine grained access roles"""
        raise NotImplementedError

    @abstractmethod
    def is_user_a_superadmin(self, user: UUID) -> bool:
        """Returns True if the user is a superadmin, else False"""
        raise NotImplementedError
