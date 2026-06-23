from django import template
import re

register = template.Library()

@register.filter
def strip_phase(value: str):
    if not value:
        return ""
    return re.sub(r"^Phase\s+[IVXLCDM]+\s+", "", value.strip(), flags=re.I).strip()