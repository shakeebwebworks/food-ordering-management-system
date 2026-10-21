from django.contrib import messages
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.db.models.deletion import ProtectedError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, ListView, TemplateView, UpdateView

from menu.models import Category, FoodItem
from orders.models import Order
from payments.models import Payment
from restaurants.models import Cuisine, Restaurant
from reviews.models import Review

from .forms import (
    CategoryForm,
    CuisineForm,
    FoodExtraFormSet,
    FoodForm,
    FoodImageFormSet,
    FoodSizeFormSet,
    OrderStatusForm,
    RestaurantForm,
)
from .mixins import StaffRequiredMixin, staff_required

User = get_user_model()


# ======================= What each management page shows =======================

class Action:
    """A button on a table row that changes the record (for example: Approve, Refund)."""

    def __init__(self, name, label, run, visible=lambda obj: True, confirm="", danger=False):
        self.name, self.label, self.run = name, label, run
        self.visible, self.confirm, self.danger = visible, confirm, danger


class Resource:
    def __init__(
        self, key, singular, plural, model, queryset, columns, icon, search_fields=(), filters=(),
        form_class=None, actions=(), deletable=False, detail_url=None, search_hint="Search",
    ):
        self.key, self.singular, self.plural, self.model = key, singular, plural, model
        self.queryset, self.columns, self.icon = queryset, columns, icon
        self.search_fields, self.filters, self.actions = search_fields, filters, actions
        self.form_class, self.deletable, self.detail_url = form_class, deletable, detail_url
        self.search_hint = search_hint

    @property
    def has_form(self):
        return self.form_class is not None or self.key == "foods"


def _approve(review):
    review.is_approved = True
    review.save(update_fields=["is_approved", "updated_at"])  # save() keeps the ratings up to date
    return "Review approved."


def _hide(review):
    review.is_approved = False
    review.save(update_fields=["is_approved", "updated_at"])
    return "Review hidden from the site."


def _mark_paid(payment):
    payment.status = Payment.Status.PAID
    payment.paid_at = timezone.now()
    payment.save(update_fields=["status", "paid_at", "updated_at"])
    return "Payment marked as paid."


def _refund(payment):
    payment.status = Payment.Status.REFUNDED
    payment.save(update_fields=["status", "updated_at"])
    return "Payment marked as refunded."


def _set_active(value):
    def run(user):
        user.is_active = value
        user.save(update_fields=["is_active"])
        return "Customer account enabled." if value else "Customer account disabled."

    return run


def _category_choices():
    return [(category.pk, category.name) for category in Category.objects.all()]


