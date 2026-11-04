"""Protect the shared GPU host from requests that need too much memory."""

import os
from io import BytesIO
from typing import List, Optional

import soundfile as sf
from fastapi import HTTPException

# The encoder's attention grows with the square of the audio length: 34 minutes needed at least 36.6 GiB and took the
# whole host down, while 12 minutes works. 15 minutes is an estimated 7 GiB.
DEFAULT_MAX_AUDIO_SECONDS = 900.0
# 15 minutes of 96 kHz stereo 16-bit WAV is about 330 MB; FastAPI holds the whole body in memory before the handler runs.
DEFAULT_MAX_UPLOAD_MB = 512.0
# The fbank frontend asserts at least 2 samples per window and turns anything shorter into a generic 500.
MIN_AUDIO_FRAMES = 2


def max_audio_seconds() -> float:
    return float(os.getenv("MAX_AUDIO_SECONDS", DEFAULT_MAX_AUDIO_SECONDS))


def max_upload_bytes() -> int:
    return int(float(os.getenv("MAX_UPLOAD_MB", DEFAULT_MAX_UPLOAD_MB)) * 1024 * 1024)


def upload_too_large(content_length: Optional[str], limit: int) -> bool:
    """Decide from the header, before the body is read. Chunked uploads send no length and are not covered."""
    return content_length is not None and content_length.isdigit() and int(content_length) > limit


def total_audio_seconds(files: List[bytes]) -> float:
    """Read each file's length from its header, without decoding. Unreadable or too-short audio is the caller's error."""
    total = 0.0
    for index, file in enumerate(files):
        try:
            info = sf.info(BytesIO(file))
        except sf.LibsndfileError:
            raise HTTPException(status_code=400, detail=f"File {index + 1} is not readable audio.") from None
        if info.frames < MIN_AUDIO_FRAMES:
            raise HTTPException(status_code=400, detail=f"File {index + 1} has no usable audio.")
        total += info.duration
    return total


def reject_if_too_long(total_seconds: float, limit: float) -> None:
    """Refuse a request before inference. Files in one request are padded into a batch, so their lengths add up."""
    if total_seconds > limit:
        raise HTTPException(
            status_code=413,
            detail=f"Audio is {total_seconds:.0f} seconds; this service accepts up to {limit:.0f}. Split it first.",
        )


def reject_mixed_sample_rates(files: List[bytes]) -> None:
    """Refuse a batch with several rates. The model resamples every file from one rate, so speech can vanish silently."""
    rates = sorted({sf.info(BytesIO(file)).samplerate for file in files})
    if len(rates) > 1:
        raise HTTPException(
            status_code=400,
            detail=f"All files in one request must share a sample rate; got {', '.join(map(str, rates))} Hz.",
        )


class InferenceFailure:
    """Drop a failed request's exception before the GPU cache is emptied.

    The traceback keeps the failed forward pass's tensors alive, so emptying the cache while the exception propagates
    frees nothing and the memory stays reserved. Use as the inner context, then call ``raise_if_failed`` afterwards.
    """

    def __init__(self):
        self.failed = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None or issubclass(exc_type, HTTPException):
            return False
        self.failed = True
        return True

    def raise_if_failed(self) -> None:
        if self.failed:
            raise HTTPException(status_code=500, detail="Inference failed; see the server log.")
