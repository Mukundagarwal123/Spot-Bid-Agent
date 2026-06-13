from __future__ import annotations

import uuid

import structlog
from flask import Flask, g, request

from app.core.logging import configure_logging, correlation_id_var
from app.core.settings import settings
from app.db.base import create_tables
from app.health.routes import health_bp
from app.portal.api import portal_api_bp
from app.portal.carriers.routes import carriers_api_bp
from app.portal.outreach.routes import outreach_bp
from app.web.routes import portal_web_bp
from app.webhooks.routes import webhooks_bp

configure_logging()
logger = structlog.get_logger(__name__)


def create_app() -> Flask:
    app = Flask(__name__, static_folder=None)
    app.config["APP_ENV"] = settings.app_env
    app.config["APP_NAME"] = settings.app_name

    @app.before_request
    def _set_correlation_id() -> None:
        cid = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        g.correlation_id = cid
        correlation_id_var.set(cid)

    @app.after_request
    def _attach_correlation_id(response):
        cid = getattr(g, "correlation_id", None)
        if cid:
            response.headers["X-Request-ID"] = cid
        correlation_id_var.set(None)
        return response

    create_tables()
    logger.info("startup", env=settings.app_env, db=settings.database_url)
    logger.info(
        "startup.llm_config",
        llm_base_url=settings.llm_base_url,
        llm_model=settings.llm_model,
        llm_api_key_set=bool(settings.llm_api_key),
    )

    app.register_blueprint(portal_web_bp)
    app.register_blueprint(portal_api_bp)
    app.register_blueprint(carriers_api_bp)
    app.register_blueprint(outreach_bp)
    app.register_blueprint(webhooks_bp)
    app.register_blueprint(health_bp)

    return app


app = create_app()
