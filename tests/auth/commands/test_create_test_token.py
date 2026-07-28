from unittest.mock import MagicMock, patch

import jwt
import pytest

from src.auth.commands.create_test_token import main
from src.config.settings import settings


@pytest.mark.anyio
async def test_create_test_token_with_custom_user_id(db_session):
    inputs = ["test@example.com", "11111111-1111-1111-1111-111111111111"]
    mock_rprint = MagicMock()

    with (
        patch("builtins.input", side_effect=inputs),
        patch("src.auth.commands.create_test_token.rprint", mock_rprint),
    ):
        await main()

    mock_rprint.assert_called_once()
    token = mock_rprint.call_args[0][0]
    payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
    assert payload["sub"] == "test@example.com"
    assert payload["user_id"] == "11111111-1111-1111-1111-111111111111"


@pytest.mark.anyio
async def test_create_test_token_default_user_id(db_session):
    inputs = ["default@example.com", ""]
    mock_rprint = MagicMock()

    with (
        patch("builtins.input", side_effect=inputs),
        patch("src.auth.commands.create_test_token.rprint", mock_rprint),
    ):
        await main()

    mock_rprint.assert_called_once()
    token = mock_rprint.call_args[0][0]
    payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
    assert payload["sub"] == "default@example.com"
    assert payload["user_id"] == "00000000-0000-0000-0000-000000000000"
