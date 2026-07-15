"""Deterministic, keyed pseudo-random number generation for anima-ai.

``SeededRNG`` is the single source of per-node randomness for a rendered
project. Every scene node that needs randomness (wobble jitter, paint
texture noise, stroke variation, ...) asks the project's ``SeededRNG`` for a
stream keyed by its own ``node_id``. Two runs with the same
``(project_seed, node_id)`` pair MUST produce byte-for-byte identical
sampled sequences -- this is a hard requirement of the verify-without-
watching design: renders must be reproducible across machines, processes,
and ``PYTHONHASHSEED`` values.

Design
------
Key derivation is domain-separated and independent of Python's ``hash()``
(which is salted per-process unless ``PYTHONHASHSEED`` is pinned, and is
therefore unsuitable for anything that must reproduce across processes).
The key material for a stream is the byte string::

    b"anima-ai/rng/v1" + b"\\x00" + str(project_seed).encode("ascii")
    + b"\\x00" + node_id.encode("utf-8")

That key material is hashed with BLAKE2b (stdlib, deterministic,
platform-independent, unaffected by ``PYTHONHASHSEED``) at an 8-byte digest
size. The resulting 8 bytes are interpreted as a big-endian unsigned 64-bit
integer and used as the seed for a hand-rolled SplitMix64 generator.

SplitMix64 (public-domain algorithm by Sebastiano Vigna) is used verbatim,
in pure Python, with no dependency on :mod:`random`, :mod:`numpy`, wall
clock, OS entropy, or hash randomization::

    state = (state + 0x9E3779B97F4A7C15) mod 2**64
    z = state
    z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9
    z = (z ^ (z >> 27)) * 0x94D049BB133111EB
    z = z ^ (z >> 31)
    return z

Each call to ``RNGStream.random()`` advances the generator's internal state
by exactly one SplitMix64 step and turns the resulting 64-bit draw into a
float in ``[0.0, 1.0)`` by taking the top 53 bits (``draw >> 11``) and
dividing by ``2**53``, matching the standard technique used by
:meth:`random.Random.random` for uniform doubles with full mantissa
precision.

Known-answer vector (v1)
-------------------------
For ``project_seed=0`` and ``node_id="known-answer-vector"``, the first
three draws from ``RNGStream.random()`` are::

    0.9222275522108391
    0.17247446487553053
    0.9236814412570742

This vector is asserted verbatim in ``tests/test_seeded_rng.py`` and must
never change for a given ``(project_seed, node_id)`` pair -- any change to
the derivation or generator below is a breaking change to every previously
rendered project.
"""

from __future__ import annotations

import hashlib
from typing import Final

_MASK64: Final[int] = (1 << 64) - 1
_GOLDEN_GAMMA: Final[int] = 0x9E3779B97F4A7C15
_MIX_MULTIPLIER_1: Final[int] = 0xBF58476D1CE4E5B9
_MIX_MULTIPLIER_2: Final[int] = 0x94D049BB133111EB

_DOMAIN_TAG: Final[bytes] = b"anima-ai/rng/v1"
_SEED_DIGEST_SIZE: Final[int] = 8

_FLOAT_MANTISSA_BITS: Final[int] = 53
_FLOAT_DIVISOR: Final[float] = float(1 << _FLOAT_MANTISSA_BITS)


def _splitmix64_step(state: int) -> tuple[int, int]:
    """Advance one SplitMix64 step, returning ``(next_state, output)``."""
    state = (state + _GOLDEN_GAMMA) & _MASK64
    z = state
    z = ((z ^ (z >> 30)) * _MIX_MULTIPLIER_1) & _MASK64
    z = ((z ^ (z >> 27)) * _MIX_MULTIPLIER_2) & _MASK64
    z = z ^ (z >> 31)
    return state, z


def _derive_seed(project_seed: int, node_id: str) -> int:
    key_material = (
        _DOMAIN_TAG
        + b"\x00"
        + str(project_seed).encode("ascii")
        + b"\x00"
        + node_id.encode("utf-8")
    )
    digest = hashlib.blake2b(key_material, digest_size=_SEED_DIGEST_SIZE).digest()
    return int.from_bytes(digest, byteorder="big", signed=False)


def _validate_project_seed(project_seed: int) -> None:
    if type(project_seed) is not int:
        raise TypeError(
            f"project_seed must be an int, got {type(project_seed).__name__!r}"
        )
    if project_seed < 0:
        raise ValueError(f"project_seed must be non-negative, got {project_seed!r}")


def _validate_node_id(node_id: str) -> None:
    if type(node_id) is not str:
        raise TypeError(f"node_id must be a str, got {type(node_id).__name__!r}")
    if node_id == "":
        raise ValueError("node_id must be a non-empty string")


class RNGStream:
    """A single deterministic stream of pseudo-randomness for one node.

    Instances are created exclusively via :meth:`SeededRNG.for_node`. Each
    instance owns its own SplitMix64 state; calling methods on one stream
    never affects any other stream, including a stream created for the same
    ``node_id`` on a later call (that later stream restarts the sequence
    from the same deterministic seed).
    """

    __slots__ = ("_state",)

    def __init__(self, initial_state: int) -> None:
        self._state: int = initial_state & _MASK64

    def _next_u64(self) -> int:
        self._state, output = _splitmix64_step(self._state)
        return output

    def random(self) -> float:
        """Return a deterministic float in ``[0.0, 1.0)``."""
        draw = self._next_u64()
        top_bits = draw >> (64 - _FLOAT_MANTISSA_BITS)
        return top_bits / _FLOAT_DIVISOR

    def uniform(self, low: float, high: float) -> float:
        """Return a deterministic float in ``[low, high)``.

        Raises:
            ValueError: if ``low`` or ``high`` is not finite, if
                ``low > high``, or if ``high - low`` overflows to a
                non-finite span (e.g. ``low=-sys.float_info.max``,
                ``high=sys.float_info.max``).
        """
        if not _is_finite(low):
            raise ValueError(f"low must be finite, got {low!r}")
        if not _is_finite(high):
            raise ValueError(f"high must be finite, got {high!r}")
        if low > high:
            raise ValueError(f"low ({low!r}) must be <= high ({high!r})")
        span = high - low
        if not _is_finite(span):
            raise ValueError(
                f"high - low must be finite, got low={low!r}, high={high!r} "
                f"(span={span!r})"
            )
        return low + span * self.random()


def _is_finite(value: float) -> bool:
    return value == value and value not in (float("inf"), float("-inf"))


class SeededRNG:
    """Deterministic, per-project source of independent per-node RNG streams.

    Example:
        >>> rng = SeededRNG(42)
        >>> stream = rng.for_node("intro/title-card")
        >>> 0.0 <= stream.random() < 1.0
        True
    """

    __slots__ = ("_project_seed",)

    def __init__(self, project_seed: int) -> None:
        _validate_project_seed(project_seed)
        self._project_seed: int = project_seed

    @property
    def project_seed(self) -> int:
        return self._project_seed

    def for_node(self, node_id: str) -> RNGStream:
        """Return a fresh, independent :class:`RNGStream` for ``node_id``.

        Calling this repeatedly with the same ``node_id`` always returns a
        new stream object whose sequence restarts deterministically from
        the same seed -- no state is shared across calls or across other
        node IDs.
        """
        _validate_node_id(node_id)
        seed = _derive_seed(self._project_seed, node_id)
        return RNGStream(seed)


__all__ = ["RNGStream", "SeededRNG"]
