import logging
import subprocess
from typing import Optional

import requests
from requests.adapters import HTTPAdapter
from requests_kerberos import HTTPKerberosAuth
from urllib3.util.retry import Retry

from rabbit_consumer.os_descriptions.os_descriptions import OsDescription
from rabbit_consumer.vm_data import VmData
from rabbit_consumer.consumer_config import ConsumerConfig

MODEL = "vm-openstack"
MAKE_SUFFIX = "/host/{0}/command/make"
MANAGE_SUFFIX = "/host/{0}/command/manage?hostname={0}&{1}={2}&force=true"
HOST_CHECK_SUFFIX = "/host/{0}"
CREATE_MACHINE_SUFFIX = (
    "/next_machine/{0}?model={1}&serial={2}&vmhost={3}&cpucount={4}&memory={5}"
)

ADD_INTERFACE_SUFFIX = "/machine/{0}/interface/{1}?mac={2}"

UPDATE_INTERFACE_SUFFIX = "/machine/{0}/interface/{1}?boot&default_route"

ADD_INTERFACE_ADDRESS_SUFFIX = (
    "/interface_address?machine={0}&interface={1}&ip={2}&fqdn={3}"
)

DELETE_HOST_SUFFIX = "/host/{0}"
DELETE_MACHINE_SUFFIX = "/machine/{0}"

logger = logging.getLogger(__name__)


class AquilonError(Exception):
    """
    Base class for Aquilon errors
    """


def verify_kerberos_ticket():
    logger.debug("Checking for valid Kerberos Ticket")

    if subprocess.call(["klist", "-s"]) == 1:
        raise RuntimeError("No shared Kerberos ticket found.")

    logger.debug("Kerberos ticket success")
    return True


def setup_requests(url, method, desc, params: Optional[dict] = None):
    verify_kerberos_ticket()

    logger.debug("%s: %s", method, url)

    session = requests.Session()
    session.verify = "/etc/grid-security/certificates/aquilon-gridpp-rl-ac-uk-chain.pem"
    retries = Retry(total=5, backoff_factor=0.1, status_forcelist=[503])
    session.mount("https://", HTTPAdapter(max_retries=retries))
    if method == "post":
        response = session.post(url, auth=HTTPKerberosAuth(), params=params)
    elif method == "put":
        response = session.put(url, auth=HTTPKerberosAuth(), params=params)
    elif method == "delete":
        response = session.delete(url, auth=HTTPKerberosAuth(), params=params)
    else:
        response = session.get(url, auth=HTTPKerberosAuth(), params=params)

    if response.status_code == 400:
        # This might be an expected error, so don't log it
        logger.debug("AQ Error Response: %s", response.text)
        raise AquilonError(response.text)

    if response.status_code != 200:
        logger.error("%s: Failed: %s", desc, response.text)
        logger.error(url)
        raise ConnectionError(
            f"Failed {desc}: {response.status_code} -" "{response.text}"
        )

    logger.debug("Success: %s ", desc)
    logger.debug("Response: %s", response.text)
    return response.text


def aq_make(hostname: str, os_data: OsDescription):
    logger.debug("Attempting to make templates for %s", hostname)

    params = {
        "personality": os_data.aq_default_personality,
        "osversion": os_data.aq_os_version,
        "osname": os_data.aq_os_name,
        "archetype": "cloud",
    }

    assert all(
        i for i in params.values()
    ), "Some fields were not set in the OS description"

    if not hostname or not hostname.strip():
        raise ValueError("Hostname cannot be empty")

    url = ConsumerConfig().aq_url + MAKE_SUFFIX.format(hostname)
    setup_requests(url, "post", "Make Template: ", params)


def aq_manage(hostname, env_type, env_name):
    logger.debug("Attempting to manage %s to %s %s", hostname, env_type, env_name)

    url = ConsumerConfig().aq_url + MANAGE_SUFFIX.format(hostname, env_type, env_name)

    setup_requests(url, "post", "Manage Host")


def create_machine(message, hostname, prefix):
    logger.debug("Attempting to create machine for %s ", hostname)

    vcpus = message.get("payload").get("vcpus")
    memory_mb = message.get("payload").get("memory_mb")
    uuid = message.get("payload").get("instance_id")
    vmhost = message.get("payload").get("host")

    url = ConsumerConfig().aq_url + CREATE_MACHINE_SUFFIX.format(
        prefix, MODEL, uuid, vmhost, vcpus, memory_mb
    )

    response = setup_requests(url, "put", "Create Machine")
    return response


def delete_machine(machinename):
    logger.debug("Attempting to delete machine for %s", machinename)

    url = ConsumerConfig().aq_url + DELETE_MACHINE_SUFFIX.format(machinename)

    setup_requests(url, "delete", "Delete Machine")


def create_host(
    hostname,
    machinename,
    firstip,
    osname,
    osversion,
):
    logger.debug("Attempting to create host for %s ", hostname)
    config = ConsumerConfig()

    default_domain = config.aq_domain
    default_personality = config.aq_personality
    default_archetype = config.aq_archetype

    url = config.aq_url
    url += (
        f"/host/{hostname}?"
        f"machine={machinename}"
        f"&ip={firstip}"
        f"&archetype={default_archetype}"
        f"&domain={default_domain}"
        f"&personality={default_personality}"
        f"&osname={osname}"
        f"&osversion={osversion}"
    )

    logger.debug(url)

    # reset personality etc ...
    setup_requests(url, "put", "Host Create")


def delete_host(hostname):
    logger.debug("Attempting to delete host for %s ", hostname)
    url = ConsumerConfig().aq_url + DELETE_HOST_SUFFIX.format(hostname)
    setup_requests(url, "delete", "Host Delete")


def add_machine_interface(machinename, macaddr, interfacename):
    logger.debug(
        "Attempting to add interface %s to machine %s ", interfacename, machinename
    )

    url = ConsumerConfig().aq_url + ADD_INTERFACE_SUFFIX.format(
        machinename, interfacename, macaddr
    )

    setup_requests(url, "put", "Add Machine Interface")


def add_machine_interface_address(machinename, ipaddr, interfacename, hostname):
    logger.debug("Attempting to add address ip %s to machine %s ", ipaddr, machinename)

    url = ConsumerConfig().aq_url + ADD_INTERFACE_ADDRESS_SUFFIX.format(
        machinename, interfacename, ipaddr, hostname
    )

    setup_requests(url, "put", "Add Machine Interface Address")


def update_machine_interface(machinename, interfacename):
    logger.debug("Attempting to bootable %s ", machinename)

    url = ConsumerConfig().aq_url + UPDATE_INTERFACE_SUFFIX.format(
        machinename, interfacename
    )

    setup_requests(url, "post", "Update Machine Interface")


def set_env(aq_details: VmData, domain: str, hostname: str, sandbox: str = None):
    if domain:
        aq_manage(hostname, "domain", domain)
    else:
        aq_manage(hostname, "sandbox", sandbox)

    aq_make(hostname, aq_details)


def check_host_exists(hostname: str) -> bool:
    logger.debug("Checking if hostname exists: %s", hostname)
    url = ConsumerConfig().aq_url + HOST_CHECK_SUFFIX.format(hostname)
    try:
        setup_requests(url, "get", "Check Host")
    except AquilonError as err:
        if f"Host {hostname} not found." in str(err):
            return False
        raise
    return True
