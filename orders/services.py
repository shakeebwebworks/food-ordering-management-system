import secrets
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from accounts.models import Address
from payments.models import Payment

from .cart import CartError, add_item, build_summary, cart_items, get_cart
from .models import Order, OrderItem


@transaction.atomic
def place_order(user, data):
    """Turns the user's cart into an order, with its items and payment, then empties the cart."""
    cart = get_cart(user)
    items = cart_items(cart)
    if not items:
        raise CartError("Your cart is empty.", "empty")

    restaurant = items[0].food_item.restaurant
    if not restaurant.is_open:
        raise CartError(f"{restaurant.name} is closed right now.", "closed")
    for line in items:
        if not line.food_item.is_available:
            raise CartError(
                f"{line.food_item.name} is no longer available. Please remove it from your cart.", "unavailable"
            )

    # Prices are always worked out here on the server, never trusted from the browser
    summary = build_summary(items)
    if not summary["meets_minimum"]:
        raise CartError(f"The minimum order is \u20B9{summary['min_order_amount']:.0f}.", "minimum")

    saved = data.get("saved_address")
    if saved:
        contact_name, contact_phone, address_text = saved.recipient_name, saved.phone, saved.full_address
    else:
        draft = Address(
            user=user,
            recipient_name=data["contact_name"],
            phone=data["contact_phone"],
            line1=data["line1"],
            line2=data.get("line2", ""),
            landmark=data.get("landmark", ""),
            city=data["city"],
            state=data["state"],
            postal_code=data["postal_code"],
        )
        contact_name, contact_phone, address_text = draft.recipient_name, draft.phone, draft.full_address
        if data.get("save_address"):
            draft.is_default = not user.addresses.exists()
            draft.label = Address.Label.HOME if draft.is_default else Address.Label.OTHER
            draft.save()

    order = Order.objects.create(
        user=user,
        restaurant=restaurant,
        restaurant_name=restaurant.name,
        contact_name=contact_name,
        contact_phone=contact_phone,
        delivery_address=address_text,
        notes=data.get("notes", ""),
        subtotal=summary["subtotal"],
        delivery_fee=summary["delivery_fee"],
        tax=summary["tax"],
        discount=summary["discount"],
        total=summary["total"],
        estimated_delivery_at=timezone.now() + timedelta(minutes=restaurant.delivery_time_minutes),
    )

    OrderItem.objects.bulk_create(
        OrderItem(
            order=order,
            food_item=line.food_item,
            name=line.food_item.name,
            size_name=line.size.name if line.size else "",
            extras=[extra.name for extra in line.extras.all()],
            unit_price=line.unit_price,
            quantity=line.quantity,
        )
        for line in items
    )

    # DEMO PAYMENTS: no real payment gateway is connected yet. Card, UPI and net banking are
    # recorded as paid with a "SIM-" transaction id. Replace this block with a real gateway
    # (for example Razorpay) before taking real money.
    method = data["payment_method"]
    online = method != Payment.Method.COD
    Payment.objects.create(
        order=order,
        method=method,
        amount=order.total,
        status=Payment.Status.PAID if online else Payment.Status.PENDING,
        transaction_id=f"SIM-{secrets.token_hex(5).upper()}" if online else "",
        gateway_response={"simulated": True} if online else {},
        paid_at=timezone.now() if online else None,
    )

    cart.items.all().delete()
    return order


def reorder(user, order):
    """Puts a past order's items back in the cart. Returns (items added, names that were skipped)."""
    added, skipped = 0, []
    items = order.items.select_related("food_item").prefetch_related("food_item__sizes", "food_item__extras")

    for item in items:
        food = item.food_item
        if food is None:  # the food was deleted from the menu
            skipped.append(item.name)
            continue

        # Find today's size and extras with the same names as in the old order
        size_id = None
        if item.size_name:
            size_id = next((size.pk for size in food.sizes.all() if size.name == item.size_name), None)
            if size_id is None:
                skipped.append(item.name)
                continue
        extra_ids = [extra.pk for extra in food.extras.all() if extra.is_available and extra.name in item.extras]
        if len(extra_ids) != len(item.extras):
            skipped.append(item.name)
            continue

        try:
            # replace=True: a cart from another restaurant is replaced by this order's restaurant
            add_item(user, food.pk, size_id, extra_ids, item.quantity, replace=True)
        except CartError:
            skipped.append(item.name)
            continue
        added += 1

    return added, skipped