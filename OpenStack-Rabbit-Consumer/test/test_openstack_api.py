from typing import Dict
from unittest import mock
from unittest.mock import NonCallableMock, patch, call, Mock

import pytest

from rabbit_consumer.openstack_api import authenticate, update_metadata


# This is duplicated as it matches a REST API call
# pylint: disable=duplicate-code
def _get_json_auth(rabbit_consumer: Mock, project_id) -> Dict:
    return {
        "auth": {
            "identity": {
                "methods": ["password"],
                "password": {
                    "user": {
                        "name": rabbit_consumer.get_env_str("OPENSTACK_USERNAME"),
                        "domain": {
                            "name": rabbit_consumer.get_env_str("OPENSTACK_DOMAIN_NAME")
                        },
                        "password": rabbit_consumer.get_env_str("OPENSTACK_PASSWORD"),
                    }
                },
            },
            "scope": {"project": {"id": project_id}},
        }
    }


@patch("rabbit_consumer.openstack_api.RabbitConsumer")
@patch("rabbit_consumer.openstack_api.requests")
def test_authenticate(requests, consumer):
    project_id = NonCallableMock()
    session = requests.Session.return_value
    session.post.return_value.status_code = 201

    authenticate(project_id)

    requests.Session.assert_called_once()
    session.mount.assert_called_once_with("https://", mock.ANY)
    session.post.assert_called_once()

    args = session.post.call_args
    assert args == call(
        consumer.get_env_str("OPENSTACK_AUTH_URL") + "/auth/tokens",
        json=_get_json_auth(consumer, project_id),
    )


@patch("rabbit_consumer.openstack_api.RabbitConsumer")
@patch("rabbit_consumer.openstack_api.requests")
def test_authenticate_throws(requests, _):
    session = requests.Session.return_value
    session.post.return_value.status_code = 500

    with pytest.raises(ConnectionRefusedError):
        authenticate(NonCallableMock())


@patch("rabbit_consumer.openstack_api.RabbitConsumer")
@patch("rabbit_consumer.openstack_api.requests")
@patch("rabbit_consumer.openstack_api.authenticate")
def test_update_metadata(auth, requests, consumer):
    project_id, instance_id = "mock_project", "mock_instance"
    metadata = NonCallableMock()
    session = requests.Session.return_value
    session.post.return_value.status_code = 200

    update_metadata(project_id, instance_id, metadata)

    session.mount.assert_called_once_with("https://", mock.ANY)
    auth.assert_called_once_with(project_id)
    session.post.assert_called_once()

    assert session.post.call_args == call(
        consumer.get_env_str("OPENSTACK_COMPUTE_URL")
        + f"{project_id}/servers/{instance_id}/metadata",
        headers={"Content-type": "application/json", "X-Auth-Token": auth.return_value},
        json={"metadata": metadata},
    )


@patch("rabbit_consumer.openstack_api.RabbitConsumer")
@patch("rabbit_consumer.openstack_api.authenticate")
@patch("rabbit_consumer.openstack_api.requests")
def test_update_metadata_throws_exception(_, __, requests):
    session = requests.Session.return_value
    session.post.return_value.status_code = 500

    with pytest.raises(ConnectionAbortedError):
        update_metadata(NonCallableMock(), NonCallableMock(), NonCallableMock())