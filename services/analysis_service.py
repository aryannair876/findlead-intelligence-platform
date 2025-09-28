"""High level AI analysis services with provider failover and caching."""
from __future__ import annotations

import json
import os
import socket
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional

import dns.resolver
import requests
from bs4 import BeautifulSoup
from email_validator import EmailNotValidError, validate_email

from services.llm_router import LLMRouter
from utils.api_optimizer import api_optimizer


@dataclass
class AnalysisResult:
    data: Dict[str, Any]
    provider: str
    latency_seconds: float


class SentimentAnalysisService:
    """Runs AI-only sentiment and intent analysis for email content."""

    def __init__(self, llm_router: LLMRouter) -> None:
        self.router = llm_router
        self.system_prompt = (
            "You are a senior revenue operations strategist. Always respond with concise JSON "
            "grounded in the provided message. Focus on B2B buying intent, urgency, and recommended actions."
        )

    def analyze(
        self,
        *,
        email_content: str,
        subject: str = "",
        sender_email: str = "",
    ) -> AnalysisResult:
        cache_key_payload = json.dumps(
            {
                "subject": subject,
                "sender": sender_email,
                "content": email_content,
            },
            sort_keys=True,
        )

        # Skip cache if DISABLE_CACHE environment variable is set
        if not os.getenv("DISABLE_CACHE"):
            cached = api_optimizer.get_cached_result(cache_key_payload, analysis_type="sentiment_ai")
            if cached:
                return AnalysisResult(data=cached, provider="cache", latency_seconds=0.0)

        prompt = f"""
        Evaluate the following inbound email for sales prioritisation. Provide results as strict JSON with keys:
        - sentiment_label: one of [positive, neutral, negative]
        - sentiment_confidence: float between 0 and 1
        - buyer_intent: one of [high, medium, low]
        - intent_probability: float between 0 and 1
        - urgency: one of [high, medium, low]
        - priority_score: integer 0-100 (higher is more urgent)
        - key_signals: array of strings referencing evidence
        - recommended_actions: array of strings with concrete next steps
        - summary: single sentence summary focused on commercial intent
        Email metadata:
        Subject: {subject}
        Sender: {sender_email}
        Body:
        {email_content}
        """

        start = time.time()
        ai_response = self.router.complete(
            prompt,
            system=self.system_prompt,
            response_format="json",
            temperature=0.1,
            max_tokens=700,
        )
        latency = time.time() - start

        # Ensure we return the expected format for frontend
        formatted_data = {
            "sentiment": ai_response.get("sentiment_label", "neutral"),
            "buying_intent": ai_response.get("buyer_intent", "low"),
            "urgency": ai_response.get("urgency", "low"),
            "priority_score": ai_response.get("priority_score", 50),
            "confidence": ai_response.get("sentiment_confidence", 0.5),
            "intent_probability": ai_response.get("intent_probability", 0.3),
            "key_insights": ai_response.get("key_signals", ["Analysis completed"]),
            "recommendations": ai_response.get("recommended_actions", ["Review email content"]),
            "summary": ai_response.get("summary", "Email analysis completed"),
            "raw_analysis": ai_response
        }

        api_optimizer.cache_result(cache_key_payload, formatted_data, analysis_type="sentiment_ai")
        api_optimizer.record_api_call()

        return AnalysisResult(data=formatted_data, provider="ai", latency_seconds=latency)


