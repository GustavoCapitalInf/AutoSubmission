"""Is the visual-OCR rung actually reachable? (Wave 3 / W3-5)

The visual rung is the **local** Unlimited-OCR server — our own GPU behind an
OpenAI-compatible endpoint (`local_ocr_server.py`, or a vLLM container serving
the same dialect). No paid vendor is involved and none may be: the ladder's
model client is built from `ocr.config.Settings` and nothing else.

A long batch must not discover that the server is down on document 1 of 3,506,
half-fill a cache, and leave an operator reading 3,505 identical failures. So
callers that intend to use the rung probe it **up front** and refuse to start.
This module is that probe and only that probe: it makes no OCR call, sends no
image, and costs no GPU time.

`GET /v1/models` is the cheapest liveness signal the endpoint offers — the
bundled local server answers it without touching the model, and every
OpenAI-compatible server implements it. Two facts come back:

* **reachable** — the request completed. A transport failure (connection
  refused, DNS, timeout, 5xx) is `available=False` with the exception CLASS
  name; the message is kept for the operator console only and never travels
  into telemetry (H-3 sensitivity invariant).
* **advertised model ids** — when the list is non-empty and does not contain
  the configured `OCR_MODEL`, every subsequent completion request would 404.
  That is a certain-failure configuration, so it is reported as such and the
  caller refuses; an endpoint that advertises nothing is not second-guessed.

The probe never raises. It returns a status object and lets the caller decide,
because "refuse to start" is a policy of the run, not of the OCR package.
"""
from __future__ import annotations

from dataclasses import dataclass, replace

#: Probing must not inherit ``OCR_TIMEOUT`` (120 s by default): the point of a
#: preflight is a fast, unambiguous answer, and a hung host should not stall the
#: operator for two minutes before the run refuses to start.
DEFAULT_PROBE_TIMEOUT = 10.0


@dataclass(frozen=True)
class VisualOcrStatus:
    """The result of one liveness probe. Never carries document content."""

    available: bool
    base_url: str
    model: str
    detail: str = ""
    advertised: tuple[str, ...] = ()
    error_type: str | None = None

    @property
    def model_advertised(self) -> bool:
        """False only when the endpoint named its models and ours is missing.

        An endpoint that advertises nothing gets the benefit of the doubt: an
        empty list is an absence of evidence, not evidence of absence, and
        refusing on it would block a working server.
        """
        return not self.advertised or self.model in self.advertised

    @property
    def usable(self) -> bool:
        return self.available and self.model_advertised

    def message(self) -> str:
        """One line an operator can act on. Console only, never telemetry."""
        if not self.available:
            return (
                f"visual-OCR server unreachable at {self.base_url} "
                f"({self.error_type}: {self.detail})"
            )
        if not self.model_advertised:
            return (
                f"visual-OCR server at {self.base_url} does not serve "
                f"{self.model!r}; it advertises: {', '.join(self.advertised)}"
            )
        return f"visual-OCR server ready at {self.base_url} ({self.model})"


def _advertised_ids(client) -> tuple[str, ...]:
    listing = client.models.list()
    data = getattr(listing, "data", None) or []
    return tuple(
        str(identifier)
        for identifier in (getattr(entry, "id", None) for entry in data)
        if identifier
    )


def probe_visual_ocr(
    *,
    settings=None,
    timeout: float | None = DEFAULT_PROBE_TIMEOUT,
    list_models=None,
) -> VisualOcrStatus:
    """Probe the configured visual-OCR endpoint. Never raises.

    ``list_models`` is an injection seam for tests: any zero-argument callable
    returning an iterable of model ids stands in for the HTTP round trip, so
    the default suite proves the policy without a server and without importing
    the model client at all.
    """
    if settings is None:
        from .config import load_settings

        settings = load_settings()

    if list_models is None:
        # Imported here, not at module scope: modes that never use the visual
        # rung must not pull the model client into the process (asserted by
        # tests/test_discovery.py).
        from .ocr_client import _build_client

        probe_settings = settings if timeout is None else replace(settings, timeout=timeout)

        def list_models():  # noqa: E306 - local closure over the probe settings
            return _advertised_ids(_build_client(probe_settings))

    try:
        advertised = tuple(str(identifier) for identifier in (list_models() or ()))
    except Exception as exc:
        return VisualOcrStatus(
            available=False,
            base_url=settings.base_url,
            model=settings.model,
            detail=str(exc)[:200],
            error_type=type(exc).__name__,
        )
    return VisualOcrStatus(
        available=True,
        base_url=settings.base_url,
        model=settings.model,
        advertised=advertised,
    )
