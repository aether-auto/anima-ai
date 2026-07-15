from __future__ import annotations

import socket
from collections.abc import Iterator
from typing import NoReturn

import pytest

_SOCKET_IO_METHODS = (
    "accept",
    "bind",
    "connect",
    "connect_ex",
    "listen",
    "recv",
    "recv_into",
    "recvfrom",
    "recvfrom_into",
    "recvmsg",
    "recvmsg_into",
    "send",
    "sendall",
    "sendfile",
    "sendmsg",
    "sendto",
    "shutdown",
)

_SOCKET_MODULE_IO = (
    "create_connection",
    "create_server",
    "getaddrinfo",
    "gethostbyaddr",
    "gethostbyname",
    "gethostbyname_ex",
    "getnameinfo",
    "socketpair",
)


def _deny_network_io(*_args: object, **_kwargs: object) -> NoReturn:
    raise RuntimeError("network access blocked during tests")


@pytest.fixture(autouse=True)
def _block_socket_io(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    for method_name in _SOCKET_IO_METHODS:
        if hasattr(socket.socket, method_name):
            monkeypatch.setattr(socket.socket, method_name, _deny_network_io)

    for function_name in _SOCKET_MODULE_IO:
        if hasattr(socket, function_name):
            monkeypatch.setattr(socket, function_name, _deny_network_io)

    yield
