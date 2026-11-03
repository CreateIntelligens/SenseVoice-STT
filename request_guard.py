"""Protect the shared GPU host from requests that need too much memory."""

import os

from fastapi import HTTPException

# The encoder's attention grows with the square of the audio length: 34 minutes needed at least 36.6 GiB and took the
# whole host down, while 12 minutes works. 15 minutes is an estimated 7 GiB.
DEFAULT_MAX_AUDIO_SECONDS = 900.0


def max_audio_seconds() -> float:
    return float(os.getenv("MAX_AUDIO_SECONDS", DEFAULT_MAX_AUDIO_SECONDS))


def reject_if_too_long(total_seconds: float, limit: float) -> None:
    """Refuse a request before inference. Files in one request are padded into a batch, so their lengths add up."""
    if total_seconds > limit:
        raise HTTPException(
            status_code=413,
            detail=f"Audio is {total_seconds:.0f} seconds; this service accepts up to {limit:.0f}. Split it first.",
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
