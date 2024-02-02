from unittest.mock import patch, call, NonCallableMock, MagicMock
import pytest

from service_status_to_influx import (
    get_hypervisor_properties,
    get_service_properties,
    get_agent_properties,
    convert_to_data_string,
    get_service_prop_string,
    get_all_hv_details,
    update_with_service_statuses,
    update_with_agent_statuses,
    get_all_service_statuses,
    main
)


def test_get_hypervisor_properties_state_up():
    mock_hv = {
        "state": "up",
        "memory_size": 1,
        "memory_used": 2,
        "memory_free": 3,
        "vcpus_used": 4,
        "vcpus": 5,
    }
    expected_result = {"hv": {
        "aggregate": "no-aggregate",
        "memorymax": 1,
        "memoryused": 2,
        "memoryavailable": 3,
        "cpuused": 4,
        "cpumax": 5,
        "cpuavailable": 1,
        "agent": 1,
        "state": 1,
        "statetext": "Up"
    }}
    assert get_hypervisor_properties(mock_hv) == expected_result


def test_get_hypervisor_properties_state_down():
    mock_hv = {
        "state": "down",
        "memory_size": 1,
        "memory_used": 2,
        "memory_free": 3,
        "vcpus_used": 4,
        "vcpus": 5,
    }
    expected_result = {"hv": {
        "aggregate": "no-aggregate",
        "memorymax": 1,
        "memoryused": 2,
        "memoryavailable": 3,
        "cpuused": 4,
        "cpumax": 5,
        "cpuavailable": 1,
        "agent": 1,
        "state": 0,
        "statetext": "Down"
    }}
    assert get_hypervisor_properties(mock_hv) == expected_result


def test_get_service_properties_enabled_up():
    mock_service = {
        "binary": "foo",
        "status": "enabled",
        "state": "up"
    }
    expected_result = {
        "foo": {
            "status": 1,
            "statustext": "Enabled",
            "state": 1,
            "statetext": "Up",
            "agent": 1
        }
    }
    assert get_service_properties(mock_service) == expected_result


def test_get_service_properties_disabled_down():
    mock_service = {
        "binary": "bar",
        "status": "disabled",
        "state": "down"
    }
    expected_result = {
        "bar": {
            "status": 0,
            "statustext": "Disabled",
            "state": 0,
            "statetext": "Down",
            "agent": 1
        }
    }
    assert get_service_properties(mock_service) == expected_result


def test_get_agent_properties_alive_admin_up():
    mock_agent = {
        "binary": "foo",
        "is_alive": True,
        "is_admin_state_up": True,
    }
    expected_result = {
        "foo": {
            "state": 1,
            "statetext": "Up",
            "status": 1,
            "statustext": "Enabled",
            "agent": 1
        }
    }
    assert get_agent_properties(mock_agent) == expected_result


def test_get_agent_properties_disabled_down():
    mock_agent = {
        "binary": "bar",
        "is_alive": False,
        "is_admin_state_up": False,
    }
    expected_result = {
        "bar": {
            "state": 0,
            "statetext": "Down",
            "status": 0,
            "statustext": "Disabled",
            "agent": 1
        }
    }
    assert get_agent_properties(mock_agent) == expected_result


def test_convert_to_data_string_no_items():
    """
    Tests convert_to_data_string returns empty string when given no details
    """
    assert convert_to_data_string(NonCallableMock(), {}) == ""


@patch("service_status_to_influx.get_service_prop_string")
def test_convert_to_data_string_one_hv_one_service(mock_get_service_prop_string):
    """
    Tests convert_to_data_string works with single entry in details
    """
    mock_instance = "prod"
    mock_service_details = NonCallableMock()
    mock_details = {"hv1": {"service1": mock_service_details}}

    mock_get_service_prop_string.return_value = "prop1=val1"

    res = convert_to_data_string(mock_instance, mock_details)
    assert res == 'ServiceStatus,host="hv1",service="service1",instance=Prod prop1=val1'
    mock_get_service_prop_string.assert_called_once_with(mock_service_details)


