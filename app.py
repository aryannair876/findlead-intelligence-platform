"""FindLead Intelligence Platform - AI-native orchestration layer."""

from __future__ import annotations

import os
from datetime import datetime

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request

from services.analysis_service import (
    EmailValidationService,
    SentimentAnalysisService,
    WebsiteMonitoringService,
    iso_timestamp,
)
from services.llm_router import LLMRouter


load_dotenv()

app = Flask(__name__)

try:
    _llm_router = LLMRouter()
    router_init_error = None
except RuntimeError as exc:  # noqa: BLE001
    _llm_router = None
    router_init_error = str(exc)


sentiment_service: SentimentAnalysisService | None = (
    SentimentAnalysisService(_llm_router) if _llm_router else None
)
email_service: EmailValidationService | None = (
    EmailValidationService(_llm_router) if _llm_router else None
)
website_service: WebsiteMonitoringService | None = (
    WebsiteMonitoringService(_llm_router) if _llm_router else None
)


def _ensure_router_ready():
    if _llm_router is None:
        raise RuntimeError(router_init_error or "LLM router is not initialised")





@app.route("/")
def home():
    return render_template("dashboard.html")


@app.route("/askspot-analyzer")
def askspot_analyzer():
    return render_template("askspot-analyzer.html")


@app.route("/sentiment")
def sentiment():
    return render_template("sentiment.html")


@app.route("/email-validation")
def email_validation():
    return render_template("email_validation.html")


@app.route("/website-monitoring")
def website_monitoring():
    return render_template("website-monitoring.html")


def _service_guard(service):
    _ensure_router_ready()
    if service is None:
        raise RuntimeError("Requested service is not available")
    return service


@app.route("/api/analyze-sentiment", methods=["POST"])
def analyze_sentiment():
    try:
        service = _service_guard(sentiment_service)
        payload = request.get_json(force=True) or {}
        email_content = payload.get("email_content", "").strip()
        if not email_content:
            return jsonify({"error": "Email content is required"}), 400

        result = service.analyze(
            email_content=email_content,
            subject=payload.get("subject", ""),
            sender_email=payload.get("sender_email", ""),
        )

        response = {
            "status": "completed",
            "analyzed_at": iso_timestamp(),
            "provider": result.provider,
            "latency_seconds": result.latency_seconds,
            "analysis": result.data,
        }
        return jsonify(response)
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": str(exc)}), 500


@app.route("/api/validate-email", methods=["POST"])
def validate_email():
    try:
        service = _service_guard(email_service)
        payload = request.get_json(force=True) or {}
        email = payload.get("email", "").strip()
        if not email:
            return jsonify({"error": "Email address is required"}), 400

        result = service.validate(email)
        return jsonify({
            "status": "completed",
            "analyzed_at": iso_timestamp(),
            "provider": result.provider,
            "latency_seconds": result.latency_seconds,
            "analysis": result.data,
        })
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": str(exc)}), 500


@app.route("/api/monitor-website", methods=["POST"])
def monitor_website():
    try:
        service = _service_guard(website_service)
        payload = request.get_json(force=True) or {}
        website_url = payload.get("website_url") or payload.get("url")
        if not website_url:
            return jsonify({"error": "Website URL is required"}), 400

        result = service.analyze(website_url)
        response = {
            "status": "completed",
            "analyzed_at": iso_timestamp(),
            "provider": result.provider,
            "latency_seconds": result.latency_seconds,
            "analysis": result.data,
        }
        return jsonify(response)
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": str(exc)}), 500


@app.route("/api/askspot-analysis", methods=["POST"])
def askspot_analysis():
    # Same processing as website monitoring but keeping legacy endpoint name
    return monitor_website()


@app.route("/api/health", methods=["GET"])
def health_check():
    status = "healthy" if router_init_error is None else "degraded"
    return jsonify(
        {
            "status": status,
            "server_running": True,
            "providers": [
                provider.config.name
                for provider in (_llm_router.providers if _llm_router else [])
            ],
            "groq_api_configured": bool(os.getenv("GROQ_API_KEY")),
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "version": "4.0-ai-router",
            "error": router_init_error,
        }
    )


if __name__ == "__main__":
    print("🚀 Starting FindLead Intelligence Platform (production)")
    if router_init_error:
        print(f"⚠️ LLM router initialisation warning: {router_init_error}")
    else:
        provider_names = ", ".join(p.config.name for p in _llm_router.providers)
        print(f"🤖 Active providers: {provider_names}")
    # Honor PORT env var if set; default to 5002
    import os as _os
    _port = int(_os.getenv("PORT", "5002"))
    app.run(host="0.0.0.0", port=_port, debug=False)
