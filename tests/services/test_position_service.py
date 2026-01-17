from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from stockholm import Money

from src.repositories.position import PositionRepository
from src.schemas.account import AccountTotals
from src.schemas.position import Position
from src.services.position import PositionService


class TestPositionService:
    """Test suite for PositionService."""

    @pytest.fixture
    def mock_position_repo(self):
        return Mock(spec=PositionRepository)

    @pytest.fixture
    def position_service(self, mock_position_repo):
        return PositionService(mock_position_repo)

    @pytest.mark.asyncio
    async def test_get_total_for_account_empty_positions(self, position_service, mock_position_repo):
        """Test get_total_for_account with no positions."""
        account_id = uuid4()
        mock_position_repo.get_by_account = AsyncMock(return_value=[])

        result = await position_service.get_total_for_account(account_id)

        assert isinstance(result, AccountTotals)
        assert result.cost == Money(0)
        mock_position_repo.get_by_account.assert_called_once_with(account_id)

    @pytest.mark.asyncio
    async def test_get_total_for_account_with_positions(self, position_service, mock_position_repo):
        """Test get_total_for_account with positions."""
        account_id = uuid4()
        positions = [
            Position(
                id=uuid4(),
                account_id=account_id,
                security_id=uuid4(),
                quantity=10.0,
                average_cost=20.0,
                created_at="2023-01-01"
            ),
            Position(
                id=uuid4(),
                account_id=account_id,
                security_id=uuid4(),
                quantity=5.0,
                average_cost=15.0,
                created_at="2023-01-01"
            ),
        ]
        mock_position_repo.get_by_account = AsyncMock(return_value=positions)

        result = await position_service.get_total_for_account(account_id)

        expected_cost = Money(10 * 20 + 5 * 15, "CAD")  # 200 + 75 = 275
        assert result.cost == expected_cost
        mock_position_repo.get_by_account.assert_called_once_with(account_id)

    @pytest.mark.asyncio
    async def test_get_total_for_account_with_none_average_cost(self, position_service, mock_position_repo):
        """Test get_total_for_account with positions having None average_cost."""
        account_id = uuid4()
        positions = [
            Position(
                id=uuid4(),
                account_id=account_id,
                security_id=uuid4(),
                quantity=10.0,
                average_cost=None,  # Should treat as 0
                created_at="2023-01-01"
            ),
        ]
        mock_position_repo.get_by_account = AsyncMock(return_value=positions)

        result = await position_service.get_total_for_account(account_id)

        assert result.cost == Money(0)
        mock_position_repo.get_by_account.assert_called_once_with(account_id)

    @pytest.mark.asyncio
    async def test_get_total_for_account_mixed_costs(self, position_service, mock_position_repo):
        """Test get_total_for_account with mix of valid and None costs."""
        account_id = uuid4()
        positions = [
            Position(
                id=uuid4(),
                account_id=account_id,
                security_id=uuid4(),
                quantity=2.0,
                average_cost=50.0,
                created_at="2023-01-01"
            ),
            Position(
                id=uuid4(),
                account_id=account_id,
                security_id=uuid4(),
                quantity=3.0,
                average_cost=None,
                created_at="2023-01-01"
            ),
        ]
        mock_position_repo.get_by_account = AsyncMock(return_value=positions)

        result = await position_service.get_total_for_account(account_id)

        expected_cost = Money(2 * 50, "CAD")  # 100, None treated as 0
        assert result.cost == expected_cost
        mock_position_repo.get_by_account.assert_called_once_with(account_id)

    def test_compute_cost_empty_list(self, position_service):
        """Test _compute_cost with empty positions list."""
        result = position_service._compute_cost([])
        assert result == Money(0)

    def test_compute_cost_single_position(self, position_service):
        """Test _compute_cost with single position."""
        positions = [
            Position(
                id=uuid4(),
                account_id=uuid4(),
                security_id=uuid4(),
                quantity=10.5,
                average_cost=12.34,
                created_at="2023-01-01"
            ),
        ]
        result = position_service._compute_cost(positions)
        expected = Money(round(10.5 * 12.34, 2), "CAD")
        assert result == expected

    def test_compute_cost_multiple_positions(self, position_service):
        """Test _compute_cost with multiple positions."""
        positions = [
            Position(id=uuid4(), account_id=uuid4(), security_id=uuid4(), quantity=1, average_cost=10, created_at="2023-01-01"),
            Position(id=uuid4(), account_id=uuid4(), security_id=uuid4(), quantity=2, average_cost=5, created_at="2023-01-01"),
        ]
        result = position_service._compute_cost(positions)
        expected = Money(10 + 10, "CAD")  # 1*10 + 2*5 = 20
        assert result == expected

    def test_compute_cost_with_none_cost(self, position_service):
        """Test _compute_cost handles None average_cost."""
        positions = [
            Position(id=uuid4(), account_id=uuid4(), security_id=uuid4(), quantity=10, average_cost=None, created_at="2023-01-01"),
        ]
        result = position_service._compute_cost(positions)
        assert result == Money(0)
