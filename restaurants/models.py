from django.db import models

from core.models import TimeStampedModel
from core.utils import unique_slug


class Cuisine(TimeStampedModel):
    name = models.CharField(max_length=60, unique=True)
    slug = models.SlugField(max_length=70, unique=True, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, self.name)
        super().save(*args, **kwargs)


class Restaurant(TimeStampedModel):
    class PriceRange(models.IntegerChoices):
        BUDGET = 1, "₹"
        MODERATE = 2, "₹₹"
        PREMIUM = 3, "₹₹₹"

    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140, unique=True, blank=True)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to="restaurants/", blank=True)
    cuisines = models.ManyToManyField(Cuisine, related_name="restaurants", blank=True)
    location = models.CharField(max_length=150, help_text="Neighbourhood or area, e.g. Bandra West")
    city = models.CharField(max_length=80)
    price_range = models.PositiveSmallIntegerField(choices=PriceRange.choices, default=PriceRange.MODERATE)
    delivery_time_minutes = models.PositiveSmallIntegerField(default=30)
    delivery_fee = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    min_order_amount = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    is_veg_only = models.BooleanField(default=False)
    is_open = models.BooleanField(default=True, help_text="Untick to mark the restaurant closed / not accepting orders.")
    # Maintained by reviews.signals from approved reviews.
    avg_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0, editable=False)
    review_count = models.PositiveIntegerField(default=0, editable=False)

    class Meta:
        ordering = ["-avg_rating", "name"]
        indexes = [
            models.Index(fields=["is_open", "-avg_rating"]),
            models.Index(fields=["city", "price_range"]),
            models.Index(fields=["delivery_time_minutes"]),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, self.name)
        super().save(*args, **kwargs)