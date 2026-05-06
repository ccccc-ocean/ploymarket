from __future__ import annotations

import json
from http.client import IncompleteRead, RemoteDisconnected
from time import sleep
from typing import Any
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class HttpError(RuntimeError):
    pass


def get_json(base_url: str, path: str, params: dict[str, Any], timeout: int) -> Any:
    query = urlencode({key: value for key, value in params.items() if value is not None})
    url = f"{base_url.rstrip('/')}/{path.lstrip('/')}"
    if query:
        url = f"{url}?{query}"

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
            with urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except (IncompleteRead, RemoteDisconnected, URLError, TimeoutError) as exc:
            last_error = exc
            sleep(0.5 * (attempt + 1))
        except Exception as exc:
            raise HttpError(f"GET {url} failed: {exc}") from exc
    raise HttpError(f"GET {url} failed after retries: {last_error}") from last_error
