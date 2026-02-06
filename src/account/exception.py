from src.account.api_types import PortfolioId
from src.exception import EntityNotFoundException


class PortfolioNotFoundException(EntityNotFoundException):
    """Raised when a portfolio is not found."""
    
    def __init__(self, portfolio_id: PortfolioId):
        self.entity_id = str(portfolio_id)
        self.entity_name = "Portfolio"

        super().__init__(str(self))