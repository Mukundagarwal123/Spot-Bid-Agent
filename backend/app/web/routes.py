from __future__ import annotations

from flask import Blueprint, render_template

portal_web_bp = Blueprint(
    "portal_web",
    __name__,
    template_folder="templates",
    static_folder="static",
    static_url_path="/assets",
)


@portal_web_bp.get("/")
@portal_web_bp.get("/portal")
def portal_page():
    return render_template("portal.html")


@portal_web_bp.get("/lanes/<lane_id>")
def lane_detail_page(lane_id: str):
    return render_template("lane_detail.html", lane_id=lane_id)
