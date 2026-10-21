from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from core.models import TimeStampedModel


class Review(TimeStampedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reviews")
    food_item = models.ForeignKey("menu.FoodItem", on_delete=models.CASCADE, related_name="reviews")
    rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField(max_length=1000, blank=True)
    is_approved = models.BooleanField(default=True, help_text="Untick to hide this review (moderation).")

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["food_item", "is_approved", "-created_at"])]
        constraints = [
            models.UniqueConstraint(fields=["user", "food_item"], name="reviews_review_one_per_user_food"),
            models.CheckConstraint(condition=models.Q(rating__gte=1, rating__lte=5), name="reviews_review_rating_range"),
        ]

    def __str__(self):
        return f"{self.user} - {self.food_item.name} ({self.rating}/5)"