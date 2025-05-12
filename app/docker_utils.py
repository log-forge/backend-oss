import docker
import subprocess
import json
import time
import yaml
from pathlib import Path
from datetime import datetime, timezone
from dateutil.parser import isoparse
from collections import defaultdict

LOG_CACHE = defaultdict(list)

client = docker.from_env()
CONTAINER_DICT ={}

# Load alert keywords from config.yml
CONFIG_PATH = Path(__file__).parent / "config.yml"
with open(CONFIG_PATH, "r") as f:
    CONFIG = yaml.safe_load(f)

ALERT_KEYWORDS = CONFIG.get("alert", {}).get("keywords", [])

def get_subprocess(container_name):
    """Get CPU and memory usage of a Docker container using subprocess.
    Args:
        container_name (str): The name of the container.
    Returns:
        tuple: CPU and memory usage as strings.
    """
    res = subprocess.run(
        ['docker', 'stats', container_name, '--no-stream', '--format', '{{.CPUPerc}}|{{.MemUsage}}'],
        capture_output=True,
        text=True
    )
    if res.returncode == 0:
        cpu, mem = res.stdout.split('|')
        return cpu.strip(), mem.strip()
    return 'N/A', 'N/A'

# def get_logs(container_name: str, tail: int = 100):
#     """Get logs for a specific container by name.
#     Args:
#         container_name (str): The name of the container.
#         tail (int): The number of lines to show from the end of the logs.
#     Returns:
#         dict: A dictionary containing the logs.
#     """
#     global CONTAINER_DICT
#     container_info = CONTAINER_DICT.get(container_name)
#     if container_info is None:
#         create_docker_dict()
#         container_info = CONTAINER_DICT.get(container_name)
#     if not container_info:
#         return None
    
#     try:
#         container_obj = client.containers.get(container_info['container_id'])
#         logs = container_obj.logs(
#             tail=tail,
#             timestamps=True, 
#             follow=False,
#             stderr=True,
#             stdout=True).decode()
#         LOG_CACHE[container_name] = logs.splitlines()
#         return logs
#     except Exception as e:
#         print(f"Error fetching logs for {container_name}: {e}")
#         return 'N/A'

def get_ports(attrs:dict) -> list:
    """Extract and format port mappings from container attributes.
    Args:
        attrs (dict): The container's full attribute dictionary.   
    Returns:
        list: A list of port mapping strings.
    """

    ports = []
    raw_ports = attrs['NetworkSettings'].get('Ports') or {}

    for port, mappings in raw_ports.items():
        if mappings:
            for mapping in mappings:
                ports.append(f'{mapping["HostIp"]}:{mapping["HostPort"]} → {port}')
        else:
            ports.append(f'{port} (Not Exposed)')
    return ports

def get_uptime(started: str, running: bool) -> str:
    """Calculate human-readable uptime from container's start time.
    Args:
        started (str): ISO 8601 timestamp when the container started.
        running (bool): Whether the container is currently running.
    Returns:
        str: Uptime formatted as 'Xh Ym' or 'N/A' if not running.
    """

    if not running:
        return  'N/A'
    started_time = isoparse(started)
    now = datetime.now(timezone.utc)
    delta = now - started_time
    secs = int(delta.total_seconds())
    mins = (secs%3600)//60
    hours = secs//3600
    return f'{hours}h {mins}m'

def get_volumes_and_networks(attrs: dict) -> tuple:
    """Extract volume mounts and connected networks from container attributes.
    Args:
        attrs (dict): The container's full attribute dictionary.   
    Returns:
        tuple: A list of volume mappings and a list of network names.
    """

    volumes = [
        f"{mount['Source']} → {mount['Destination']} ({'rw' if mount.get('RW') else 'ro'})"
        for mount in attrs.get('Mounts', [])
    ]
    networks = list(attrs['NetworkSettings']['Networks'].keys())
    return volumes, networks

def create_docker_dict() -> dict:
    """Create a dictionary of Docker containers with their details.
    """
    global CONTAINER_DICT
    containers = client.containers.list(all=True)
    CONTAINER_DICT.clear()
    for container in containers:
        attrs = container.attrs
        #cpu, mem = get_subprocess(container.name)
        ports = get_ports(attrs)
        uptime =  get_uptime(attrs['State']['StartedAt'], attrs['State']['Running'])
        volumes, networks = get_volumes_and_networks(attrs)
        cmd = ' '.join(attrs['Config'].get('Cmd') or []) or str(attrs['Config'].get('Entrypoint', ''))
        CONTAINER_DICT[container.name] ={
            "status": container.status,
            #"cpu": cpu,
            #"memory": mem,
            "log_path": f'docker logs {container.name}',
            "container_id": container.short_id,
            "image": attrs['Config']['Image'],
            "ports": ports,
            "volumes": volumes,
            "networks": networks,
            "started_at": attrs['State']['StartedAt'],
            "uptime": uptime,
            "command": cmd
        }
    return CONTAINER_DICT


def get_filtered_logs(container_name: str) -> str:
    """Fetch the entire logs from a container and filter all lines by keyword.
     Args:
        container_name (str): Docker container name.
        filter_keyword (str): Keyword to filter for (e.g., 'ERROR').
    Returns:
        str: Filtered log lines.
    """

    global CONTAINER_DICT
    container = CONTAINER_DICT.get(container_name)

    if container is None:
        create_docker_dict()
        container = CONTAINER_DICT.get(container_name)

    if not container:
        return 'Container Not Found.'

    try:
        container_obj = client.containers.get(container['container_id'])
        logs = container_obj.logs(stdout=True, stderr=True, timestamps=True)
        logs = logs.decode(errors="ignore").splitlines()
    except Exception as e:
        return f'Failed to fetch logs: {e}'

    try:
        with open(Path(__file__).parent / "config.yml", "r") as f:
            config = yaml.safe_load(f)
        alert_keywords = config.get("alert", {}).get("keywords", [])
    except Exception as e:
        return f'Failed to load config: {e}'

    filtered_logs = [line for line in logs if any(k in line for k in alert_keywords)]

    return '\n'.join(filtered_logs)


def fetch_logs_background(container_name: str, tail: int = 1000, refresh_interval: int = 60):
    """Background task to keep container logs fresh."""
    while True:
        try:
            container = client.containers.get(container_name)
            logs = container.logs(
                tail=tail,
                timestamps=True,
                stdout=True,
                stderr=True,
                follow=False
            ).decode()
            LOG_CACHE[container_name] = logs
        except Exception as e:
            print(f"[LogForge] Error fetching logs for {container_name}: {e}")
            LOG_CACHE[container_name] = ["[Error fetching logs]"]

        time.sleep(refresh_interval)