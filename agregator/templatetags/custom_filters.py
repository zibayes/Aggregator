from django import template

register = template.Library()


@register.filter(name='getattr')
def get_attribute(obj, field_name):
    """Аналог getattr() для шаблонов Django."""
    return getattr(obj, field_name, "")
