from unittest.mock import patch

import pytest
from sqlalchemy import select

from src.auth.commands.create_test_user import main
from src.auth.model import UserModel


@pytest.mark.anyio
async def test_create_test_user(db_session):
    with (
        patch("builtins.input", return_value="newuser@example.com"),
        patch("src.auth.commands.create_test_user.getpass", return_value="secretpass123"),
    ):
        await main()

    stmt = select(UserModel).where(UserModel.email == "newuser@example.com")
    result = await db_session.execute(stmt)
    user = result.scalar_one_or_none()

    assert user is not None
    assert user.email == "newuser@example.com"