RESOURCES = {
    "orders": Resource(
        "orders", "order", "Orders", Order,
        queryset=lambda: Order.objects.select_related("user"),
        icon="bi-receipt",
        columns=[
            {"label": "Order", "key": "order_number", "kind": "link"},
            {"label": "Customer", "key": "user.username"},
            {"label": "Restaurant", "key": "restaurant_name"},
            {"label": "Total", "key": "total", "kind": "money"},
            {"label": "Status", "key": "get_status_display", "kind": "badge", "badge_key": "status"},
            {"label": "Placed", "key": "created_at", "kind": "datetime"},
        ],
        search_fields=("order_number", "user__username", "restaurant_name", "contact_phone"),
        search_hint="Search order, customer or restaurant",
        filters=[{"param": "status", "field": "status", "label": "All statuses", "choices": lambda: Order.Status.choices}],
        detail_url="dashboard:order_detail",
    ),
    "restaurants": Resource(
        "restaurants", "restaurant", "Restaurants", Restaurant,
        queryset=lambda: Restaurant.objects.all(),
        icon="bi-shop",
        columns=[
            {"label": "Name", "key": "name", "kind": "link"},
            {"label": "City", "key": "city"},
            {"label": "Price", "key": "get_price_range_display"},
            {"label": "Delivery", "key": "delivery_time_minutes", "kind": "minutes"},
            {"label": "Rating", "key": "avg_rating", "kind": "rating"},
            {"label": "Open", "key": "is_open", "kind": "bool"},
        ],
        search_fields=("name", "location", "city"),
        filters=[{"param": "open", "field": "is_open", "label": "Open or closed", "choices": lambda: [("1", "Open"), ("0", "Closed")]}],
        form_class=RestaurantForm, deletable=True,
    ),
    "foods": Resource(
        "foods", "food item", "Food items", FoodItem,
        queryset=lambda: FoodItem.objects.select_related("restaurant", "category"),
        icon="bi-egg-fried",
        columns=[
            {"label": "Name", "key": "name", "kind": "link"},
            {"label": "Restaurant", "key": "restaurant.name"},
            {"label": "Category", "key": "category.name"},
            {"label": "Price", "key": "price", "kind": "money"},
            {"label": "Veg", "key": "is_veg", "kind": "bool"},
            {"label": "Available", "key": "is_available", "kind": "bool"},
        ],
        search_fields=("name", "restaurant__name", "category__name"),
        filters=[
            {"param": "category", "field": "category_id", "label": "All categories", "choices": _category_choices},
            {"param": "available", "field": "is_available", "label": "Availability", "choices": lambda: [("1", "Available"), ("0", "Unavailable")]},
        ],
        deletable=True,
    ),
    "categories": Resource(
        "categories", "category", "Categories", Category,
        queryset=lambda: Category.objects.annotate(food_count=Count("food_items")).order_by("display_order", "name"),
        icon="bi-grid",
        columns=[
            {"label": "Name", "key": "name", "kind": "link"},
            {"label": "Icon", "key": "icon"},
            {"label": "Order", "key": "display_order"},
            {"label": "Foods", "key": "food_count"},
            {"label": "Active", "key": "is_active", "kind": "bool"},
        ],
        search_fields=("name",),
        form_class=CategoryForm, deletable=True,
    ),
    "cuisines": Resource(
        "cuisines", "cuisine", "Cuisines", Cuisine,
        queryset=lambda: Cuisine.objects.annotate(restaurant_count=Count("restaurants")).order_by("name"),
        icon="bi-globe2",
        columns=[
            {"label": "Name", "key": "name", "kind": "link"},
            {"label": "Restaurants", "key": "restaurant_count"},
        ],
        search_fields=("name",),
        form_class=CuisineForm, deletable=True,
    ),
    "customers": Resource(
        "customers", "customer", "Customers", User,
        queryset=lambda: User.objects.filter(is_staff=False).annotate(
            order_count=Count("orders", distinct=True),
            total_spent=Sum("orders__total", filter=~Q(orders__status=Order.Status.CANCELLED)),
        ).order_by("-date_joined"),
        icon="bi-people",
        columns=[
            {"label": "Username", "key": "username"},
            {"label": "Name", "key": "get_full_name"},
            {"label": "Email", "key": "email"},
            {"label": "Orders", "key": "order_count"},
            {"label": "Spent", "key": "total_spent", "kind": "money"},
            {"label": "Joined", "key": "date_joined", "kind": "date"},
            {"label": "Active", "key": "is_active", "kind": "bool"},
        ],
        search_fields=("username", "email", "first_name", "last_name"),
        search_hint="Search name, username or email",
        filters=[{"param": "active", "field": "is_active", "label": "Active or disabled", "choices": lambda: [("1", "Active"), ("0", "Disabled")]}],
        actions=[
            Action("disable", "Disable", _set_active(False), visible=lambda u: u.is_active,
                   confirm="This customer will not be able to log in.", danger=True),
            Action("enable", "Enable", _set_active(True), visible=lambda u: not u.is_active),
        ],
    ),
    "payments": Resource(
        "payments", "payment", "Payments", Payment,
        queryset=lambda: Payment.objects.select_related("order"),
        icon="bi-credit-card",
        columns=[
            {"label": "Order", "key": "order.order_number"},
            {"label": "Method", "key": "get_method_display"},
            {"label": "Status", "key": "get_status_display", "kind": "badge", "badge_key": "status"},
            {"label": "Amount", "key": "amount", "kind": "money"},
            {"label": "Transaction", "key": "transaction_id"},
            {"label": "Created", "key": "created_at", "kind": "datetime"},
        ],
        search_fields=("order__order_number", "transaction_id", "order__user__username"),
        search_hint="Search order or transaction",
        filters=[
            {"param": "status", "field": "status", "label": "All statuses", "choices": lambda: Payment.Status.choices},
            {"param": "method", "field": "method", "label": "All methods", "choices": lambda: Payment.Method.choices},
        ],
        actions=[
            Action("paid", "Mark paid", _mark_paid, visible=lambda p: p.status == Payment.Status.PENDING),
            Action("refund", "Refund", _refund, visible=lambda p: p.status == Payment.Status.PAID,
                   confirm="Mark this payment as refunded?", danger=True),
        ],
    ),
    "reviews": Resource(
        "reviews", "review", "Reviews", Review,
        queryset=lambda: Review.objects.select_related("user", "food_item"),
        icon="bi-chat-heart",
        columns=[
            {"label": "Food", "key": "food_item.name"},
            {"label": "Customer", "key": "user.username"},
            {"label": "Rating", "key": "rating", "kind": "rating"},
            {"label": "Comment", "key": "comment", "kind": "text"},
            {"label": "Visible", "key": "is_approved", "kind": "bool"},
            {"label": "Date", "key": "created_at", "kind": "date"},
        ],
        search_fields=("food_item__name", "user__username", "comment"),
        filters=[
            {"param": "visible", "field": "is_approved", "label": "Visible or hidden", "choices": lambda: [("1", "Visible"), ("0", "Hidden")]},
            {"param": "rating", "field": "rating", "label": "Any rating", "choices": lambda: [(n, f"{n} stars") for n in range(5, 0, -1)]},
        ],
        actions=[
            Action("approve", "Approve", _approve, visible=lambda r: not r.is_approved),
            Action("hide", "Hide", _hide, visible=lambda r: r.is_approved, confirm="Hide this review from the site?"),
        ],
        deletable=True,
    ),
}


