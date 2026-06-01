from __future__ import annotations

import structlog
from flask import Blueprint, jsonify

health_bp = Blueprint("health", __name__)
logger = structlog.get_logger(__name__)


@health_bp.get("/health")
def health():
    logger.info("health_check")
    return jsonify({"status": "ok"})
