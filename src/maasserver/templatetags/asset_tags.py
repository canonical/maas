import json

from django import template

from maasserver.djangosettings import settings

register = template.Library()


@register.simple_tag
def get_index_css_path() -> str:
    """Get the path to the index.html CSS file used for the api docs."""
    if not settings.MAAS_UI_MANIFEST_PATH.exists():
        return ""

    with open(settings.MAAS_UI_MANIFEST_PATH, "r") as f:
        manifest = json.load(f)

    try:
        return f"/MAAS/r/{manifest["index.html"]["css"][0]}"
    except KeyError:
        return ""
