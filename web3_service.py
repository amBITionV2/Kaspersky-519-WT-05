from typing import Optional

from web3 import Web3

# Simple module-level holder
_w3: Optional[Web3] = None


def init_web3(rpc_url: str) -> Optional[Web3]:
    global _w3
    if not rpc_url:
        _w3 = None
        return _w3
    try:
        _w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={"timeout": 10}))
        # Attempt a lightweight call
        _ = _w3.is_connected()
        return _w3
    except Exception:
        _w3 = None
        return _w3


def get_web3() -> Optional[Web3]:
    return _w3
