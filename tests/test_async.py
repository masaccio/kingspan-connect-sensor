"""Tests specific to the asynchronous Kingspan Connect Sensor client."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from zeep import AsyncClient as AsyncSoapClient

from connectsensor import (
    APIVersion,
    AsyncSensorClient,
    KingspanAPIError,
    KingspanErrorCode,
)

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


@pytest.mark.asyncio
async def test_init_exception(mocker: MockerFixture) -> None:
    """Verify client initialization failures are wrapped as KingspanAPIError."""
    mocker.patch("httpx.AsyncClient", side_effect=Exception("Test zeep init"))
    with pytest.raises(
        KingspanAPIError,
        match="Unexpected request failure: Test zeep init",
    ) as exc_info:
        async with AsyncSensorClient(version=APIVersion.CONNECT_V1) as _:
            pass
    assert exc_info.value.code == KingspanErrorCode.UNKNOWN


@pytest.mark.asyncio
@pytest.mark.usefixtures("mock_wsdl")
@pytest.mark.parametrize("api_version", [APIVersion.KNECT_V1, APIVersion.CONNECT_V1])
async def test_async_client_injection(api_version: APIVersion) -> None:
    """Verify injected HTTPX clients bypass lifecycle management but WSDL clients are closed."""
    # pylint: disable=protected-access
    mock_client = AsyncMock(spec=httpx.AsyncClient)

    with patch("connectsensor.client.httpx.Client", autospec=True) as mock_sync_client:
        mock_wsdl_instance = mock_sync_client.return_value

        async with AsyncSensorClient(version=api_version, client=mock_client) as client:
            assert client._has_injected_client is True
            if api_version == APIVersion.CONNECT_V1:
                assert isinstance(client._client, AsyncSoapClient)
                assert client._client.transport.client == mock_client
            else:
                assert client._client == mock_client

        mock_client.aclose.assert_not_called()

        if api_version == APIVersion.CONNECT_V1:
            mock_wsdl_instance.close.assert_called_once()
        else:
            mock_sync_client.assert_not_called()

    with patch("connectsensor.client.httpx.AsyncClient", autospec=True) as mock_internal:
        mock_internal_instance = mock_internal.return_value

        async with AsyncSensorClient(version=api_version) as client:
            assert client._has_injected_client is False
            if api_version == APIVersion.CONNECT_V1:
                assert isinstance(client._client, AsyncSoapClient)
            else:
                assert client._client == mock_internal_instance

        mock_internal_instance.aclose.assert_called_once()
