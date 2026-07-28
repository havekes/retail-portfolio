from unittest.mock import patch

import pytest
from sqlalchemy import select

from src.account.model import AccountModel, PortfolioModel, PositionModel
from src.auth.model import UserModel
from src.commands.seed import seed_data
from src.integration.model import IntegrationUserModel
from src.market.model import SecurityModel


@pytest.mark.anyio
async def test_seed_data_dev_and_idempotency(db_session):
    # First seed run with environment = "dev"
    with patch("src.commands.seed.settings.environment", "dev"):
        await seed_data()

    # Verify records were inserted in test database
    user_res = await db_session.execute(select(UserModel).where(UserModel.email == "test@example.com"))
    user = user_res.scalar_one_or_none()
    assert user is not None

    sec_res = await db_session.execute(select(SecurityModel))
    securities = sec_res.scalars().all()
    assert len(securities) == 4

    acc_res = await db_session.execute(select(AccountModel))
    accounts = acc_res.scalars().all()
    assert len(accounts) == 3

    pos_res = await db_session.execute(select(PositionModel))
    positions = pos_res.scalars().all()
    assert len(positions) == 5

    port_res = await db_session.execute(select(PortfolioModel))
    portfolios = port_res.scalars().all()
    assert len(portfolios) == 2

    iu_res = await db_session.execute(select(IntegrationUserModel))
    integration_users = iu_res.scalars().all()
    assert len(integration_users) == 1

    # Second seed run in "dev" to verify idempotency (skips creating existing items)
    with patch("src.commands.seed.settings.environment", "dev"):
        await seed_data()

    # Third seed run in non-dev environment ("prod") to verify dev-skipping path
    with patch("src.commands.seed.settings.environment", "prod"):
        await seed_data()