@patch("service_status_to_influx.get_service_prop_string")
def test_convert_to_data_string_one_hv_multi_service(mock_get_service_prop_string):
    """
    Tests convert_to_data_string works with single entry in details with multiple service binaries
    """
    mock_instance = "prod"
    mock_service_details_1 = NonCallableMock()
    mock_service_details_2 = NonCallableMock()
    mock_details = {"hv1": {
        "service1": mock_service_details_1,
        "service2": mock_service_details_2
    }}

    mock_get_service_prop_string.side_effect = ["prop1=val1", "prop1=val2"]

    res = convert_to_data_string(mock_instance, mock_details)
    assert res == (
        'ServiceStatus,host="hv1",service="service1",instance=Prod prop1=val1'
        'ServiceStatus,host="hv1",service="service2",instance=Prod prop1=val2'
    )
    mock_get_service_prop_string.assert_has_calls([
        call(mock_service_details_1), call(mock_service_details_2)
    ])


@patch("service_status_to_influx.get_service_prop_string")
def test_convert_to_data_string_multi_item(mock_get_service_prop_string):
    """
    Tests convert_to_data_string works with multiple entries in dict for details
    """
    mock_instance = "prod"
    mock_service_details_1 = NonCallableMock()
    mock_service_details_2 = NonCallableMock()
    mock_service_details_3 = NonCallableMock()
    mock_details = {
        "hv1": {
            "service1": mock_service_details_1,
            "service2": mock_service_details_2,
        },
        "hv2": {
            "service3": mock_service_details_3
        }
    }

    mock_get_service_prop_string.side_effect = [
        "prop1=val1", "prop1=val2", "prop1=val3"
    ]

    res = convert_to_data_string(mock_instance, mock_details)
    assert res == (
        'ServiceStatus,host="hv1",service="service1",instance=Prod prop1=val1'
        'ServiceStatus,host="hv1",service="service2",instance=Prod prop1=val2'
        'ServiceStatus,host="hv2",service="service3",instance=Prod prop1=val3'
    )
    mock_get_service_prop_string.assert_has_calls([
        call(mock_service_details_1), call(mock_service_details_2), call(mock_service_details_3)
    ])


def test_get_service_prop_string_empty_dict():
    props = {}
    expected_result = ''
    assert get_service_prop_string(props) == expected_result


def test_get_service_prop_string_with_string_props():
    props = {"statetext": "foo", "statustext": "bar", "aggregate": "baz"}
    expected_result = 'statetext="foo",statustext="bar",aggregate="baz"'
    assert get_service_prop_string(props) == expected_result


def test_get_service_prop_string_with_int_props():
    props = {"prop1": 1, "prop2": 2, "prop3": 3}
    expected_result = 'prop1="1i",prop2="2i",prop3="3i"'
    assert get_service_prop_string(props) == expected_result


@patch("service_status_to_influx.get_hypervisor_properties")
def test_get_all_hv_details(mock_get_hypervisor_properties):
    mock_conn = MagicMock()
    mock_hvs = [{"name": "hv1"}, {"name": "hv2"}, {"name": "hv3"}]

    mock_aggregates = [
        {"name": "ag1", "hosts": ["hv1", "hv2"]},
        {"name": "ag2", "hosts": ["hv3", "hv4"]},
        {"name": "ag3", "hosts": ["hv5"]},
    ]

    # stubs out getting props
    mock_get_hypervisor_properties.side_effect = [
        {"hv": {}}, {"hv": {}}, {"hv": {}}
    ]
    mock_conn.list_hypervisors.return_value = mock_hvs
    mock_conn.compute.aggregates.return_value = mock_aggregates
    res = get_all_hv_details(mock_conn)

    mock_conn.list_hypervisors.assert_called_once()
    mock_conn.compute.aggregates.assert_called_once()

    mock_get_hypervisor_properties.assert_has_calls(
        [call(hv) for hv in mock_hvs]
    )

    assert res == {
        "hv1": {"hv": {"aggregate": "ag1"}},
        "hv2": {"hv": {"aggregate": "ag1"}},
        "hv3": {"hv": {"aggregate": "ag2"}}
    }


