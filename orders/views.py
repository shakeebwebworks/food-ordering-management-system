from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import DetailView, FormView, ListView, TemplateView

from . import cart as cart_service
from .cart import CartError, money
from .forms import CheckoutForm
from .models import Order
from .services import place_order, reorder


# The steps shown on the tracking page, in order
FLOW = [
    Order.Status.PLACED,
    Order.Status.CONFIRMED,
    Order.Status.PREPARING,
    Order.Status.OUT_FOR_DELIVERY,
    Order.Status.DELIVERED,
]

STATUS_MESSAGES = {
    Order.Status.PLACED: "We have received your order.",
    Order.Status.CONFIRMED: "The restaurant has confirmed your order.",
    Order.Status.PREPARING: "Your food is being prepared.",
    Order.Status.OUT_FOR_DELIVERY: "Your order is on its way to you.",
    Order.Status.DELIVERED: "Delivered. Enjoy your meal!",
    Order.Status.CANCELLED: "This order was cancelled.",
}


def build_timeline(order):
    """The tracking steps, each marked done, current or pending, with the time it was reached."""
    reached = {}
    for event in order.status_history.all():
        reached.setdefault(event.status, event.created_at)

    cancelled = order.status == Order.Status.CANCELLED
    current = None if cancelled else FLOW.index(order.status)

    steps = []
    for index, status in enumerate(FLOW):
        if cancelled:
            state = "done" if status in reached else "pending"
        elif index < current or status == Order.Status.DELIVERED and index == current:
            state = "done"
        elif index == current:
            state = "current"
        else:
            state = "pending"
        steps.append({"key": status.value, "label": status.label, "state": state, "time": reached.get(status)})

    return {
        "steps": steps,
        "cancelled": cancelled,
        "final": cancelled or order.status == Order.Status.DELIVERED,
        "message": STATUS_MESSAGES[order.status],
    }


class CartView(LoginRequiredMixin, TemplateView):
    template_name = "orders/cart.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        items = cart_service.cart_items(cart_service.get_cart(self.request.user))
        context["items"] = items
        context["summary"] = cart_service.build_summary(items)
        return context


class CheckoutView(LoginRequiredMixin, FormView):
    template_name = "orders/checkout.html"
    form_class = CheckoutForm

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            items = cart_service.cart_items(cart_service.get_cart(request.user))
            if not items:
                return redirect("orders:cart")
            if not cart_service.build_summary(items)["meets_minimum"]:
                return redirect("orders:cart")
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        items = cart_service.cart_items(cart_service.get_cart(self.request.user))
        addresses = list(self.request.user.addresses.all())

        if self.request.method == "POST":
            selected = self.request.POST.get("saved_address", "")
        else:
            selected = str(addresses[0].pk) if addresses else ""  # default address comes first

        context.update(
            items=items,
            summary=cart_service.build_summary(items),
            saved_addresses=addresses,
            selected_address=selected,
            selected_payment=self.request.POST.get("payment_method", "cod"),
        )
        return context

    def form_valid(self, form):
        try:
            order = place_order(self.request.user, form.cleaned_data)
        except CartError as error:
            form.add_error(None, error.message)
            return self.form_invalid(form)
        return redirect(reverse("orders:order_detail", args=[order.order_number]) + "?placed=1")


