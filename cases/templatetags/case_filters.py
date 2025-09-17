from django import template
from django.utils.html import strip_tags
from html import unescape
import re

register = template.Library()


@register.filter(name="clean_html")
def clean_html(value):
    """Remove HTML tags and decode HTML entities"""
    if not value:
        return ""

    # Strip HTML tags
    text = strip_tags(value)

    # Decode HTML entities like &nbsp;
    text = unescape(text)

    # Replace multiple spaces with single space
    text = re.sub(r'\s+', ' ', text)

    # Strip leading and trailing whitespace
    text = text.strip()

    return text