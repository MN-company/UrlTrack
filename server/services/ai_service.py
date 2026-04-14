import re
from typing import Iterable

from sqlalchemy import func

from ..config import Config
from ..extensions import db
from ..models import Link, Visit


class AIService:
    client = None
    genai_module = None
    mode = "disabled"

    @staticmethod
    def _strip_disabled_commands(message: str) -> str:
        return re.sub(r"@db:\S+", "", message or "").strip()

    @staticmethod
    def _summarize_visits(visits: list[Visit], title: str) -> str:
        if not visits:
            return f"\n=== {title} ===\nNo matching visits found.\n"

        emails = sorted({visit.email for visit in visits if visit.email})
        countries = sorted({visit.country for visit in visits if visit.country})
        devices = sorted({f'{visit.os_family or "Unknown"} / {visit.device_type or "Unknown"}' for visit in visits})
        links = sorted({visit.link.slug for visit in visits if visit.link})
        first_seen = min(visit.timestamp for visit in visits)
        last_seen = max(visit.timestamp for visit in visits)

        return (
            f"\n=== {title} ===\n"
            f"Visits: {len(visits)}\n"
            f"First Seen: {first_seen}\n"
            f"Last Seen: {last_seen}\n"
            f"Emails: {', '.join(emails) if emails else 'Anonymous'}\n"
            f"Countries: {', '.join(countries) if countries else 'Unknown'}\n"
            f"Devices: {', '.join(devices) if devices else 'Unknown'}\n"
            f"Links: {', '.join('/' + slug for slug in links) if links else 'None'}\n"
        )

    @classmethod
    def build_context(cls, message: str) -> tuple[str, str]:
        clean_message = cls._strip_disabled_commands(message)
        sections: list[str] = []

        email_match = re.search(r"@email:(\S+)", clean_message)
        if email_match:
            email = email_match.group(1)
            visits = Visit.query.filter_by(email=email).order_by(Visit.timestamp.desc()).limit(50).all()
            sections.append(cls._summarize_visits(visits, f"EMAIL CONTEXT: {email}"))

        hash_match = re.search(r"@hash:(\S+)", clean_message)
        if hash_match:
            value = hash_match.group(1)
            visits = (
                Visit.query.filter(db.or_(Visit.canvas_hash == value, Visit.etag == value))
                .order_by(Visit.timestamp.desc())
                .limit(50)
                .all()
            )
            sections.append(cls._summarize_visits(visits, f"FINGERPRINT CONTEXT: {value}"))

        visit_match = re.search(r"@visit:(\d+)", clean_message)
        if visit_match:
            visit = db.session.get(Visit, int(visit_match.group(1)))
            if visit:
                sections.append(
                    "\n=== VISIT CONTEXT ===\n"
                    f"ID: {visit.id}\n"
                    f"Timestamp: {visit.timestamp}\n"
                    f"IP: {visit.ip_address}\n"
                    f"Location: {visit.city or 'Unknown'}, {visit.country or 'Unknown'}\n"
                    f"Email: {visit.email or 'Anonymous'}\n"
                    f"Device: {visit.os_family or 'Unknown'} / {visit.device_type or 'Unknown'}\n"
                    f"Fingerprint: {visit.canvas_hash or visit.etag or 'None'}\n"
                    f"Link: /{visit.link.slug if visit.link else 'unknown'}\n"
                )

        link_match = re.search(r"@link:([A-Za-z0-9_-]+)", clean_message)
        if link_match:
            slug = link_match.group(1)
            link = Link.query.filter_by(slug=slug).first()
            if link:
                visits = Visit.query.filter_by(link_id=link.id).order_by(Visit.timestamp.desc()).limit(50).all()
                sections.append(
                    "\n=== LINK CONTEXT ===\n"
                    f"Slug: /{link.slug}\n"
                    f"Destination: {link.destination}\n"
                    f"Require Email: {link.require_email}\n"
                    f"Captcha Enabled: {link.enable_captcha}\n"
                    f"Total Visits: {Visit.query.filter_by(link_id=link.id).count()}\n"
                    f"{cls._summarize_visits(visits, f'LINK VISITS: /{link.slug}')}"
                )

        ip_match = re.search(r"@ip:([0-9a-fA-F:\.]+)", clean_message)
        if ip_match:
            ip_address = ip_match.group(1)
            visits = Visit.query.filter_by(ip_address=ip_address).order_by(Visit.timestamp.desc()).limit(50).all()
            sections.append(cls._summarize_visits(visits, f"IP CONTEXT: {ip_address}"))

        return clean_message, "\n".join(sections)

    @classmethod
    def initialize(cls):
        if cls.client or cls.genai_module:
            return

        if not Config.GEMINI_API_KEY:
            return

        try:
            from google import genai

            cls.client = genai.Client(api_key=Config.GEMINI_API_KEY)
            cls.mode = "new_sdk"
            return
        except Exception:
            pass

        try:
            import google.generativeai as genai_old

            genai_old.configure(api_key=Config.GEMINI_API_KEY)
            cls.genai_module = genai_old
            cls.mode = "old_sdk"
        except Exception as exc:
            print(f"AI Service unavailable: {exc}")
            cls.mode = "disabled"

    @classmethod
    def generate(cls, prompt: str, model: str | None = None) -> str:
        cls.initialize()
        target_model = model or Config.GEMINI_MODEL
        if cls.mode == "disabled":
            return "AI is not configured. Set GEMINI_API_KEY to enable the analyst."

        if cls.mode == "new_sdk":
            response = cls.client.models.generate_content(model=target_model, contents=prompt)
            return (getattr(response, "text", "") or str(response)).strip()

        model_instance = cls.genai_module.GenerativeModel(target_model)
        response = model_instance.generate_content(prompt)
        return (getattr(response, "text", "") or str(response)).strip()

    @classmethod
    def generate_stream(cls, prompt: str, model: str | None = None) -> Iterable[str]:
        cls.initialize()
        target_model = model or Config.GEMINI_MODEL
        if cls.mode == "disabled":
            yield "AI is not configured. Set GEMINI_API_KEY to enable the analyst."
            return

        if cls.mode == "new_sdk":
            for chunk in cls.client.models.generate_content_stream(model=target_model, contents=prompt):
                text = getattr(chunk, "text", "")
                if text:
                    yield text
            return

        model_instance = cls.genai_module.GenerativeModel(target_model)
        for chunk in model_instance.generate_content(prompt, stream=True):
            text = getattr(chunk, "text", "")
            if text:
                yield text

    @staticmethod
    def _system_prompt() -> str:
        total_visits = Visit.query.count()
        total_links = Link.query.count()
        identified_visits = Visit.query.filter(Visit.email.isnot(None)).count()

        recent_visits = Visit.query.order_by(Visit.timestamp.desc()).limit(5).all()
        recent_text = "\n".join(
            f"- {visit.timestamp:%Y-%m-%d %H:%M} | /{visit.link.slug if visit.link else 'unknown'} | {visit.ip_address} | {visit.country or 'Unknown'}"
            for visit in reversed(recent_visits)
        ) or "- No recent visits"

        top_countries = (
            db.session.query(Visit.country, func.count(Visit.id))
            .group_by(Visit.country)
            .order_by(func.count(Visit.id).desc())
            .limit(5)
            .all()
        )
        top_devices = (
            db.session.query(Visit.device_type, func.count(Visit.id))
            .group_by(Visit.device_type)
            .order_by(func.count(Visit.id).desc())
            .limit(5)
            .all()
        )

        country_text = ", ".join(f"{country or 'Unknown'} ({count})" for country, count in top_countries) or "None"
        device_text = ", ".join(f"{device or 'Unknown'} ({count})" for device, count in top_devices) or "None"

        return (
            "You are a security analytics assistant for UrlTrack.\n"
            "Focus on visits, links, fingerprints, IP patterns, and access-control signals.\n"
            "Be concise, practical, and explicit about uncertainty.\n\n"
            f"Total Visits: {total_visits}\n"
            f"Total Links: {total_links}\n"
            f"Identified Visits: {identified_visits}\n"
            f"Top Countries: {country_text}\n"
            f"Top Devices: {device_text}\n"
            f"Recent Activity:\n{recent_text}\n"
        )

    @classmethod
    def generate_response(cls, message: str) -> dict:
        clean_message, context = cls.build_context(message)
        prompt = f"{cls._system_prompt()}\n{context}\nUser Question: {clean_message}"
        response = cls.generate(prompt)
        return {
            "response": response,
            "model": Config.GEMINI_MODEL,
            "context_used": bool(context),
        }

    @classmethod
    def generate_stream_response(cls, message: str) -> Iterable[str]:
        clean_message, context = cls.build_context(message)
        prompt = f"{cls._system_prompt()}\n{context}\nUser Question: {clean_message}"
        return cls.generate_stream(prompt)
