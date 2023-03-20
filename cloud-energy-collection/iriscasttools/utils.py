import subprocess
import time
import os
import psutil
from typing import Dict

def retry(func, retry_on: (Exception,), retries: int = 3, delay: int = 3, backoff: int = 2):    
    """A retry function """
   
    for i in range(retries + 1):
        try:
            return func()
        except retry_on:
            if i == retries:
                return None
        seconds = delay + (backoff * i)
        time.sleep(seconds)
    return wrapper


def run_cmd(cmd_args: str): 
    """ Run command with given arguments and return output """
    res_list = subprocess.Popen(
        cmd_args, 
        shell=True, 
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    ).communicate()

    # assert we did not find any errors
    assert not res_list[1]  
    return res_list[0]


def check_ipmi_conn():
    """ Check if IPMItool exists and can be connected to """ 
    return any([
        os.path.exists(f) for f in ["/dev/ipmi0", "/dev/ipmi/0", "/dev/ipmidev/0"]
    ])


def ipmi_raw_power_query():
    """ Get raw power query from IPMItool """
    try:
        return retry(
            lambda: run_cmd("/usr/sbin/ipmi-dcmi --get-system-power-statistics"),
            AssertionError,
            retries= 3,
            delay = 3, 
            backoff = 2,
        )
        
    except AssertionError:
        return None

def to_csv(stats: Dict, include_header: bool = False):
    """ convert output to csv """ 
    res = ",".join([str(s) for s in stats.values()])
    if include_header:
        return f"{','.join(stats.keys())}\n{res}"
    return res


def get_ipmi_power_stats(*args):
    """ Get ipmi power stats as dictionary. 
    Stats passed as argument can be one or more of:
        "current_power",
        "minimum_power_over_sampling_duration"
        "maximum_power_over_sampling_duration",
        "average_power_over_sampling_duration",
        "statistics_reporting_time_period"
    """
    if not check_ipmi_conn():
        return None
    res = ipmi_query_power()

    power_stats = {x:'' for x in args}

    if res:
        for line in res.splitlines():
            line_str = line.split(b":")
            stat = line_str[0].decode().strip().lower().replace(" ", "_")
            
            val_str = ":".join([l.decode() for l in line_str[1:]]).strip()

            if stat in power_stats.keys():
                power_stats[stat] = re.search("[0-9]+", stat).group(0)

    return power_stats

def get_os_load(*args):
    """ get os load average from os library """ 
    res = {x:'' for x in args}
    
    stats = {
        "os_load_1": '',
        "os_load_5": '',
        "os_loads_15": ''
    }

    try:
        stats["os_load_1"], 
        stats["os_load_5"],
        stats["os_load_15"] = os.getloadavg()
    except OSError:
        pass

    res.update({k:v for k, v in stats.items() if k in args})
    return res 

def get_ram_usage(*args):
    """ Get Ram usage: (Used RAM / Total RAM) * 100 """
    res = {x:'' for x in args}

    stats = {
        "max_ram_kb": '', 
        "used_ram_kb": '',
        "ram_usage_percentage": '' 
    }

    try:
        stats['max_ram_kb'] = int(
            retry(
                lambda: run_cmd("free -k | sed -n '2p' | awk '{print $2}'"),
                retry_on=AssertionError,
                retries=3,
                delay=3,
                backoff=2
            )
        )
        stats['used_ram_kb'] = int(
            retry(
                lambda: run_cmd("free -k | sed -n '2p' | awk '{print $2}'"),
                retry_on=AssertionError,
                retries=3,
                delay=3,
                backoff=2
            )
        )

        if max_ram and used_ram:
            stat['ram_usage_percentage'] = round(
                (used_ram / max_ram) * 100, 3
            )

    except (AssertionError, ValueError):
        pass
   
    res.update({k:v for k,v in stats.items() if k in args})
    return res