@patch("service_status_to_influx.get_service_properties")
def test_update_with_service_statuses(mock_get_service_properties):
    mock_conn = MagicMock()
    mock_status_details = {
        "hv1": {"hv": {}, "foo": {}, "bar": {}},
        "hv2": {"hv": {}},
    }

    mock_services = [
        {"host": "hv1", "binary": "nova-compute"},
        {"host": "hv1", "binary": "other-svc"},
        {"host": "hv2", "binary": "other-svc"},
        {"host": "hv3", "binary": "nova-compute"},
    ]
    mock_conn.compute.services.return_value = mock_services

    # stubs out actually getting properties
    mock_get_service_properties.side_effect = [
        {"nova-compute": {"status": "enabled"}},
        {"other-service": {}},
        {"other-service": {"status": "enabled"}},
        {"nova-compute": {"status": "disabled"}}
    ]

    res = update_with_service_statuses(mock_conn, mock_status_details)

    mock_conn.compute.services.assert_called_once()
    mock_get_service_properties.assert_has_calls(
        [call(svc) for svc in mock_services]
    )
    assert res == {
        # shouldn't override what's already there
        # add hv status == nova-compute svc status
        "hv1": {
            "hv": {"status": "enabled"},
            "nova-compute": {"status": "enabled"},
            "foo": {}, "bar": {},
            "other-service": {}
        },
        # only nova-compute status adds hv status
        "hv2": {
            "hv": {},
            "other-service": {"status": "enabled"}
        },
        # adds what doesn't exist, no "hv" so no setting status
        "hv3": {"nova-compute": {"status": "disabled"}}
    }


@patch("service_status_to_influx.get_agent_properties")
def test_update_with_agent_statuses(mock_get_agent_properties):
    mock_conn = MagicMock()
    mock_status_details = {"hv1": {"foo": {}}, "hv2": {}}

    mock_agents = [
        {"host": "hv1", "binary": "ag1"},
        {"host": "hv1", "binary": "ag2"},
        {"host": "hv2", "binary": "ag1"},
        {"host": "hv3", "binary": "ag3"}
    ]
    mock_conn.network.agents.return_value = mock_agents

    # stubs out actually getting properties
    mock_get_agent_properties.side_effect = [
        {"ag1": {}}, {"ag2": {}}, {"ag1": {}}, {"ag3": {}},
    ]

    res = update_with_agent_statuses(mock_conn, mock_status_details)

    mock_conn.network.agents.assert_called_once()
    mock_get_agent_properties.assert_has_calls([call(agent) for agent in mock_agents])
    assert res == {
        # shouldn't override what's already there
        "hv1": {"foo": {}, "ag1": {}, "ag2": {}},
        "hv2": {"ag1": {}},
        # adds what doesn't exist
        "hv3": {"ag3": {}}
    }


@patch("service_status_to_influx.openstack")
@patch("service_status_to_influx.get_all_hv_details")
@patch("service_status_to_influx.update_with_service_statuses")
@patch("service_status_to_influx.update_with_agent_statuses")
@patch("service_status_to_influx.convert_to_data_string")
def test_get_all_service_statuses(
    mock_convert,
    mock_get_agent_statuses,
    mock_get_service_statuses,
    mock_get_hv_statuses,
    mock_openstack
):
    mock_instance = NonCallableMock()
    mock_conn = mock_openstack.connect.return_value
    res = get_all_service_statuses(mock_instance)
    mock_openstack.connect.assert_called_once_with(mock_instance)
    mock_get_hv_statuses.assert_called_once_with(mock_conn)
    mock_get_service_statuses.assert_called_once_with(mock_conn, mock_get_hv_statuses.return_value)
    mock_get_agent_statuses.assert_called_once_with(mock_conn, mock_get_service_statuses.return_value)
    mock_convert.assert_called_once_with(mock_instance, mock_get_agent_statuses.return_value)
    assert res == mock_convert.return_value


@patch("service_status_to_influx.run_scrape")
@patch("service_status_to_influx.parse_args")
def test_main(mock_parse_args, mock_run_scrape):
    mock_user_args = NonCallableMock()
    main(mock_user_args)
    mock_run_scrape.assert_called_once_with(mock_parse_args.return_value, get_all_service_statuses)
    mock_parse_args.assert_called_once_with(mock_user_args, description="Get All Service Statuses")
