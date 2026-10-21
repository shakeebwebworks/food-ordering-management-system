from decimal import Decimal

from django.db.models import Avg, Count
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from menu.models import FoodItem
from restaurants.models import Restaurant

from .models import Review


def _rating_values(queryset):
    stats = queryset.aggregate(avg=Avg("rating"), count=Count("id"))
    return round(Decimal(str(stats["avg"] or 0)), 2), stats["count"]


def refresh_rating_aggregates(food_item_id):
    """Recompute cached rating/review_count for a food item and its restaurant."""
    approved = Review.objects.filter(is_approved=True)

    avg, count = _rating_values(approved.filter(food_item_id=food_item_id))
    FoodItem.objects.filter(pk=food_item_id).update(avg_rating=avg, review_count=count)

    restaurant_id = FoodItem.objects.filter(pk=food_item_id).values_list("restaurant_id", flat=True).first()
    if restaurant_id:
        avg, count = _rating_values(approved.filter(food_item__restaurant_id=restaurant_id))
        Restaurant.objects.filter(pk=restaurant_id).update(avg_rating=avg, review_count=count)


@receiver([post_save, post_delete], sender=Review)
def update_rating_aggregates(sender, instance, **kwargs):
    refresh_rating_aggregates(instance.food_item_id)