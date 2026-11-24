"""Read-only, per-call verification of the exact Gemini key's billing project."""
import re

import streamlit as st
from google.auth.transport.requests import AuthorizedSession

BILLING_SCOPES = [
    "https://www.googleapis.com/auth/cloud-platform.read-only",
    "https://www.googleapis.com/auth/cloud-billing.readonly",
]


class FreeOnlyBlocked(RuntimeError):
    pass


def checked_response(response, stage):
    if response.status_code == 200:
        return response.json()
    labels = {
        "SERVICE_DISABLED": "İlgili Google API projesinde etkin değil.",
        "ACCESS_TOKEN_SCOPE_INSUFFICIENT": "Google okuma izni eksik; bağlantıyı yeniden kurun.",
        "IAM_PERMISSION_DENIED": "Bu Google hesabının proje okuma yetkisi yok.",
        "PERMISSION_DENIED": "Google proje erişimini reddetti.",
        "API_KEY_INVALID": "Gemini anahtarı geçersiz.",
        "CONSUMER_INVALID": "Google API tüketici projesi geçersiz.",
    }
    reason = "Google erişim kontrolünü tamamlayamadı."
    try:
        body = response.json().get("error", {})
        for detail in body.get("details", []):
            code = detail.get("reason") if isinstance(detail, dict) else None
            if code in labels:
                reason = labels[code]
                break
    except Exception:
        pass
    status = response.status_code
    status = status if type(status) is int and 100 <= status <= 599 else "?"
    raise FreeOnlyBlocked(f"{stage} · HTTP {status} · {reason} Üretim kapalı; ödeme eklemeyin.")


def verify_unbilled_key(api_key, credentials, session_factory=AuthorizedSession):
    """Never generate, change billing, cache authorization, or return key material.

    Query the owning project rather than trusting an operator-entered project ID.
    A linked but inactive billing account is rejected too. No provider error bodies
    are surfaced, since lookupKey URLs contain the API key.
    """
    if not api_key or credentials is None:
        raise FreeOnlyBlocked(
            "Yalnızca ücretsiz mod: bağlantı doğrulanmadı. Üstteki Google ücretsiz kullanım "
            "kontrolünü bağlayın; ödeme veya kart eklemeyin."
        )
    try:
        with session_factory(credentials) as session:
            lookup = session.get(
                "https://apikeys.googleapis.com/v2/keys:lookupKey",
                params={"keyString": api_key}, timeout=10, allow_redirects=False,
            )
            key = checked_response(lookup, "API Keys API: anahtarın projesi")
            parent = key.get("parent", "")
            if not re.fullmatch(r"projects/[0-9]+/locations/global", parent):
                raise ValueError("project")
            if not re.fullmatch(re.escape(parent) + r"/keys/[A-Za-z0-9_-]+", key.get("name", "")):
                raise ValueError("key")
            project = parent.split("/")[1]
            response = session.get(
                f"https://cloudbilling.googleapis.com/v1/projects/{project}/billingInfo",
                timeout=10, allow_redirects=False,
            )
            info = checked_response(response, "Cloud Billing API: faturalandırma")
            # Proto JSON may omit a false boolean and an empty string. Only a
            # successful, identified BillingInfo resource permits those defaults.
            project_id = info.get("projectId", "")
            if not re.fullmatch(r"[a-z][a-z0-9-]{4,61}[a-z0-9]|[0-9]+", project_id):
                raise ValueError("billing identity")
            if info.get("name") not in {
                f"projects/{project_id}/billingInfo", f"projects/{project}/billingInfo"
            }:
                raise ValueError("billing identity")
            if info.get("billingEnabled", False) is not False or info.get("billingAccountName", "") != "":
                raise FreeOnlyBlocked(
                    "Bu Gemini projesine faturalandırma hesabı bağlı veya "
                    "faturalandırma açık. Yalnızca ücretsiz modda üretim kapalı. "
                    "Panel faturalandırma ayarlarını değiştirmez."
                )
            return project_id
    except FreeOnlyBlocked:
        raise
    except Exception:
        raise FreeOnlyBlocked(
            "Google ücretsiz kullanım kontrolü tamamlanamadı. Hesabın anahtarın "
            "projesinde apikeys.keys.lookup ve resourcemanager.projects.get "
            "izinleri, API Keys API ve Cloud Billing API erişimi gerekli. "
            "Ücretli üretim denenmedi; kart veya ödeme eklemeyin."
        ) from None


def require_free_generation():
    # No success cache: changing API keys or billing must invalidate eligibility.
    try:
        api_key = st.secrets.get("GEMINI_API_KEY")
        credentials = st.session_state.get("vortex_billing_credentials")
    except Exception:
        api_key, credentials = None, None
    return verify_unbilled_key(api_key, credentials)