def get_resource(key):
    try:
        return RESOURCES[key]
    except KeyError:
        raise Http404("Unknown page")


# ======================= Overview (the charts load from /api/dashboard/) =======================

class OverviewView(StaffRequiredMixin, TemplateView):
    template_name = "dashboard/overview.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active"] = "overview"
        context["recent_orders"] = Order.objects.select_related("user")[:6]
        return context


# ======================= List page (search, filters, pages) =======================

class ResourceListView(StaffRequiredMixin, ListView):
    template_name = "dashboard/list.html"
    paginate_by = 12
    context_object_name = "page_items"
    resource = None  # set in urls.py

    def get_queryset(self):
        resource, params = self.resource, self.request.GET
        queryset = resource.queryset()

        query = params.get("q", "").strip()
        if query and resource.search_fields:
            condition = Q()
            for field in resource.search_fields:
                condition |= Q(**{f"{field}__icontains": query})
            queryset = queryset.filter(condition)

        for option in resource.filters:
            value = params.get(option["param"], "")
            if value:
                queryset = queryset.filter(**{option["field"]: value})
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        resource, params = self.resource, self.request.GET

        rows = [
            {"obj": obj, "actions": [action for action in resource.actions if action.visible(obj)]}
            for obj in context["page_obj"].object_list
        ]
        filters = [
            {
                "param": option["param"],
                "label": option["label"],
                "choices": [(str(value), label) for value, label in option["choices"]()],
                "selected": params.get(option["param"], ""),
            }
            for option in resource.filters
        ]
        other_params = params.copy()
        other_params.pop("page", None)

        context.update(
            resource=resource, active=resource.key, rows=rows, filters=filters,
            query=params.get("q", "").strip(), query_string=other_params.urlencode(),
            has_filters=bool(other_params),
        )
        return context


# ======================= Add and edit (simple forms) =======================

