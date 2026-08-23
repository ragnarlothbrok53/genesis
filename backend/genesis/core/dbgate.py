from genesis.core.config import DBGATE
from genesis.core.net import tcp_ok


def check() -> bool:
    return tcp_ok(DBGATE["host"], DBGATE["port"])
