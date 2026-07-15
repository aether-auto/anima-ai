from __future__ import annotations

import os
import subprocess
import sys
import textwrap

import pytest
from hypothesis import given
from hypothesis import strategies as st

from anima.rng import RNGStream, SeededRNG

# --- Known-answer vector (v1) -----------------------------------------------
# See src/anima/rng.py module docstring: any change to these values is a
# breaking change to every previously rendered project.
_KNOWN_ANSWER_SEED = 0
_KNOWN_ANSWER_NODE_ID = "known-answer-vector"
_KNOWN_ANSWER_SEQUENCE = (
    0.9222275522108391,
    0.17247446487553053,
    0.9236814412570742,
)


def test_known_answer_vector_v1() -> None:
    rng = SeededRNG(_KNOWN_ANSWER_SEED)
    stream = rng.for_node(_KNOWN_ANSWER_NODE_ID)
    sampled = tuple(stream.random() for _ in _KNOWN_ANSWER_SEQUENCE)
    assert sampled == _KNOWN_ANSWER_SEQUENCE


# --- Basic unit tests --------------------------------------------------------


def test_for_node_returns_rng_stream_instance() -> None:
    rng = SeededRNG(1)
    assert isinstance(rng.for_node("a"), RNGStream)


def test_recreating_a_stream_restarts_the_sequence() -> None:
    rng = SeededRNG(7)
    first = rng.for_node("node-a")
    first_sequence = [first.random() for _ in range(5)]

    second = rng.for_node("node-a")
    second_sequence = [second.random() for _ in range(5)]

    assert first_sequence == second_sequence


def test_for_node_returns_fresh_independent_stream_objects() -> None:
    rng = SeededRNG(7)
    first = rng.for_node("node-a")
    second = rng.for_node("node-a")
    assert first is not second


def test_distinct_node_ids_produce_distinct_prefixes() -> None:
    rng = SeededRNG(7)
    a = [rng.for_node("node-a").random() for _ in range(8)]
    b = [rng.for_node("node-b").random() for _ in range(8)]
    assert a != b


def test_advancing_one_stream_does_not_affect_a_sibling_stream() -> None:
    rng = SeededRNG(7)
    a = rng.for_node("node-a")
    b = rng.for_node("node-a")

    # Advance `a` several times; `b` (a fresh stream for the same node_id)
    # must still start from the beginning of the deterministic sequence.
    for _ in range(10):
        a.random()

    reference = rng.for_node("node-a")
    assert b.random() == reference.random()


def test_random_values_are_within_unit_interval() -> None:
    stream = SeededRNG(123).for_node("bounds-check")
    for _ in range(2000):
        value = stream.random()
        assert 0.0 <= value < 1.0


def test_uniform_values_stay_within_requested_range() -> None:
    stream = SeededRNG(123).for_node("uniform-bounds-check")
    for _ in range(2000):
        value = stream.uniform(-5.0, 10.0)
        assert -5.0 <= value < 10.0


def test_uniform_rejects_low_greater_than_high() -> None:
    stream = SeededRNG(1).for_node("a")
    with pytest.raises(ValueError, match="low"):
        stream.uniform(1.0, 0.0)


@pytest.mark.parametrize("bad", [float("inf"), float("-inf"), float("nan")])
def test_uniform_rejects_non_finite_bounds(bad: float) -> None:
    stream = SeededRNG(1).for_node("a")
    with pytest.raises(ValueError):
        stream.uniform(bad, 1.0)
    with pytest.raises(ValueError):
        stream.uniform(0.0, bad)


def test_uniform_rejects_bounds_whose_span_overflows_to_non_finite() -> None:
    import sys

    stream = SeededRNG(1).for_node("a")
    with pytest.raises(ValueError, match="span"):
        stream.uniform(-sys.float_info.max, sys.float_info.max)


@pytest.mark.parametrize("bad_seed", [-1, -100, 1.5, "0", True, False, None])
def test_seeded_rng_rejects_invalid_project_seed(bad_seed: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        SeededRNG(bad_seed)  # type: ignore[arg-type]


@pytest.mark.parametrize("bad_node_id", ["", 1, 1.5, None, ()])
def test_for_node_rejects_invalid_node_id(bad_node_id: object) -> None:
    rng = SeededRNG(1)
    with pytest.raises((TypeError, ValueError)):
        rng.for_node(bad_node_id)  # type: ignore[arg-type]


# --- Hypothesis / property-based tests ---------------------------------------


@given(
    project_seed=st.integers(min_value=0, max_value=2**63 - 1),
    node_id=st.text(min_size=1, max_size=64),
)
def test_hypothesis_identical_keys_yield_identical_sequences(
    project_seed: int, node_id: str
) -> None:
    rng = SeededRNG(project_seed)
    first = rng.for_node(node_id)
    second = rng.for_node(node_id)
    assert [first.random() for _ in range(20)] == [second.random() for _ in range(20)]


@given(
    project_seed=st.integers(min_value=0, max_value=2**63 - 1),
    low=st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False),
    span=st.floats(min_value=0.0, max_value=1e6, allow_nan=False, allow_infinity=False),
    node_id=st.text(min_size=1, max_size=32),
)
def test_hypothesis_uniform_samples_remain_in_range(
    project_seed: int, low: float, span: float, node_id: str
) -> None:
    high = low + span
    stream = SeededRNG(project_seed).for_node(node_id)
    for _ in range(10):
        value = stream.uniform(low, high)
        assert low <= value <= high


@given(
    project_seed=st.integers(min_value=0, max_value=2**63 - 1),
    node_id_a=st.text(min_size=1, max_size=32),
    node_id_b=st.text(min_size=1, max_size=32),
)
def test_hypothesis_distinct_node_ids_do_not_couple_state(
    project_seed: int, node_id_a: str, node_id_b: str
) -> None:
    if node_id_a == node_id_b:
        return
    rng = SeededRNG(project_seed)
    a_stream = rng.for_node(node_id_a)
    b_stream = rng.for_node(node_id_b)

    a_first = a_stream.random()
    b_values = [b_stream.random() for _ in range(5)]
    a_rest = [a_stream.random() for _ in range(5)]

    # Advancing `b_stream` between `a_stream` draws must not perturb `a_stream`'s
    # sequence: it should match a freshly recreated, uninterrupted `a` stream.
    reference = rng.for_node(node_id_a)
    reference_sequence = [reference.random() for _ in range(6)]
    assert [a_first, *a_rest] == reference_sequence
    assert len(b_values) == 5


# --- Cross-process / hash-seed independence ---------------------------------


def test_seeded_rng_is_cross_process_and_hash_seed_stable() -> None:
    script = textwrap.dedent(
        """
        import sys
        sys.path.insert(0, {src_path!r})
        from anima.rng import SeededRNG

        rng = SeededRNG(4242)
        stream = rng.for_node("cross-process-check")
        print(",".join(repr(stream.random()) for _ in range(5)))
        """
    ).format(src_path="src")

    outputs = []
    for hash_seed in ("0", "1", "1337"):
        child_env = dict(os.environ)
        child_env["PYTHONHASHSEED"] = hash_seed
        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=".",
            env=child_env,
            capture_output=True,
            text=True,
            check=True,
        )
        outputs.append(result.stdout.strip())

    assert len(set(outputs)) == 1
    assert outputs[0] != ""