class ResourceFormMixin(StaffRequiredMixin):
    template_name = "dashboard/form.html"
    resource = None

    def get_form_class(self):
        return self.resource.form_class

    def get_success_url(self):
        return reverse(f"dashboard:{self.resource.key}_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(resource=self.resource, active=self.resource.key)
        return context


class ResourceCreateView(ResourceFormMixin, CreateView):
    def get_queryset(self):
        return self.resource.model.objects.all()

    def form_valid(self, form):
        messages.success(self.request, f"{self.resource.singular.capitalize()} added.")
        return super().form_valid(form)


class ResourceUpdateView(ResourceFormMixin, UpdateView):
    def get_queryset(self):
        return self.resource.model.objects.all()

    def form_valid(self, form):
        messages.success(self.request, f"{self.resource.singular.capitalize()} saved.")
        return super().form_valid(form)


# ======================= Food: the form plus photos, sizes and extras =======================

class FoodEditView(StaffRequiredMixin, View):
    resource = RESOURCES["foods"]

    def get_object(self):
        pk = self.kwargs.get("pk")
        return get_object_or_404(FoodItem, pk=pk) if pk else None

    @staticmethod
    def build_formsets(food, request=None):
        data = request.POST if request else None
        files = request.FILES if request else None
        return {
            "images": FoodImageFormSet(data, files, instance=food, prefix="images"),
            "sizes": FoodSizeFormSet(data, instance=food, prefix="sizes"),
            "extras": FoodExtraFormSet(data, instance=food, prefix="extras"),
        }

    def show(self, request, food, form, formsets):
        return render(request, "dashboard/food_form.html", {
            "resource": self.resource, "active": "foods", "food": food, "form": form, "formsets": formsets,
        })

    def get(self, request, pk=None):
        food = self.get_object()
        return self.show(request, food, FoodForm(instance=food), self.build_formsets(food))

    def post(self, request, pk=None):
        food = self.get_object()
        form = FoodForm(request.POST, instance=food)
        formsets = self.build_formsets(food, request)

        if form.is_valid() and all(formset.is_valid() for formset in formsets.values()):
            with transaction.atomic():
                saved = form.save()
                for formset in formsets.values():
                    formset.instance = saved
                    formset.save()
            messages.success(request, "Food item saved.")
            return redirect("dashboard:foods_list")
        return self.show(request, food, form, formsets)


# ======================= Delete and row buttons =======================

@staff_required
@require_POST
def resource_delete(request, key, pk):
    resource = get_resource(key)
    if not resource.deletable:
        raise Http404
    obj = get_object_or_404(resource.model, pk=pk)
    try:
        obj.delete()
        messages.success(request, f"{resource.singular.capitalize()} deleted.")
    except ProtectedError:
        messages.error(request, f"This {resource.singular} can't be deleted because other records still use it.")
    return redirect("dashboard:%s_list" % key)


@staff_required
@require_POST
def resource_action(request, key, pk, name):
    resource = get_resource(key)
    action = next((item for item in resource.actions if item.name == name), None)
    if action is None:
        raise Http404
    obj = get_object_or_404(resource.queryset(), pk=pk)
    if not action.visible(obj):
        messages.error(request, "That action is not available for this record.")
    else:
        messages.success(request, action.run(obj))
    return redirect("dashboard:%s_list" % key)


# ======================= One order: details and status =======================

class OrderDetailView(StaffRequiredMixin, View):
    def get_order(self, order_number):
        return get_object_or_404(
            Order.objects.select_related("user").prefetch_related("items", "payments", "status_history"),
            order_number=order_number,
        )

    def show(self, request, order, form):
        return render(request, "dashboard/order_detail.html", {
            "resource": RESOURCES["orders"], "active": "orders", "order": order, "form": form,
            "payments": order.payments.all(), "history": order.status_history.all(),
        })

    def get(self, request, order_number):
        order = self.get_order(order_number)
        return self.show(request, order, OrderStatusForm(initial={"status": order.status}))

    def post(self, request, order_number):
        order = self.get_order(order_number)
        form = OrderStatusForm(request.POST)
        if not form.is_valid():
            return self.show(request, order, form)

        new_status = form.cleaned_data["status"]
        if new_status == order.status:
            messages.info(request, "The order already has this status.")
        else:
            order.update_status(new_status, note=form.cleaned_data["note"])  # also updates the customer's tracking page
            messages.success(request, f"Order moved to {order.get_status_display()}.")
        return redirect("dashboard:order_detail", order_number=order.order_number)