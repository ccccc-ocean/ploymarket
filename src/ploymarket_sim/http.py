from __future__ import annotations

import json
import signal
import threading
from contextlib import contextmanager
from http.client import IncompleteRead, RemoteDisconnected
from time import sleep
from typing import Any
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .cache import JsonCache


class HttpError(RuntimeError):
    pass


def get_json(base_url: str, path: str, params: dict[str, Any], timeout: int, cache: JsonCache | None = None) -> Any:
    query = urlencode({key: value for key, value in params.items() if value is not None})
    url = f"{base_url.rstrip('/')}/{path.lstrip('/')}"
    if query:
        url = f"{url}?{query}"

    if cache:
        cached = cache.get_fresh(url)
        if cached is not None:
            return cached

    request = Request(
        url,
        headers={
            "User-Agent": "ploymarket-research/0.1",
            "Accept": "application/json",
            "Accept-Encoding": "identity",
            "Connection": "close",
        },
    )
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            with _request_deadline(timeout + 2):
                with urlopen(request, timeout=timeout) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                    if cache:
                        cache.set(url, payload)
                    return payload
        except (IncompleteRead, RemoteDisconnected, URLError, TimeoutError) as exc:
            last_error = exc
            sleep(0.5 * (attempt + 1))
        except Exception as exc:
            raise HttpError(f"GET {url} failed: {exc}") from exc
    if cache and cache.policy.stale_if_error:
        stale = cache.get_stale(url)
        if stale is not None:
            return stale
    raise HttpError(f"GET {url} failed after retries: {last_error}") from last_error


@contextmanager
def _request_deadline(seconds: int):
    if threading.current_thread() is not threading.main_thread():
        yield
        return

    previous_handler = signal.getsignal(signal.SIGALRM)
    previous_timer = signal.setitimer(signal.ITIMER_REAL, 0)

    def _raise_timeout(_signum, _frame):
        raise TimeoutError(f"request exceeded {seconds}s deadline")

    signal.signal(signal.SIGALRM, _raise_timeout)
    signal.setitimer(signal.ITIMER_REAL, max(1, seconds))
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, previous_timer[0], previous_timer[1])
        signal.signal(signal.SIGALRM, previous_handler)
