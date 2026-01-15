"""Time helpers."""

import time


def utc_now_ms() -> int:
    return int(time.time() * 1000)


def utc_now_s() -> int:
    return int(time.time())
