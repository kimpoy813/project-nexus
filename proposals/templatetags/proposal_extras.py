from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    if dictionary is None:
        return ""
    return dictionary.get(key, "")

@register.filter
def choice_options(choices):
    """Normalize admin dictionaries and Django (value, label) pairs for chips."""
    result = []
    for choice in choices or []:
        if isinstance(choice, dict):
            result.append(choice)
        elif isinstance(choice, (list, tuple)) and len(choice) == 2:
            result.append({"value": choice[0], "label": choice[1]})
        else:
            result.append({"value": choice, "label": choice})
    return result
