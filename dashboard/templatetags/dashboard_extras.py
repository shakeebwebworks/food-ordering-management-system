from django import template

register = template.Library()

BADGE_CLASSES = {
    "placed": "badge-placed",
    "confirmed": "badge-placed",
    "preparing": "badge-preparing",
    "out_for_delivery": "badge-out",
    "delivered": "badge-delivered",
    "cancelled": "badge-cancelled",
    "pending": "badge-preparing",
    "paid": "badge-delivered",
    "failed": "badge-cancelled",
    "refunded": "badge-placed",
}


@register.filter
def cell(obj, path):
    """Reads a value such as "restaurant.name" from an object (and calls it if it is a method)."""
    value = obj
    for part in path.split("."):
        if value is None:
            return None
        value = getattr(value, part, None)
        if callable(value):
            value = value()
    return value


@register.filter
def badge_class(status):
    return BADGE_CLASSES.get(str(status), "badge-placed")