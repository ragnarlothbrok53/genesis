import socket
from urllib.parse import urlparse


def tcp_ok(host: str, port: int, timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def host_port(address: str, default_port: int) -> tuple[str, int]:
    if "://" in address:
        parsed = urlparse(address)
        return parsed.hostname or "127.0.0.1", parsed.port or default_port
    host, _, port = address.partition(":")
    return host or "127.0.0.1", int(port) if port else default_port
