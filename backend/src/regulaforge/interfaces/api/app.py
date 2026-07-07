"""FastAPI application factory.

Creates and configures the RegulaForge REST API with all
middleware, routers, and lifecycle hooks.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from prometheus_client import make_asgi_app

from regulaforge.agents.interfaces.api import create_agents_router
from regulaforge.modules.auth.interfaces import create_auth_router as create_module_auth_router
from regulaforge.modules.authorization.interfaces import create_authorization_router
from regulaforge.modules.users.interfaces import create_users_router
from regulaforge.modules.contracts.interfaces import create_contracts_router
from regulaforge.modules.regulations.interfaces import create_regulations_router
from regulaforge.modules.knowledge_graph.interfaces import create_knowledge_graph_router
from regulaforge.modules.reports.interfaces import create_reports_router
from regulaforge.modules.notifications.interfaces import create_notifications_router
from regulaforge.modules.audit.interfaces import create_audit_router
from regulaforge.modules.settings.interfaces import create_settings_router
from regulaforge.modules.websocket import create_websocket_router
from regulaforge.audit.interfaces.audit_middleware import add_audit_middleware
from regulaforge.config.constants import (
    API_CONTACT_EMAIL,
    API_CONTACT_NAME,
    API_CONTACT_URL,
    API_DESCRIPTION,
    API_TITLE,
    API_V1_PREFIX,
    API_VERSION,
)
from regulaforge.config.logging import configure_logging, get_logger
from regulaforge.config.settings import settings
from regulaforge.document_intelligence.interfaces.api import create_document_intelligence_router
from regulaforge.graphrag.interfaces.api import create_graphrag_router
from regulaforge.infrastructure.persistence.database import (
    check_database_health,
    initialize_database,
    shutdown_database,
)
from regulaforge.knowledge_graph.interfaces.api import router as knowledge_graph_router
from regulaforge.knowledge_graph.interfaces.api_graphrag import router as knowledge_graph_graphrag_router
from regulaforge.ingestion.interfaces.api import create_ingestion_router
from regulaforge.interfaces.api.middleware.error_handler import register_error_handlers
from regulaforge.interfaces.api.middleware.logging_middleware import LoggingMiddleware
from regulaforge.interfaces.api.middleware.prometheus_middleware import PrometheusMetricsMiddleware
from regulaforge.interfaces.api.middleware.rate_limit_middleware import add_rate_limit_middleware
from regulaforge.interfaces.api.middleware.security_headers import add_security_headers_middleware
from regulaforge.interfaces.api.v1.admin import router as admin_router
from regulaforge.interfaces.api.v1.assessments import router as assessments_router
from regulaforge.interfaces.api.v1.auth import router as auth_router
from regulaforge.interfaces.api.v1.dashboard import router as dashboard_router
from regulaforge.interfaces.api.v1.documents import router as documents_router
from regulaforge.interfaces.api.v1.entities import router as entities_router
from regulaforge.interfaces.api.v1.regulations import router as regulations_router
from regulaforge.ml.interfaces.api import router as ml_router

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifecycle manager.

    Handles startup and shutdown events including database
    connection pool initialization and cleanup.
    """
    # Startup
    logger.info(
        "Starting RegulaForge API v%s in %s mode",
        API_VERSION,
        settings.environment.value,
    )
    configure_logging()

    await initialize_database()

    # Health check
    healthy = await check_database_health()
    if not healthy:
        logger.warning("Database health check failed at startup")
    else:
        logger.info("Database health check passed")

    yield

    # Shutdown
    logger.info("Shutting down RegulaForge API")
    await shutdown_database()
    logger.info("RegulaForge API shut down")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application instance.

    Returns:
        A fully configured FastAPI application ready to serve.

    Raises:
        RuntimeError: If production security settings are not properly configured.
    """
    # Validate security configuration in production
    if settings.environment.value == "production":
        if "change-me" in settings.security.secret_key.lower():
            raise RuntimeError(
                "SECURITY CRITICAL: SECRET_KEY must be changed from the default value in production. "
                "Set REGULAFORGE_SECURITY_SECRET_KEY to a unique, secure value."
            )
        if "*" in settings.security.cors_origins:
            raise RuntimeError(
                "SECURITY CRITICAL: CORS origins cannot be wildcard '*' in production. "
                "Set REGULAFORGE_SECURITY_CORS_ORIGINS to specific allowed origins."
            )

    app = FastAPI(
        title=API_TITLE,
        description=API_DESCRIPTION,
        version=API_VERSION,
        contact={
            "name": API_CONTACT_NAME,
            "email": API_CONTACT_EMAIL,
            "url": API_CONTACT_URL,
        },
        docs_url="/api/v1/docs" if settings.docs_enabled else None,
        redoc_url="/api/v1/redoc" if settings.docs_enabled else None,
        openapi_url=settings.openapi_url if settings.docs_enabled else None,
        lifespan=lifespan,
    )

    # Middleware - order matters (last added = first executed)
    if settings.security.allowed_hosts:
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=settings.security.allowed_hosts,
        )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.security.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_middleware(PrometheusMetricsMiddleware)
    app.add_middleware(LoggingMiddleware)

    # Security headers (CSP, HSTS, X-Frame-Options, etc.)
    add_security_headers_middleware(app)

    # Rate limiting
    if settings.environment.value != "testing":
        add_rate_limit_middleware(app)

    # Audit logging
    add_audit_middleware(app, excluded_paths=["/health", "/metrics", "/docs", "/redoc", "/openapi.json"])

    # Register error handlers
    register_error_handlers(app)

    # Include routers
    app.include_router(auth_router, prefix=API_V1_PREFIX)
    app.include_router(admin_router, prefix=API_V1_PREFIX)
    app.include_router(dashboard_router, prefix=API_V1_PREFIX)
    app.include_router(regulations_router, prefix=API_V1_PREFIX)
    app.include_router(assessments_router, prefix=API_V1_PREFIX)
    app.include_router(entities_router, prefix=API_V1_PREFIX)
    app.include_router(documents_router, prefix=API_V1_PREFIX)

    ingestion_router = create_ingestion_router()
    app.include_router(ingestion_router, prefix=API_V1_PREFIX)

    docintel_router = create_document_intelligence_router()
    app.include_router(docintel_router, prefix=API_V1_PREFIX)

    graphrag_router = create_graphrag_router()
    app.include_router(graphrag_router, prefix=API_V1_PREFIX)

    app.include_router(knowledge_graph_router, prefix=API_V1_PREFIX)
    app.include_router(knowledge_graph_graphrag_router, prefix=API_V1_PREFIX)

    agents_router = create_agents_router()
    app.include_router(agents_router, prefix=API_V1_PREFIX)

    app.include_router(ml_router, prefix=API_V1_PREFIX)

    # Module routers (DDD-layered modules)
    module_auth_router = create_module_auth_router()
    app.include_router(module_auth_router, prefix=API_V1_PREFIX)

    authz_router = create_authorization_router()
    app.include_router(authz_router, prefix=API_V1_PREFIX)

    users_router = create_users_router()
    app.include_router(users_router, prefix=API_V1_PREFIX)

    contracts_router = create_contracts_router()
    app.include_router(contracts_router, prefix=API_V1_PREFIX)

    regulations_module_router = create_regulations_router()
    app.include_router(regulations_module_router, prefix=API_V1_PREFIX)

    kg_module_router = create_knowledge_graph_router()
    app.include_router(kg_module_router, prefix=API_V1_PREFIX)

    reports_router = create_reports_router()
    app.include_router(reports_router, prefix=API_V1_PREFIX)

    notifications_router = create_notifications_router()
    app.include_router(notifications_router, prefix=API_V1_PREFIX)

    audit_router = create_audit_router()
    app.include_router(audit_router, prefix=API_V1_PREFIX)

    settings_router = create_settings_router()
    app.include_router(settings_router, prefix=API_V1_PREFIX)

    ws_router = create_websocket_router()
    app.include_router(ws_router)

    # Prometheus metrics endpoint (separate from dashboard KPI at /api/v1/metrics)
    metrics_app = make_asgi_app()
    app.mount("/metrics", metrics_app)

    # Health check endpoint
    @app.get(f"{API_V1_PREFIX}/health")
    async def health_check() -> dict[str, Any]:
        """Health check endpoint for load balancers and monitoring."""
        db_healthy = await check_database_health()
        return {
            "status": "healthy" if db_healthy else "degraded",
            "version": API_VERSION,
            "environment": settings.environment.value,
            "database": "connected" if db_healthy else "disconnected",
        }

    logger.info("API application created with %d routers", len(app.routes))

    return app


app = create_app()
"""Global application instance for ASGI servers (uvicorn, gunicorn)."""
