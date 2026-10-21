from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.db import transaction

from menu.models import FoodItem

from .models import Cart, CartItem

MAX_QUANTITY = 20
CENT = Decimal("0.01")


class CartError(Exception):
    """A cart problem with a message that is safe to show to the user."""

    def __init__(self, message, code="invalid"):
        super().__init__(message)
        self.message = message
        self.code = code


def money(value):
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


def _to_int(value, message):
    try:
        return int(value)
    except (TypeError, ValueError):
        raise CartError(message)


def get_cart(user):
    cart, _ = Cart.objects.get_or_create(user=user)
    return cart


def cart_items(cart):
    """Cart lines with everything the cart page needs, loaded in a few queries."""
    return list(
        cart.items
        .select_related("food_item__restaurant", "size")
        .prefetch_related("extras", "food_item__images")
    )


def item_count(user):
    cart = Cart.objects.filter(user=user).first()
    if cart is None:
        return 0
    return sum(cart.items.values_list("quantity", flat=True))


@transaction.atomic
def add_item(user, food_id, size_id=None, extra_ids=(), quantity=1, replace=False):
    quantity = _to_int(quantity, "Please choose a valid quantity.")
    if not 1 <= quantity <= MAX_QUANTITY:
        raise CartError(f"You can order 1 to {MAX_QUANTITY} of an item.")

    food = (
        FoodItem.objects.select_related("restaurant")
        .prefetch_related("sizes", "extras")
        .filter(pk=_to_int(food_id, "This food could not be found."))
        .first()
    )
    if food is None:
        raise CartError("This food could not be found.", "not_found")
    if not food.is_available:
        raise CartError(f"{food.name} is currently unavailable.", "unavailable")
    if not food.restaurant.is_open:
        raise CartError(f"{food.restaurant.name} is closed right now.", "closed")

    # Size: use the chosen one, otherwise the default (or first) size, if the food has sizes
    sizes = list(food.sizes.all())
    size = None
    if sizes:
        if size_id not in (None, ""):
            wanted = _to_int(size_id, "Please choose a valid size.")
            size = next((s for s in sizes if s.pk == wanted), None)
            if size is None:
                raise CartError("Please choose a valid size.")
        else:
            size = next((s for s in sizes if s.is_default), sizes[0])

    # Extras: every id must be an available extra of this food
    available = {extra.pk: extra for extra in food.extras.all() if extra.is_available}
    chosen = []
    for raw in set(extra_ids):
        extra = available.get(_to_int(raw, "One of the extras is not available."))
        if extra is None:
            raise CartError("One of the extras is not available.")
        chosen.append(extra)

    cart = get_cart(user)

    # One restaurant per cart
    existing = cart.items.select_related("food_item").first()
    if existing and existing.food_item.restaurant_id != food.restaurant_id:
        if not replace:
            raise CartError(
                "Your cart has food from another restaurant. Start a new cart?", "different_restaurant"
            )
        cart.items.all().delete()

    # The same food with the same options becomes one line with a bigger quantity
    wanted_extras = {extra.pk for extra in chosen}
    for line in cart.items.filter(food_item=food, size=size).prefetch_related("extras"):
        if {extra.pk for extra in line.extras.all()} == wanted_extras:
            line.quantity = min(MAX_QUANTITY, line.quantity + quantity)
            line.save(update_fields=["quantity", "updated_at"])
            return line

    line = CartItem.objects.create(cart=cart, food_item=food, size=size, quantity=quantity)
    line.extras.set(chosen)
    return line


def _get_line(user, item_id):
    line = CartItem.objects.filter(pk=item_id, cart__user=user).first()
    if line is None:
        raise CartError("This item is no longer in your cart.", "not_found")
    return line


def update_quantity(user, item_id, quantity):
    quantity = _to_int(quantity, "Please choose a valid quantity.")
    line = _get_line(user, item_id)
    if quantity < 1:
        line.delete()
        return
    if quantity > MAX_QUANTITY:
        raise CartError(f"You can order 1 to {MAX_QUANTITY} of an item.")
    line.quantity = quantity
    line.save(update_fields=["quantity", "updated_at"])


def remove_item(user, item_id):
    _get_line(user, item_id).delete()


def build_summary(items, coupon=None):
    """Subtotal, delivery fee, tax, discount and total for a list of cart lines."""
    subtotal = sum((line.line_total for line in items), Decimal("0"))
    restaurant = items[0].food_item.restaurant if items else None

    delivery_fee = restaurant.delivery_fee if restaurant else Decimal("0")
    discount = Decimal("0")
    if coupon is not None and coupon.get_error(subtotal) is None:
        discount = coupon.discount_for(subtotal)

    tax = money((subtotal - discount) * settings.TAX_RATE)
    minimum = restaurant.min_order_amount if restaurant else Decimal("0")

    return {
        "restaurant": restaurant,
        "subtotal": money(subtotal),
        "delivery_fee": money(delivery_fee),
        "tax": tax,
        "discount": money(discount),
        "total": money(subtotal - discount + delivery_fee + tax),
        "min_order_amount": money(minimum),
        "meets_minimum": subtotal >= minimum,
        "count": sum(line.quantity for line in items),
    }