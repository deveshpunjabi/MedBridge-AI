"""
MedBridge AI - Global Rate Limiter
"""

import time
import threading
import click
from config import MODEL_NAME

# Determine minimum interval between API calls based on the model in use.
# Standard Flash has a 15 RPM limit (approx 4s interval), while Lite has 2 RPM (approx 31s interval).
if "lite" in MODEL_NAME.lower():
    MIN_CALL_INTERVAL: float = 31.0
else:
    MIN_CALL_INTERVAL: float = 4.0

_last_call_time: float = 0.0
_lock = threading.Lock()

def wait_for_rate_limit() -> None:
    """Block until enough time has elapsed since the last API call."""
    global _last_call_time

    with _lock:
        now = time.time()
        elapsed = now - _last_call_time

        if _last_call_time > 0 and elapsed < MIN_CALL_INTERVAL:
            wait_time = MIN_CALL_INTERVAL - elapsed
            click.echo(
                click.style(
                    f"   ⏳ Rate limiter: waiting {wait_time:.1f}s before next API call...",
                    fg="yellow",
                )
            )
            time.sleep(wait_time)

        _last_call_time = time.time()

def reset() -> None:
    """Reset the rate limiter."""
    global _last_call_time
    with _lock:
        _last_call_time = 0.0