class OrderDetailView(LoginRequiredMixin, DetailView):
    """Order confirmation and live tracking. Customers can only open their own orders."""

    template_name = "orders/order_detail.html"
    context_object_name = "order"
    slug_field = "order_number"
    slug_url_kwarg = "order_number"

    def get_queryset(self):
        return (
            Order.objects.filter(user=self.request.user)
            .select_related("restaurant")
            .prefetch_related("items", "payments", "status_history")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        order = self.object
        context["timeline"] = build_timeline(order)
        context["payment"] = next(iter(order.payments.all()), None)
        context["just_placed"] = self.request.GET.get("placed") == "1"
        return context


class OrderListView(LoginRequiredMixin, ListView):
    """The customer's order history, newest first."""

    template_name = "orders/order_list.html"
    context_object_name = "orders"
    paginate_by = 8

    def get_queryset(self):
        return Order.objects.filter(user=self.request.user).prefetch_related("items", "payments")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["section"] = "orders"  # highlights "Orders" in the account menu
        return context


@login_required
@require_POST
def reorder_order(request, order_number):
    order = get_object_or_404(Order.objects.filter(user=request.user), order_number=order_number)
    added, skipped = reorder(request.user, order)

    if not added:
        messages.error(request, "None of these items can be ordered right now.")
        return redirect("orders:order_list")

    messages.success(request, f"{added} item{'s' if added != 1 else ''} added to your cart.")
    if skipped:
        messages.warning(request, "No longer available: " + ", ".join(skipped) + ".")
    return redirect("orders:cart")


# ---------- JSON endpoints used by the buttons on the site ----------

def api_login_required(view):
    """Like login_required, but answers with JSON so JavaScript can show a message."""

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse(
                {"ok": False, "code": "login_required", "message": "Please log in to use your cart."},
                status=401,
            )
        return view(request, *args, **kwargs)

    return wrapper


def _error(error):
    status = {"different_restaurant": 409, "not_found": 404}.get(error.code, 400)
    return JsonResponse({"ok": False, "code": error.code, "message": error.message}, status=status)


def _payload(user):
    """The current cart numbers, as text, for JavaScript to put on the page."""
    items = cart_service.cart_items(cart_service.get_cart(user))
    summary = cart_service.build_summary(items)
    return {
        "count": summary["count"],
        "lines": {
            str(line.pk): {"quantity": line.quantity, "line_total": str(money(line.line_total))}
            for line in items
        },
        "summary": {key: str(summary[key]) for key in ("subtotal", "delivery_fee", "tax", "discount", "total")},
        "meets_minimum": summary["meets_minimum"],
        "min_order_amount": str(summary["min_order_amount"]),
    }


@require_POST
@api_login_required
def cart_add(request):
    try:
        line = cart_service.add_item(
            request.user,
            food_id=request.POST.get("food_id"),
            size_id=request.POST.get("size"),
            extra_ids=request.POST.getlist("extras"),
            quantity=request.POST.get("quantity", 1),
            replace=request.POST.get("replace") == "1",
        )
    except CartError as error:
        return _error(error)
    return JsonResponse({"ok": True, "message": f"{line.food_item.name} added to cart", **_payload(request.user)})


@require_POST
@api_login_required
def cart_update(request, item_id):
    try:
        cart_service.update_quantity(request.user, item_id, request.POST.get("quantity"))
    except CartError as error:
        return _error(error)
    return JsonResponse({"ok": True, **_payload(request.user)})


@require_POST
@api_login_required
def cart_remove(request, item_id):
    try:
        cart_service.remove_item(request.user, item_id)
    except CartError as error:
        return _error(error)
    return JsonResponse({"ok": True, "message": "Item removed", **_payload(request.user)})


@api_login_required
def order_status(request, order_number):
    """Current tracking state of one of the user's orders, polled by the tracking page."""
    order = get_object_or_404(
        Order.objects.filter(user=request.user).prefetch_related("status_history"),
        order_number=order_number,
    )
    timeline = build_timeline(order)
    return JsonResponse(
        {
            "ok": True,
            "status": order.status,
            "label": order.get_status_display(),
            "message": timeline["message"],
            "final": timeline["final"],
            "cancelled": timeline["cancelled"],
            "steps": [
                {
                    "key": step["key"],
                    "state": step["state"],
                    "time": timezone.localtime(step["time"]).strftime("%I:%M %p").lstrip("0") if step["time"] else "",
                }
                for step in timeline["steps"]
            ],
        }
    )