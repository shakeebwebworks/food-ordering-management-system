from django.utils.text import slugify


def unique_slug(instance, source, field_name="slug"):
    """Return a slug for `source` that is unique across instance's model."""
    max_length = instance._meta.get_field(field_name).max_length
    base = (slugify(source) or "item")[: max_length - 6]
    slug, counter = base, 2
    others = instance.__class__._default_manager.exclude(pk=instance.pk)
    while others.filter(**{field_name: slug}).exists():
        slug = f"{base}-{counter}"
        counter += 1
    return slug