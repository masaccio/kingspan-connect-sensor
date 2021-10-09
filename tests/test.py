from unittest.mock import patch
from pytest import raises

from mock_requests import mock_get, mock_post
from connectsensor import SensorClient, APIError


@patch("requests.sessions.Session.post", side_effect=mock_post)
@patch("requests.sessions.Session.get", side_effect=mock_get)
def test_valid_login(mock_get, mock_post):
    client = SensorClient()
    mock_get.assert_called_with(
        "https://www.connectsensor.com/soap/MobileApp.asmx?WSDL", timeout=300
    )

    client.login("test@example.com", "s3cret")
    mock_post.assert_called()

    tanks = client.tanks()
    assert tanks[0].name() == "TestTank"
    assert tanks[0].capacity() == "2000"
    assert tanks[0].serial_number() == "20001000"
    assert tanks[0].model() == "TestModel"
    assert mock_post.call_count == 2


@patch("requests.sessions.Session.post", side_effect=mock_post)
@patch("requests.sessions.Session.get", side_effect=mock_get)
def test_invalid_login(mock_get, mock_post):
    with raises(APIError) as e:
        client = SensorClient()
        client.login("invalid", "invalid")
    assert str(e.value) == "Authentication Failed, Invalid Login"


@patch("requests.sessions.Session.post", side_effect=mock_post)
@patch("requests.sessions.Session.get", side_effect=mock_get)
def test_levels(mock_get, mock_post):
    client = SensorClient()
    client.login("test@example.com", "s3cret")
    tanks = client.tanks()
    levels = tanks[0].level()
    assert levels["SignalmanNo"] == 20001000
    assert levels["LevelLitres"] == 1000
    assert levels["LevelLitres"] == 1000

    history = tanks[0].history()

    assert mock_post.call_count == 3
