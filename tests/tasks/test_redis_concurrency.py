import asyncio
import concurrent.futures
from unittest.mock import AsyncMock, patch

import pytest

from src.integration.sync_status import RedisManager
from src.ws.manager import ConnectionManager


@pytest.mark.asyncio
async def test_redis_manager_concurrency():
    """Verify that RedisManager manages loop-scoped clients and cleans up closed loops."""
    redis_url = "redis://localhost:6379/0"
    manager = RedisManager(redis_url)

    mock_client_instances = []

    def mock_from_url(*args, **kwargs):
        mock_client = AsyncMock()
        mock_client_instances.append(mock_client)
        return mock_client

    with patch("redis.asyncio.from_url", side_effect=mock_from_url):
        # 1. Run in two different threads, each creating its own event loop
        def run_in_thread():
            async def task():
                async with manager.client() as client:
                    return client, asyncio.get_running_loop()

            return asyncio.run(task())

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(run_in_thread) for _ in range(2)]
            results = [f.result() for f in futures]

        # Verify that two distinct loops were used
        client1, loop1 = results[0]
        client2, loop2 = results[1]

        assert loop1 is not loop2
        # Verify that they got different client instances
        assert client1 is not client2
        assert len(mock_client_instances) == 2

        # Verify both loop clients are initially stored in manager._clients
        assert loop1 in manager._clients
        assert loop2 in manager._clients

        # Since these threads finished, their loops are closed.
        assert loop1.is_closed()
        assert loop2.is_closed()

        # 2. Access from the current test running loop
        current_loop = asyncio.get_running_loop()
        async with manager.client() as current_client:
            # Running manager.client() should clean up the closed loops
            assert loop1 not in manager._clients
            assert loop2 not in manager._clients
            # The current loop client should be initialized
            assert current_loop in manager._clients
            assert manager._clients[current_loop] is current_client

        # Verify that aclose was called on the closed loops' clients
        for client in mock_client_instances:
            if client is not current_client:
                client.aclose.assert_called()

        await manager.close()
        assert len(manager._clients) == 0


@pytest.mark.asyncio
async def test_connection_manager_concurrency():
    """Verify that ConnectionManager manages loop-scoped clients and cleans up closed loops."""
    redis_url = "redis://localhost:6379/0"
    manager = ConnectionManager()

    mock_client_instances = []

    def mock_from_url(*args, **kwargs):
        mock_client = AsyncMock()
        mock_client_instances.append(mock_client)
        return mock_client

    with (
        patch.object(ConnectionManager, "init_redis", ConnectionManager.orig_init_redis),
        patch.object(ConnectionManager, "close", ConnectionManager.orig_close),
        patch("redis.asyncio.from_url", side_effect=mock_from_url),
    ):
        # 1. Run in two different threads/event loops
        def run_in_thread():
            async def task():
                await manager.init_redis(redis_url, run_listener=False)
                client = manager.get_redis_client()
                return client, asyncio.get_running_loop()

            return asyncio.run(task())

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(run_in_thread) for _ in range(2)]
            results = [f.result() for f in futures]

        client1, loop1 = results[0]
        client2, loop2 = results[1]

        assert loop1 is not loop2
        assert client1 is not client2
        assert len(mock_client_instances) == 2

        assert loop1 in manager._clients
        assert loop2 in manager._clients

        assert loop1.is_closed()
        assert loop2.is_closed()

        # 2. Access from current loop should trigger cleanup
        current_loop = asyncio.get_running_loop()
        await manager.init_redis(redis_url, run_listener=False)
        current_client = manager.get_redis_client()

        # Closed loops should have been cleaned up
        assert loop1 not in manager._clients
        assert loop2 not in manager._clients
        assert current_loop in manager._clients
        assert manager._clients[current_loop] is current_client

        # Verify that aclose was called on the closed loops' clients
        for client in mock_client_instances:
            if client is not current_client:
                client.aclose.assert_called()

        await manager.close()
        assert len(manager._clients) == 0


