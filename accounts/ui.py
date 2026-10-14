"""Validated presentation settings shared by all page families."""
import re
from django.conf import settings

BRAND_DEFAULTS = {"primary": "#103b07", "secondary": "#5a1113", "accent": "#f5e587"}


def brand_tokens(config):
    tokens = {}
    for name, fallback in BRAND_DEFAULTS.items():
        color = getattr(config, f"{name}_color", fallback) or fallback
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
            color = fallback
        tokens[name] = {"hex": color, "rgb": " ".join(str(int(color[i:i + 2], 16)) for i in (1, 3, 5))}
    return tokens


def idle_timeout_seconds():
    # The UI must never promise a session longer than its cookie lasts.
    return max(1, min(settings.IDLE_TIMEOUT_SECONDS, settings.SESSION_COOKIE_AGE))
