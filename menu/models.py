from decimal import Decimal

from django.conf import settings
from django.db import models, transaction

from core.models import TimeStampedModel
from core.utils import unique_slug


class Category(TimeStampedModel):
    name = models.CharField(max_length=60, unique=True)
    slug = models.SlugField(max_length=70, unique=True, blank=True)
    icon = models.CharField(max_length=50, blank=True, help_text="Bootstrap Icons class, e.g. bi-cup-hot")
    image = models.ImageField(upload_to="categories/", blank=True)
    display_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["display_order", "name"]
        verbose_name_plural = "categories"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, self.name)
        super().save(*args, **kwargs)


class FoodItem(TimeStampedModel):
    restaurant = models.ForeignKey("restaurants.Restaurant", on_delete=models.CASCADE, related_name="food_items")
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="food_items")
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140, unique=True, blank=True)
    description = models.CharField(max_length=255)
    ingredients = models.TextField(blank=True, help_text="Comma-separated, e.g. Chicken, Lettuce, Brioche bun")
    price = models.DecimalField(max_digits=8, decimal_places=2)
    is_veg = models.BooleanField(default=True)
    is_available = models.BooleanField(default=True)
    is_popular = models.BooleanField(default=False, help_text="Show in the Popular section on the home page.")
    # Maintained by reviews.signals from approved reviews.
    avg_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0, editable=False)
    review_count = models.PositiveIntegerField(default=0, editable=False)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["category", "is_available"]),
            models.Index(fields=["restaurant", "is_available"]),
            models.Index(fields=["is_popular", "-avg_rating"]),
            models.Index(fields=["is_veg"]),
        ]
        constraints = [
            models.CheckConstraint(condition=models.Q(price__gte=0), name="menu_fooditem_price_non_negative"),
        ]

    def __str__(self):
        return f"{self.name} ({self.restaurant})"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, self.name)
        super().save(*args, **kwargs)

    @property
    def ingredient_list(self):
        return [item.strip() for item in self.ingredients.split(",") if item.strip()]

    @property
    def primary_image(self):
        """Uses prefetched `images` when available, so list pages stay query-free."""
        images = list(self.images.all())
        return next((img for img in images if img.is_primary), images[0] if images else None)

    def price_for(self, size=None, extras=()):
        """Single source of truth for customised unit price (cart, orders and API all use this)."""
        total = self.price
        if size is not None:
            total += size.price_delta
        total += sum((extra.price for extra in extras), Decimal("0"))
        return total


class FoodImage(TimeStampedModel):
    food_item = models.ForeignKey(FoodItem, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="food/")
    alt_text = models.CharField(max_length=150, blank=True)
    is_primary = models.BooleanField(default=False)
    display_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["-is_primary", "display_order", "id"]

    def __str__(self):
        return f"Image for {self.food_item.name}"

    def save(self, *args, **kwargs):
        with transaction.atomic():
            if self.is_primary:
                FoodImage.objects.filter(food_item=self.food_item, is_primary=True).exclude(pk=self.pk).update(
                    is_primary=False
                )
            super().save(*args, **kwargs)


class FoodSize(TimeStampedModel):
    """Size option such as Regular / Large. price_delta is added to the base price."""

    food_item = models.ForeignKey(FoodItem, on_delete=models.CASCADE, related_name="sizes")
    name = models.CharField(max_length=40)
    price_delta = models.DecimalField(max_digits=7, decimal_places=2, default=0)
    is_default = models.BooleanField(default=False)

    class Meta:
        ordering = ["price_delta", "id"]
        constraints = [
            models.UniqueConstraint(fields=["food_item", "name"], name="menu_foodsize_unique_name_per_food"),
        ]

    def __str__(self):
        return f"{self.food_item.name} - {self.name}"


class FoodExtra(TimeStampedModel):
    """Optional add-on such as Extra Cheese."""

    food_item = models.ForeignKey(FoodItem, on_delete=models.CASCADE, related_name="extras")
    name = models.CharField(max_length=60)
    price = models.DecimalField(max_digits=7, decimal_places=2, default=0)
    is_available = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["food_item", "name"], name="menu_foodextra_unique_name_per_food"),
        ]

    def __str__(self):
        return f"{self.food_item.name} + {self.name}"


class Wishlist(TimeStampedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="wishlist_items")
    food_item = models.ForeignKey(FoodItem, on_delete=models.CASCADE, related_name="wishlisted_by")

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["user", "food_item"], name="menu_wishlist_unique_user_food"),
        ]

    def __str__(self):
        return f"{self.user} - {self.food_item.name}"