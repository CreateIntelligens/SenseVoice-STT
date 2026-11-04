import contextlib
import gc
import weakref

from io import BytesIO
from unittest import mock

import numpy as np
import pytest
import soundfile as sf
from fastapi import HTTPException

import request_guard
from request_guard import (
    DEFAULT_MAX_AUDIO_SECONDS,
    DEFAULT_MAX_UPLOAD_MB,
    InferenceFailure,
    max_audio_seconds,
    max_upload_bytes,
    reject_if_too_long,
    reject_mixed_sample_rates,
    total_audio_seconds,
    upload_too_large,
)


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


def wav_bytes(seconds, rate=16000):
    buffer = BytesIO()
    sf.write(buffer, np.zeros(int(seconds * rate), dtype="float32"), rate, format="WAV", subtype="PCM_16")
    return buffer.getvalue()


def test_total_seconds_add_up_across_files_and_rates():
    assert total_audio_seconds([wav_bytes(2), wav_bytes(3, rate=44100)]) == pytest.approx(5.0)


def test_length_is_read_without_decoding():
    with mock.patch.object(request_guard.sf, "read") as read:
        total_audio_seconds([wav_bytes(1)])
    read.assert_not_called()


@pytest.mark.parametrize("bad", [b"", b"RIFF" + bytes(4096), b"not audio"])
def test_unreadable_audio_is_a_client_error_naming_the_file(bad):
    with pytest.raises(HTTPException) as error:
        total_audio_seconds([wav_bytes(1), bad])
    assert error.value.status_code == 400
    assert "File 2" in error.value.detail


@pytest.mark.parametrize("frames", [0, 1])
def test_audio_too_short_for_the_frontend_is_a_client_error_naming_the_file(frames):
    with pytest.raises(HTTPException) as error:
        total_audio_seconds([wav_bytes(1), wav_bytes(frames / 16000)])
    assert error.value.status_code == 400
    assert "File 2" in error.value.detail


def test_shortest_audio_the_frontend_accepts_passes():
    assert total_audio_seconds([wav_bytes(2 / 16000)]) == pytest.approx(2 / 16000)


@pytest.mark.parametrize("rates", [(16000, 8000), (8000, 16000), (16000, 16000, 44100)])
def test_mixed_sample_rates_are_a_client_error_listing_them(rates):
    with pytest.raises(HTTPException) as error:
        reject_mixed_sample_rates([wav_bytes(1, rate=rate) for rate in rates])
    assert error.value.status_code == 400
    for rate in rates:
        assert str(rate) in error.value.detail


@pytest.mark.parametrize("rates", [(16000,), (44100,), (8000, 8000)])
def test_files_sharing_one_sample_rate_pass(rates):
    reject_mixed_sample_rates([wav_bytes(1, rate=rate) for rate in rates])


def test_sample_rates_are_read_without_decoding():
    with mock.patch.object(request_guard.sf, "read") as read:
        reject_mixed_sample_rates([wav_bytes(1)])
    read.assert_not_called()


@pytest.mark.parametrize(
    "header, expected",
    [("1000", False), ("1001", True), (None, False), ("not-a-number", False)],
)
def test_upload_limit_uses_the_declared_length(header, expected):
    assert upload_too_large(header, 1000) is expected


def test_upload_limit_comes_from_the_environment(monkeypatch):
    monkeypatch.delenv("MAX_UPLOAD_MB", raising=False)
    assert max_upload_bytes() == int(DEFAULT_MAX_UPLOAD_MB * 1024 * 1024)
    monkeypatch.setenv("MAX_UPLOAD_MB", "1")
    assert max_upload_bytes() == 1048576