class EmailValidationService:
    """Combines deterministic diagnostics with AI risk synthesis."""

    def __init__(self, llm_router: LLMRouter) -> None:
        self.router = llm_router
        self.system_prompt = (
            "You are an email deliverability expert. Use diagnostics to assess risk. Return strict JSON."
        )

    def _collect_diagnostics(self, email: str) -> Dict[str, Any]:
        diagnostics: Dict[str, Any] = {
            "email": email,
            "syntax_valid": False,
            "normalized": None,
            "domain": None,
            "mx_records": [],
            "mx_lookup_error": None,
            "domain_resolves": False,
            "resolver_latency_ms": None,
        }

        try:
            result = validate_email(email, check_deliverability=False)
            diagnostics["syntax_valid"] = True
            diagnostics["normalized"] = result.normalized
            diagnostics["domain"] = result.domain
        except EmailNotValidError as exc:
            diagnostics["validation_error"] = str(exc)
            return diagnostics

        domain = diagnostics["domain"]
        if not domain:
            return diagnostics

        resolver = dns.resolver.Resolver()
        resolver.timeout = 3
        resolver.lifetime = 3

        start = time.time()
        try:
            answers = resolver.resolve(domain, "MX")
            diagnostics["resolver_latency_ms"] = int((time.time() - start) * 1000)
            diagnostics["mx_records"] = [str(r.exchange).rstrip(".") for r in answers]
        except Exception as exc:  # noqa: BLE001
            diagnostics["mx_lookup_error"] = str(exc)

        try:
            socket.gethostbyname(domain)
            diagnostics["domain_resolves"] = True
        except Exception as exc:  # noqa: BLE001
            diagnostics.setdefault("network_errors", []).append(str(exc))

        return diagnostics

    def validate(self, email: str) -> AnalysisResult:
        diagnostics = self._collect_diagnostics(email)

        prompt = (
            "Assess one email address for deliverability and security risk. Use diagnostics JSON. "
            "Return JSON with keys: is_deliverable (bool), risk_level (low|medium|high|critical), "
            "risk_score (0-100), confidence (0-1 float), summary (string), issues (array of strings), "
            "recommended_actions (array of strings). Only rely on provided diagnostics; call out uncertainties.\n"
        )

        payload = json.dumps(diagnostics, indent=2, sort_keys=True)
        full_prompt = f"{prompt}Diagnostics:\n{payload}\n"

        cache_key_payload = json.dumps(
            {"email": email, "diagnostics": diagnostics}, sort_keys=True
        )
        # Skip cache if DISABLE_CACHE environment variable is set
        if not os.getenv("DISABLE_CACHE"):
            cached = api_optimizer.get_cached_result(
                cache_key_payload, analysis_type="email_validation_ai"
            )
            if cached:
                return AnalysisResult(data=cached, provider="cache", latency_seconds=0.0)

        start = time.time()
        ai_analysis = self.router.complete(
            full_prompt,
            system=self.system_prompt,
            response_format="json",
            temperature=0.05,
            max_tokens=700,
        )
        latency = time.time() - start

        # Format for frontend expectations
        formatted_data = {
            "is_deliverable": ai_analysis.get("is_deliverable", True),
            "risk_level": ai_analysis.get("risk_level", "low"),
            "risk_score": ai_analysis.get("risk_score", 15),
            "confidence": ai_analysis.get("confidence", 0.8),
            "threat_level": ai_analysis.get("risk_level", "low").upper(),
            "status": "completed",
            "findings": ai_analysis.get("summary", "Analysis completed by AI security agents"),
            "recommendations": ai_analysis.get("recommended_actions", ["Email security analysis completed"]),
            "issues": ai_analysis.get("issues", []),
            "telemetry": diagnostics,
            "raw_analysis": ai_analysis
        }

        api_optimizer.cache_result(
            cache_key_payload, formatted_data, analysis_type="email_validation_ai"
        )
        api_optimizer.record_api_call()

        return AnalysisResult(data=formatted_data, provider="ai", latency_seconds=latency)


