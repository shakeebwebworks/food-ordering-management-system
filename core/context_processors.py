from django.db.models import Sum

from menu.models import Wishlist
from orders.models import CartItem


def wishlist(request):
    """Makes the logged-in user's saved food ids available on every page."""
    if not request.user.is_authenticated:
        return {"wishlist_ids": []}
    ids = Wishlist.objects.filter(user=request.user).values_list("food_item_id", flat=True)
    return {"wishlist_ids": list(ids)}


def cart(request):
    """Makes the number of items in the user's cart available on every page."""
    if not request.user.is_authenticated:
        return {"cart_count": 0}
    total = CartItem.objects.filter(cart__user=request.user).aggregate(total=Sum("quantity"))["total"]
    return {"cart_count": total or 0}