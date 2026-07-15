"""Agent-authored, deterministically verifiable animation."""

from typing import Final

from anima.rng import RNGStream, SeededRNG

__version__: Final = "0.0.0.dev0"

__all__ = ["RNGStream", "SeededRNG", "__version__"]
