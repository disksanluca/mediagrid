"""Keep Windows awake only while a local encoder is actively rendering."""

import ctypes
import logging
import os
from collections.abc import Iterator
from contextlib import contextmanager

logger = logging.getLogger(__name__)
ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001


def _set_thread_execution_state(flags: int) -> int:
    api = ctypes.windll.kernel32.SetThreadExecutionState
    api.argtypes = [ctypes.c_uint32]
    api.restype = ctypes.c_uint32
    return int(api(flags))


@contextmanager
def keep_system_awake() -> Iterator[None]:
    """Prevent automatic idle sleep during Remotion; respect manual sleep."""
    acquired = False
    if os.name == "nt":
        try:
            acquired = bool(_set_thread_execution_state(
                ES_CONTINUOUS | ES_SYSTEM_REQUIRED
            ))
            if not acquired:
                logger.warning("Windows did not accept the active render power request")
        except OSError:
            logger.warning("Windows render power request failed", exc_info=True)
    try:
        yield
    finally:
        if acquired:
            try:
                if not _set_thread_execution_state(ES_CONTINUOUS):
                    logger.warning("Windows did not clear the render power request")
            except OSError:
                logger.warning("Windows render power request could not be cleared",
                               exc_info=True)
