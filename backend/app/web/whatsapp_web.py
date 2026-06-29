from __future__ import annotations

from flask import Blueprint, render_template

whatsapp_web_bp = Blueprint(
    "whatsapp_web",
    __name__,
    template_folder="templates",
    static_folder="static",
    static_url_path="/assets",
)


@whatsapp_web_bp.get("/whatsapp")
def whatsapp_page():
    return render_template("whatsapp.html")
