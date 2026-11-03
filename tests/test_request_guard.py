import contextlib
import gc
import weakref

import pytest
from fastapi import HTTPException

from request_guard import DEFAULT_MAX_AUDIO_SECONDS, InferenceFailure, max_audio_seconds, reject_if_too_long


class Tensor:
    """Stands in for the tensors a failed forward pass holds."""


def fail_with_live_tensor(refs):
    tensor = Tensor()
    refs.append(weakref.ref(tensor))
    raise RuntimeError("out of memory")


@contextlib.contextmanager
def record_alive_at_cleanup(refs, seen):
    try:
        yield
    finally:
        gc.collect()
        seen.append(refs[0]() is not None)


def test_failed_tensors_are_gone_before_cleanup():
    refs, seen = [], []
    guard = InferenceFailure()
    with record_alive_at_cleanup(refs, seen), guard:
        fail_with_live_tensor(refs)
    assert seen == [False]
    with pytest.raises(HTTPException) as error:
        guard.raise_if_failed()
    assert error.value.status_code == 500
    assert "out of memory" not in error.value.detail


def test_without_the_guard_cleanup_runs_while_tensors_are_alive():
    """Documents the bug: this is why 19 GB stayed reserved after an out-of-memory request."""
    refs, seen = [], []
    with pytest.raises(RuntimeError):
        with record_alive_at_cleanup(refs, seen):
            fail_with_live_tensor(refs)
    assert seen == [True]


def test_guard_leaves_success_and_http_errors_alone():
    guard = InferenceFailure()
    with guard:
        pass
    guard.raise_if_failed()

    guard = InferenceFailure()
    with pytest.raises(HTTPException) as error:
        with guard:
            raise HTTPException(status_code=413)
    assert error.value.status_code == 413
    guard.raise_if_failed()


@pytest.mark.parametrize("seconds", [0.0, 899.9, 900.0])
def test_audio_up_to_the_limit_is_accepted(seconds):
    reject_if_too_long(seconds, 900.0)


def test_audio_over_the_limit_is_rejected_with_413():
    with pytest.raises(HTTPException) as error:
        reject_if_too_long(2059.0, 900.0)
    assert error.value.status_code == 413
    assert "2059" in error.value.detail


def test_limit_comes_from_the_environment(monkeypatch):
    monkeypatch.delenv("MAX_AUDIO_SECONDS", raising=False)
    assert max_audio_seconds() == DEFAULT_MAX_AUDIO_SECONDS
    monkeypatch.setenv("MAX_AUDIO_SECONDS", "60")
    assert max_audio_seconds() == 60.0
