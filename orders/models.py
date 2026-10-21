import secrets
from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from core.models import TimeStampedModel
from core.validators import phone_validator


class Coupon(TimeStampedModel):
    class DiscountType(models.TextChoices):
        PERCENT = "percent", "Percentage"
        FLAT = "flat", "Flat amount"

    code = models.CharField(max_length=30, unique=True)
    description = models.CharField(max_length=150, blank=True)
    discount_type = models.CharField(max_length=10, choices=DiscountType.choices, default=DiscountType.PERCENT)
    value = models.DecimalField(max_digits=8, decimal_places=2, help_text="Percent (e.g. 20) or flat rupee amount")
    max_discount = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True, help_text="Cap for percentage coupons"
    )
    min_order_amount = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    valid_from = models.DateTimeField()
    valid_until = models.DateTimeField()
    usage_limit = models.PositiveIntegerField(null=True, blank=True, help_text="Leave blank for unlimited")
    used_count = models.PositiveIntegerField(default=0, editable=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(condition=models.Q(value__gt=0), name="orders_coupon_value_positive"),
            models.CheckConstraint(
                condition=models.Q(valid_until__gt=models.F("valid_from")), name="orders_coupon_valid_range"
            ),
        ]

    def __str__(self):
        return self.code

    def save(self, *args, **kwargs):
        self.code = self.code.strip().upper()
        super().save(*args, **kwargs)

    def get_error(self, subtotal, now=None):
        """Return a user-facing reason this coupon can't be applied, or None if it can."""
        now = now or timezone.now()
        if not self.is_active:
            return "This coupon is no longer active."
        if not (self.valid_from <= now <= self.valid_until):
            return "This coupon has expired or is not valid yet."
        if self.usage_limit is not None and self.used_count >= self.usage_limit:
            return "This coupon has reached its usage limit."
        if subtotal < self.min_order_amount:
            return f"Add items worth ₹{self.min_order_amount:.0f} or more to use this coupon."
        return None

    def discount_for(self, subtotal):
        if self.discount_type == self.DiscountType.PERCENT:
            amount = subtotal * self.value / Decimal("100")
            if self.max_discount is not None:
                amount = min(amount, self.max_discount)
        else:
            amount = self.value
        return min(amount, subtotal).quantize(Decimal("0.01"))


class Cart(TimeStampedModel):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="cart")

    def __str__(self):
        return f"Cart of {self.user}"

    @property
    def subtotal(self):
        return sum((item.line_total for item in self.items.all()), Decimal("0"))


class CartItem(TimeStampedModel):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items")
    food_item = models.ForeignKey("menu.FoodItem", on_delete=models.CASCADE, related_name="+")
    size = models.ForeignKey("menu.FoodSize", on_delete=models.CASCADE, null=True, blank=True, related_name="+")
    extras = models.ManyToManyField("menu.FoodExtra", blank=True, related_name="+")
    quantity = models.PositiveSmallIntegerField(default=1, validators=[MinValueValidator(1), MaxValueValidator(20)])

    class Meta:
        ordering = ["created_at"]
        indexes = [models.Index(fields=["cart", "food_item"])]

    def __str__(self):
        return f"{self.quantity} x {self.food_item.name}"

    @property
    def unit_price(self):
        return self.food_item.price_for(self.size, self.extras.all())

    @property
    def line_total(self):
        return self.unit_price * self.quantity


def generate_order_number():
    while True:
        number = f"FD{timezone.localdate():%y%m%d}{secrets.token_hex(3).upper()}"
        if not Order.objects.filter(order_number=number).exists():
            return number


class Order(TimeStampedModel):
    class Status(models.TextChoices):
        PLACED = "placed", "Order Placed"
        CONFIRMED = "confirmed", "Restaurant Confirmed"
        PREPARING = "preparing", "Preparing"
        OUT_FOR_DELIVERY = "out_for_delivery", "Out for Delivery"
        DELIVERED = "delivered", "Delivered"
        CANCELLED = "cancelled", "Cancelled"

    order_number = models.CharField(max_length=20, unique=True, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="orders")
    restaurant = models.ForeignKey(
        "restaurants.Restaurant", on_delete=models.SET_NULL, null=True, related_name="orders"
    )
    restaurant_name = models.CharField(max_length=120)  # snapshot: history survives restaurant deletion
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PLACED)

    # Delivery details are snapshots so later address edits don't rewrite past orders.
    contact_name = models.CharField(max_length=100)
    contact_phone = models.CharField(max_length=14, validators=[phone_validator])
    delivery_address = models.TextField()
    notes = models.TextField(blank=True)

    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    delivery_fee = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    tax = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    discount = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=10, decimal_places=2)
    coupon = models.ForeignKey(Coupon, on_delete=models.SET_NULL, null=True, blank=True, related_name="orders")
    estimated_delivery_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["restaurant", "-created_at"]),
        ]
        constraints = [
            models.CheckConstraint(condition=models.Q(total__gte=0), name="orders_order_total_non_negative"),
        ]

    def __str__(self):
        return self.order_number

    def save(self, *args, **kwargs):
        creating = self._state.adding
        if not self.order_number:
            self.order_number = generate_order_number()
        super().save(*args, **kwargs)
        if creating:
            OrderStatusEvent.objects.create(order=self, status=self.status)

    def update_status(self, new_status, note=""):
        """Change status and record it on the tracking timeline."""
        if new_status == self.status:
            return
        self.status = new_status
        self.save(update_fields=["status", "updated_at"])
        OrderStatusEvent.objects.create(order=self, status=new_status, note=note)


class OrderItem(TimeStampedModel):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    food_item = models.ForeignKey("menu.FoodItem", on_delete=models.SET_NULL, null=True, related_name="+")
    name = models.CharField(max_length=120)  # snapshot
    size_name = models.CharField(max_length=40, blank=True)
    extras = models.JSONField(default=list, blank=True)  # list of extra names at time of order
    unit_price = models.DecimalField(max_digits=8, decimal_places=2)
    quantity = models.PositiveSmallIntegerField(default=1)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(quantity__gte=1), name="orders_orderitem_quantity_min_one"),
        ]

    def __str__(self):
        return f"{self.quantity} x {self.name}"

    @property
    def line_total(self):
        return self.unit_price * self.quantity


class OrderStatusEvent(TimeStampedModel):
    """One row per status change; powers the order tracking timeline."""

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="status_history")
    status = models.CharField(max_length=20, choices=Order.Status.choices)
    note = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["created_at", "id"]
        indexes = [models.Index(fields=["order", "created_at"])]

    def __str__(self):
        return f"{self.order} -> {self.status}"