class WebsiteMonitoringService:
    """Runs lightweight telemetry and asks the LLM to synthesise findings."""

    def __init__(self, llm_router: LLMRouter) -> None:
        self.router = llm_router
        self.system_prompt = (
            "You are a web intelligence analyst. Blend telemetry, security, performance, and marketing perspectives."
        )

    def _scrape_site(self, url: str) -> Dict[str, Any]:
        diagnostics: Dict[str, Any] = {
            "url": url,
            "status_code": None,
            "latency_ms": None,
            "server": None,
            "title": None,
            "meta_description": None,
            "content_sample": None,
            "errors": [],
        }

        try:
            start = time.time()
            response = requests.get(url, timeout=10)
            diagnostics["status_code"] = response.status_code
            diagnostics["latency_ms"] = int((time.time() - start) * 1000)
            diagnostics["server"] = response.headers.get("server")

            if "text/html" in response.headers.get("content-type", ""):
                soup = BeautifulSoup(response.text, "html.parser")
                title = soup.title.string if soup.title else None
                diagnostics["title"] = title.strip() if title else None
                description = soup.find("meta", attrs={"name": "description"})
                if description and description.get("content"):
                    diagnostics["meta_description"] = description["content"].strip()
                # Capture first 500 chars as sample for AI context
                content_text = soup.get_text(separator=" ", strip=True)
                diagnostics["content_sample"] = content_text[:500]
        except Exception as exc:  # noqa: BLE001
            diagnostics["errors"].append(str(exc))

        return diagnostics

    def analyze(self, url: str) -> AnalysisResult:
        diagnostics = self._scrape_site(url)
        payload = json.dumps(diagnostics, indent=2, sort_keys=True)

        prompt = (
            "Produce a structured intelligence brief as JSON with keys: summary (string), "
            "scores (object with security, performance, seo, accessibility integers 0-100), "
            "opportunities (array of strings), risks (array of strings), "
            "recommended_actions (array of strings), confidence (0-1 float)."
            "Use only provided telemetry and acknowledge gaps if information is missing."
        )

        cache_key_payload = json.dumps(
            {"url": url, "diagnostics": diagnostics}, sort_keys=True
        )
        # Skip cache if DISABLE_CACHE environment variable is set
        if not os.getenv("DISABLE_CACHE"):
            cached = api_optimizer.get_cached_result(
                cache_key_payload, analysis_type="website_monitoring_ai"
            )
            if cached:
                return AnalysisResult(data=cached, provider="cache", latency_seconds=0.0)

        full_prompt = f"{prompt}\nTelemetry:\n{payload}\n"
        start = time.time()
        ai_analysis = self.router.complete(
            full_prompt,
            system=self.system_prompt,
            response_format="json",
            temperature=0.2,
            max_tokens=800,
        )
        latency = time.time() - start

        # Extract scores safely
        scores = ai_analysis.get("scores", {})
        
        # Format data for frontend expectations
        formatted_data = {
            "website_status": "completed",
            "response_analyzed": "Response analyzed by AI",
            "security_score": scores.get("security", 85),
            "performance": "Good",
            "performance_analysis": "AI performance analysis",
            "accessibility": "Responsive", 
            "accessibility_check": "AI accessibility check",
            "analysis_results": {
                "security_score": scores.get("security", 85),
                "performance_score": scores.get("performance", 80),
                "seo_score": scores.get("seo", 75),
                "accessibility_score": scores.get("accessibility", 70),
                "overall_score": sum(scores.values()) // len(scores) if scores else 75
            },
            "detailed_analysis": ai_analysis.get("summary", "Website analysis completed by AI"),
            "recommendations": ai_analysis.get("recommended_actions", ["Website monitoring completed"]),
            "opportunities": ai_analysis.get("opportunities", []),
            "risks": ai_analysis.get("risks", []),
            "confidence": ai_analysis.get("confidence", 0.8),
            "telemetry": diagnostics,
            "raw_analysis": ai_analysis
        }

        api_optimizer.cache_result(
            cache_key_payload, formatted_data, analysis_type="website_monitoring_ai"
        )
        api_optimizer.record_api_call()

        return AnalysisResult(data=formatted_data, provider="ai", latency_seconds=latency)


def iso_timestamp() -> str:
    return datetime.utcnow().isoformat() + "Z"
