import socket
import time
from src.monitors import BaseMonitor, MonitorResult, register_monitor


@register_monitor
class TcpPingMonitor(BaseMonitor):
    type_id = "tcp_ping"
    name = "TCP Ping"
    description = "Check if a TCP port is open and accepting connections"
    config_schema = {
        "host": {"type": "string", "label": "Hostname or IP", "required": True},
        "port": {"type": "number", "label": "Port", "required": True},
        "timeout": {"type": "number", "label": "Timeout (seconds)", "default": 5, "required": False},
    }

    def check(self) -> MonitorResult:
        host = self.config.get("host", "")
        port = int(self.config.get("port", 0))
        timeout = int(self.config.get("timeout", 5))

        if not host or not port:
            return MonitorResult(status="error", error="Host and port required")

        try:
            start = time.time()
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((host, port))
            elapsed = (time.time() - start) * 1000
            sock.close()

            if result == 0:
                return MonitorResult(
                    status="up",
                    response_time_ms=round(elapsed, 1),
                    response_summary=f"Port {port} open"
                )
            else:
                return MonitorResult(
                    status="down",
                    response_time_ms=round(elapsed, 1),
                    error=f"Port {port} closed (error {result})"
                )
        except socket.timeout:
            return MonitorResult(status="down", error=f"Connection to {host}:{port} timed out")
        except socket.gaierror:
            return MonitorResult(status="error", error=f"Could not resolve hostname: {host}")
        except Exception as e:
            return MonitorResult(status="error", error=str(e))
