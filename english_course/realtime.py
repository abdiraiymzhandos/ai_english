import hashlib
import logging
from typing import Any, Optional

import requests
from django.http import JsonResponse

from english_course.realtime_config import REALTIME_CLIENT_SECRETS_URL, REALTIME_MODEL

logger = logging.getLogger(__name__)


class RealtimeTokenError(RuntimeError):
    pass


def get_openai_safety_identifier(request) -> str:
    if request.user.is_authenticated:
        raw_identifier = str(request.user.id)
    else:
        if not request.session.session_key:
            request.session.create()
        raw_identifier = request.session.session_key
    return hashlib.sha256(raw_identifier.encode("utf-8")).hexdigest()


def build_realtime_session_config(
    *,
    instructions: str,
    voice: str = "cedar",
    model: str = REALTIME_MODEL,
) -> dict[str, Any]:
    return {
        "session": {
            "type": "realtime",
            "model": model,
            "instructions": instructions,
            "audio": {
                "input": {
                    "turn_detection": {
                        "type": "server_vad",
                    },
                },
                "output": {
                    "voice": voice,
                },
            },
        },
    }


def _extract_client_secret(data: dict[str, Any]) -> Optional[str]:
    value = data.get("value")
    if isinstance(value, str):
        return value

    client_secret = data.get("client_secret")

    if isinstance(client_secret, dict):
        value = client_secret.get("value")
        return value if isinstance(value, str) else None

    if isinstance(client_secret, str):
        return client_secret

    return None


def mint_realtime_client_secret(
    *,
    api_key: str,
    instructions: str,
    safety_identifier: str,
    feature: str,
    voice: str = "cedar",
    model: str = REALTIME_MODEL,
    timeout: int = 20,
) -> dict[str, Any]:
    payload = build_realtime_session_config(
        instructions=instructions,
        voice=voice,
        model=model,
    )
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "OpenAI-Safety-Identifier": safety_identifier,
    }

    logger.info(
        "Minting Realtime client secret for %s with model %s",
        feature,
        model,
    )

    try:
        response = requests.post(
            REALTIME_CLIENT_SECRETS_URL,
            headers=headers,
            json=payload,
            timeout=timeout,
        )
    except requests.RequestException as exc:
        logger.exception("Realtime client secret request failed for %s", feature)
        raise RealtimeTokenError("Realtime token request failed") from exc

    if response.status_code >= 400:
        try:
            err_payload = response.json()
        except ValueError:
            err_payload = {"error": response.text}
        logger.error(
            "Realtime client secret error for %s: status=%s payload=%s",
            feature,
            response.status_code,
            err_payload,
        )
        raise RealtimeTokenError("Realtime token request rejected")

    try:
        data = response.json()
    except ValueError as exc:
        logger.exception("Invalid Realtime client secret JSON for %s", feature)
        raise RealtimeTokenError("Invalid Realtime token response") from exc

    if not isinstance(data, dict):
        logger.error("Realtime client secret response for %s was not a JSON object", feature)
        raise RealtimeTokenError("Invalid Realtime token response")

    secret_value = _extract_client_secret(data)
    if not secret_value:
        logger.error("Realtime client secret response for %s omitted secret value", feature)
        raise RealtimeTokenError("Realtime token response missing client secret")

    logger.info("Realtime client secret minted for %s", feature)
    token_payload = dict(data)
    if not isinstance(token_payload.get("value"), str):
        token_payload["value"] = secret_value
    token_payload["realtime_model"] = model
    return token_payload


def realtime_token_error_response() -> JsonResponse:
    return JsonResponse(
        {"error": "OpenAI Realtime уақытша қолжетімсіз. Кейін қайталап көріңіз."},
        status=502,
    )
