"""KI-Assistent fuer ZTA OS (google-genai SDK mit 100 % deterministischem Offline-Fallback)."""
from __future__ import annotations

from typing import Any, Dict

from .logic import format_eur_from_cents


def run_ai_assist(
    mode: str,
    context: Dict[str, Any],
    api_key: str = "",
    model_name: str = "gemini-2.5-flash",
) -> Dict[str, Any]:
    """Liefert KI-Textvorschlaege fuer Agentur-Kommunikation oder nutzt den deterministischen Offline-Fallback."""
    fallback_text = _build_deterministic_fallback(mode, context)

    if not api_key:
        return {
            "mode": mode,
            "provider": "offline-fallback",
            "text": fallback_text,
        }

    try:
        from google import genai  # type: ignore

        client = genai.Client(api_key=api_key)
        prompt = (
            "Du bist der professionelle Assistent einer Berliner Schauspiel-, Regie- und PR-Agentur (ZTA Management). "
            "Verwende niemals Gedankenstriche. Antworte praezise, freundlich und kopierfertig auf Deutsch.\n\n"
            f"Modus: {mode}\n"
            f"Kontext: {context}\n"
        )
        resp = client.models.generate_content(model=model_name, contents=prompt)
        text = (getattr(resp, "text", None) or "").strip()
        if text:
            text = text.replace("\u2013", "-").replace("\u2014", "-")
            return {
                "mode": mode,
                "provider": "gemini",
                "text": text,
            }
    except Exception:
        pass

    return {
        "mode": mode,
        "provider": "offline-fallback",
        "text": fallback_text,
    }


def _build_deterministic_fallback(mode: str, context: Dict[str, Any]) -> str:
    client_name = str(context.get("client_name") or "unser Talent")
    project_title = str(context.get("project_title") or "das Projekt")
    gage_cents = int(context.get("gage_cents") or 150000)

    if mode == "contract_check":
        return (
            f"Vertragspruefung fuer {client_name} ({project_title}):\n"
            f"1. Vereinbarte Bruttogage: {format_eur_from_cents(gage_cents)}.\n"
            "2. Bitte Buyout-Umfang (DACH / Online / Festival) und Nachsynchron-Tagessatz im Vertragstext pruefen.\n"
            "3. Hinweis fuer Klient:in: Die Auszahlung erfolgt gesammelt zum Monatsende nach Zahlungseingang der Produktion."
        )
    if mode == "dossier_pitch":
        skills = ", ".join(context.get("skills") or ["Charakterrolle", "Mehrsprachig", "Berlin"])
        return (
            f"Empfehlung fuer \"{project_title}\": {client_name} bringt genau das gesuchte Profil mit ({skills}) "
            "und ist ab Berlin flexibel disponierbar. Aktuelles Demoband und Vita senden wir gerne direkt mit."
        )

    return (
        f"Vielen Dank fuer die Anfrage zu \"{project_title}\" fuer {client_name}. "
        f"Wir haben den Zeitraum im Agenturkalender geprueft und melden uns mit der abgestimmten Option zurueck."
    )
