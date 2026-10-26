"""Cliente HTTP "educado": se identifica, espera entre peticiones y reintenta
con calma ante errores temporales."""
from __future__ import annotations

import time

import requests

USER_AGENT = "CorteHoyBot/1.0 (+https://github.com/arhka5/corte-hoy)"
TIMEOUT = 60
RETRY_STATUS = {429, 500, 502, 503, 504}


class Client:
    def __init__(self, delay: float = 1.0, retries: int = 3):
        self.delay = delay
        self.retries = retries
        self._last = 0.0
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "es-PE,es;q=0.9"})
        self.requests = 0

    def request(self, method: str, url: str, **kwargs) -> requests.Response:
        for attempt in range(self.retries + 1):
            espera = self.delay - (time.monotonic() - self._last)
            if espera > 0:
                time.sleep(espera)
            self._last = time.monotonic()
            self.requests += 1
            try:
                r = self.session.request(method, url, timeout=TIMEOUT, **kwargs)
            except (requests.ConnectionError, requests.Timeout):
                if attempt == self.retries:
                    raise
                time.sleep(10 * (attempt + 1))
                continue
            if r.status_code in RETRY_STATUS and attempt < self.retries:
                time.sleep(10 * (attempt + 1))
                continue
            r.raise_for_status()
            return r
        raise RuntimeError("inalcanzable")
