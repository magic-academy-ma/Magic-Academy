"""Metadata-only, best-effort tracing; telemetry never changes execution results."""

import logging
from contextlib import contextmanager
from functools import wraps
from inspect import signature
from time import perf_counter
from urllib.parse import urlsplit

logger = logging.getLogger(__name__)
_client = None


def _create_client(settings):
    from langfuse import Langfuse
    from opentelemetry.sdk.trace import TracerProvider

    return Langfuse(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key,
        base_url=settings.langfuse_base_url,
        debug=False,
        tracer_provider=TracerProvider(),
        # Export only our manual SDK observations, never provider auto-instrumentation.
        should_export_span=lambda span: span.instrumentation_scope.name == 'langfuse-sdk',
    )


def configure_tracing(settings):
    global _client
    if _client is not None or not settings.langfuse_enabled:
        return
    try:
        url = urlsplit(settings.langfuse_base_url or '')
        url.port  # Validate malformed ports without logging the URL.
    except ValueError:
        logger.warning('Langfuse tracing disabled: invalid base URL')
        return
    if (not (settings.langfuse_public_key or "").strip()
            or not (settings.langfuse_secret_key or "").strip()
            or url.scheme not in ('http', 'https') or not url.hostname
            or url.username or url.password or url.query or url.fragment):
        logger.warning('Langfuse tracing disabled: incomplete or invalid configuration')
        return
    try:
        _client = _create_client(settings)
    except Exception:
        logger.warning('Langfuse tracing initialization failed')


def shutdown_tracing():
    global _client
    client, _client = _client, None
    if client is None:
        return
    for operation in (client.flush, client.shutdown):
        try:
            operation()
        except Exception:
            logger.warning('Langfuse tracing shutdown/export failed')


class SafeObservation:
    def __init__(self, span=None):
        self.span = span

    def update(self, **fields):
        if self.span is not None:
            try:
                self.span.update(**fields)
            except Exception:
                logger.warning('Langfuse tracing update failed')


@contextmanager
def observation(name, *, as_type='span', metadata=None, **fields):
    manager = None
    span = SafeObservation()
    started = perf_counter()
    if _client is not None:
        try:
            manager = _client.start_as_current_observation(
                name=name, as_type=as_type, metadata=metadata, **fields
            )
            span = SafeObservation(manager.__enter__())
        except Exception:
            manager = None
            logger.warning('Langfuse tracing span creation failed')
    try:
        yield span
    except BaseException as exc:
        span.update(level='ERROR', metadata={**(metadata or {}), 'status': 'failed', 'failure_type': type(exc).__name__})
        raise
    else:
        span.update(metadata={**(metadata or {}), 'status': 'completed'})
    finally:
        span.update(metadata={'duration_ms': (perf_counter() - started) * 1000})
        if manager is not None:
            try:
                # Never pass application exceptions: SDK would capture raw messages/stack.
                manager.__exit__(None, None, None)
            except Exception:
                logger.warning('Langfuse tracing span export failed')


def trace_tick(function):
    parameters = signature(function)

    @wraps(function)
    async def wrapped(*args, **kwargs):
        bound = parameters.bind(*args, **kwargs).arguments
        snapshot = bound.get('snapshot')
        simulation = bound.get('simulation')
        metadata = {
            'simulation_id': str(snapshot.simulation_id if snapshot else simulation.id),
            'tick_number': snapshot.current_tick if snapshot else simulation.current_tick + 1,
        }
        with observation('tick.engine' if snapshot else 'tick', metadata=metadata):
            return await function(*args, **kwargs)
    return wrapped
