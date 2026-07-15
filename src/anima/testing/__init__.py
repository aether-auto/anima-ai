"""Deterministic golden-image test harness for anima renderer primitives.

This package is agent-facing test infrastructure: a pure-numpy PNG comparator
(:mod:`anima.testing.pixelcompare`), a manifest-backed baseline registry
(:mod:`anima.testing.registry`), a ``generate``/``compare``/``update`` CLI
(:mod:`anima.testing.goldens`), and the committed fixtures
(:mod:`anima.testing.fixtures`). Canonical baselines are blessed only inside
the pinned golden container; the host can compare but never bless.
"""

from __future__ import annotations
