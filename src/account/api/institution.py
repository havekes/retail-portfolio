from svcs import Container

from src.account.api_types import Institution
from src.account.repository import InstitutionRepository


class InstitutionApi:
    _institution_repository: InstitutionRepository

    def __init__(self, institution_repository: InstitutionRepository) -> None:
        self._institution_repository = institution_repository

    async def get_all_enabled_integrations(self) -> list[Institution]:
        """Retrieve a list of all enabled integrations."""
        institutions = await self._institution_repository.get_all_enabled_integrations()
        return [
            Institution(
                id=institution.id,
                name=institution.name,
                country=institution.country,
                website=institution.website,
                is_active=institution.is_active,
                integration_enabled=institution.integration_enabled,
            )
            for institution in institutions
        ]


async def institution_api_factory(container: Container) -> InstitutionApi:
    return InstitutionApi(
        institution_repository=await container.aget(InstitutionRepository),
    )
