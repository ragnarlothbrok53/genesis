import logging

from opentelemetry import trace
from opentelemetry._logs import set_logger_provider
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from genesis.core.config import settings
from genesis.core.net import host_port, tcp_ok

logger = logging.getLogger(__name__)

_configured = False


def check() -> bool:
    host, port = host_port(settings.OTEL_EXPORTER_OTLP_ENDPOINT, 5080)
    return tcp_ok(host, port)


def _otlp_headers() -> dict:
    token = settings.get("OTEL_EXPORTER_OTLP_TOKEN", "")
    headers = {
        "organization": settings.get("OTEL_ORG", "default"),
        "stream-name": settings.get("OTEL_STREAM", "default"),
    }
    if token:
        headers["Authorization"] = f"Basic {token}"
    return headers


def _setup_traces(resource: Resource, headers: dict) -> None:
    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(
        endpoint=f"{settings.OTEL_EXPORTER_OTLP_ENDPOINT}/v1/traces",
        headers=headers,
    )
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)


def _setup_logs(resource: Resource, headers: dict) -> None:
    provider = LoggerProvider(resource=resource)
    exporter = OTLPLogExporter(
        endpoint=f"{settings.OTEL_EXPORTER_OTLP_ENDPOINT}/v1/logs",
        headers=headers,
    )
    provider.add_log_record_processor(BatchLogRecordProcessor(exporter))
    set_logger_provider(provider)
    logging.getLogger().addHandler(LoggingHandler(logger_provider=provider))


def _instrument(app) -> None:
    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
    from opentelemetry.instrumentation.psycopg2 import Psycopg2Instrumentor
    from opentelemetry.instrumentation.redis import RedisInstrumentor

    Psycopg2Instrumentor().instrument()
    HTTPXClientInstrumentor().instrument()
    RedisInstrumentor().instrument()

    if app is not None:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor.instrument_app(app)


def setup_observability(app=None) -> None:
    global _configured
    if _configured or not settings.OTEL_ENABLED:
        return
    _configured = True

    if not check():
        logger.warning(
            "OpenObserve not reachable at %s, observability disabled",
            settings.OTEL_EXPORTER_OTLP_ENDPOINT,
        )
        return

    resource = Resource.create({"service.name": settings.OTEL_SERVICE_NAME})
    headers = _otlp_headers()
    _setup_traces(resource, headers)
    _setup_logs(resource, headers)
    _instrument(app)
    logger.info("Observability exporting to %s", settings.OTEL_EXPORTER_OTLP_ENDPOINT)
