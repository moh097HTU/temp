"""
MAVProxy command builder.

Builds command line for starting MAVProxy with correct configuration.
"""

from dataclasses import dataclass, field
from typing import List


@dataclass
class MavproxyConfig:
    """MAVProxy configuration."""
    # Serial master
    serial_port: str = "/dev/ttyTHS1"  # Jetson UART
    baudrate: int = 57600
    
    # UDP outputs
    local_port: int = 14551  # For Jetson apps
    gcs_ip: str = "192.168.1.100"
    gcs_port: int = 14550
    
    # Options
    daemon: bool = True
    console: bool = False
    logfile: str = "/var/log/mavproxy.log"
    
    # Additional outputs (optional)
    extra_outputs: List[str] = field(default_factory=list)


def build_mavproxy_command(config: MavproxyConfig) -> List[str]:
    """
    Build MAVProxy command line arguments.
    
    Args:
        config: MAVProxy configuration
        
    Returns:
        List of command line arguments
    """
    cmd = ["mavproxy.py"]
    
    # Serial master
    cmd.extend([
        f"--master={config.serial_port}",
        f"--baudrate={config.baudrate}"
    ])
    
    # Local UDP output for Jetson apps
    cmd.append(f"--out=udp:127.0.0.1:{config.local_port}")
    
    # GCS UDP output
    cmd.append(f"--out=udp:{config.gcs_ip}:{config.gcs_port}")
    
    # Extra outputs
    for output in config.extra_outputs:
        cmd.append(f"--out={output}")
    
    # Options
    if config.daemon:
        cmd.append("--daemon")
    
    if not config.console:
        cmd.append("--non-interactive")
    
    if config.logfile:
        cmd.append(f"--logfile={config.logfile}")
    
    return cmd


def build_mavproxy_shell_command(config: MavproxyConfig) -> str:
    """
    Build MAVProxy shell command as a single string.
    
    Args:
        config: MAVProxy configuration
        
    Returns:
        Shell command string
    """
    return " ".join(build_mavproxy_command(config))
