from unittest.mock import NonCallableMock, patch
import pytest
from netbox_api.netbox_connect import NetboxConnect


@pytest.fixture(name="instance")
def instance_fixture():
    """
    This fixture method calls the class being tested.
    :return: The class object.
    """
    url = NonCallableMock()
    token = NonCallableMock()
    return NetboxConnect(url, token)


def test_api_object(instance):
    """
    This test checks that the Api method is called once.
    """
    with patch("netbox_api.netbox_connect.nb") as mock_netbox:
        res = instance.api_object()
    mock_netbox.api.assert_called_once_with(instance.url, instance.token)
    assert res == mock_netbox.api.return_value
