from __future__ import annotations

import socket

import pytest


def test_socket_guard_blocks_network_io() -> None:
    with socket.socket() as probe:
        with pytest.raises(RuntimeError, match="network access blocked during tests"):
            probe.connect(("127.0.0.1", 9))


def test_socket_guard_allows_network_free_work() -> None:
    assert sum((2, 3, 5, 7)) == 17
