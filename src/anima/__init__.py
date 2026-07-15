"""Agent-authored, deterministically verifiable animation."""

from anima._version import __version__
from anima.rng import RNGStream, SeededRNG

__all__ = ["RNGStream", "SeededRNG", "__version__"]
