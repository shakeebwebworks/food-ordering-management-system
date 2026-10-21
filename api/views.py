from datetime import timedelta
from decimal import Decimal, InvalidOperation
from tracemalloc import start

from django.contrib.auth import get_user_model, login, logout
from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncDate
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import mixins, request, status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.forms import LoginForm, RegisterForm
from menu.models import Category, FoodItem, Wishlist
from orders import cart as cart_service
from orders.cart import CartError
from orders.forms import CheckoutForm
from orders.models import Order, OrderItem
from orders.services import place_order
from orders.views import build_timeline
from restaurants.models import Restaurant
from reviews.models import Review

from .permissions import IsAdminOrReadOnly, IsOwnerOrStaff, IsStaff
from .serializers import (
    CartAddSerializer,
    CartUpdateSerializer,
    CategorySerializer,
    FoodItemDetailSerializer,
    FoodItemListSerializer,
    FoodItemWriteSerializer,
    OrderSerializer,
    RestaurantSerializer,
    ReviewSerializer,
    WishlistCreateSerializer,
    WishlistItemSerializer,
)

User = get_user_model()


def _number(value, cast):
    """Turns a query-string value into a number, or None when it isn't one."""
    try:
        return cast(value)
    except (TypeError, ValueError, InvalidOperation):
        return None


def _flag(value):
    return {"true": True, "1": True, "false": False, "0": False}.get(str(value).lower())


def _cart_error(error):
    code = {"different_restaurant": status.HTTP_409_CONFLICT, "not_found": status.HTTP_404_NOT_FOUND}
    return Response(
        {"detail": error.message, "code": error.code},
        status=code.get(error.code, status.HTTP_400_BAD_REQUEST),
    )


# ======================= Authentication =======================

@method_decorator(ensure_csrf_cookie, name="dispatch")
class CsrfView(APIView):
    """Call once before a POST/PATCH/DELETE: it sets the csrftoken cookie to send back as X-CSRFToken."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        return Response({"detail": "CSRF cookie set."})


def _user_data(user):
    profile = getattr(user, "profile", None)
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "phone": profile.phone if profile else "",
        "is_staff": user.is_staff,
    }


class RegisterAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        form = RegisterForm(request.data)
        if not form.is_valid():
            return Response({"errors": form.errors}, status=status.HTTP_400_BAD_REQUEST)
        user = form.save()
        login(request._request, user)
        return Response(_user_data(user), status=status.HTTP_201_CREATED)


class LoginAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        form = LoginForm(request=request._request, data=request.data)
        if not form.is_valid():
            return Response({"errors": form.errors}, status=status.HTTP_400_BAD_REQUEST)
        user = form.get_user()
        login(request._request, user)
        return Response(_user_data(user))


class LogoutAPIView(APIView):
    def post(self, request):
        logout(request._request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(_user_data(request.user))


# ======================= Catalogue =======================

class CategoryViewSet(viewsets.ModelViewSet):
    serializer_class = CategorySerializer
    permission_classes = [IsAdminOrReadOnly]
    lookup_field = "slug"
    pagination_class = None  # a short list, so no pages

    def get_queryset(self):
        queryset = Category.objects.all()
        return queryset if self.request.user.is_staff else queryset.filter(is_active=True)


class RestaurantViewSet(viewsets.ModelViewSet):
    """Filters: ?cuisine=slug &min_rating=4 &max_time=30 &price=1|2|3 &veg=true &open=true &search=text"""

    serializer_class = RestaurantSerializer
    permission_classes = [IsAdminOrReadOnly]
    lookup_field = "slug"
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ["name", "location", "city", "cuisines__name"]
    ordering_fields = ["avg_rating", "delivery_time_minutes", "delivery_fee", "name"]

    def get_queryset(self):
        queryset = Restaurant.objects.prefetch_related("cuisines")
        params = self.request.query_params

        if params.get("cuisine"):
            queryset = queryset.filter(cuisines__slug=params["cuisine"])
        if (rating := _number(params.get("min_rating"), Decimal)) is not None:
            queryset = queryset.filter(avg_rating__gte=rating)
        if (minutes := _number(params.get("max_time"), int)) is not None:
            queryset = queryset.filter(delivery_time_minutes__lte=minutes)
        if (price := _number(params.get("price"), int)) is not None:
            queryset = queryset.filter(price_range=price)
        if _flag(params.get("veg")):
            queryset = queryset.filter(is_veg_only=True)
        if _flag(params.get("open")):
            queryset = queryset.filter(is_open=True)
        return queryset.distinct()


class FoodItemViewSet(viewsets.ModelViewSet):
    """Filters: ?category=slug &restaurant=slug &veg=true|false &popular=true &available=true &search=text"""

    permission_classes = [IsAdminOrReadOnly]
    lookup_field = "slug"
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ["name", "description", "category__name", "restaurant__name"]
    ordering_fields = ["price", "avg_rating", "name", "created_at"]

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return FoodItemWriteSerializer
        return FoodItemDetailSerializer if self.action == "retrieve" else FoodItemListSerializer

    def get_queryset(self):
        queryset = FoodItem.objects.select_related("restaurant", "category").prefetch_related("images")
        if self.action == "retrieve":
            queryset = queryset.prefetch_related("sizes", "extras")
        params = self.request.query_params

        if params.get("category"):
            queryset = queryset.filter(category__slug=params["category"])
        if params.get("restaurant"):
            queryset = queryset.filter(restaurant__slug=params["restaurant"])
        if (veg := _flag(params.get("veg"))) is not None:
            queryset = queryset.filter(is_veg=veg)
        if _flag(params.get("popular")):
            queryset = queryset.filter(is_popular=True)
        if _flag(params.get("available")):
            queryset = queryset.filter(is_available=True)
        return queryset


class SearchAPIView(APIView):
    """GET /api/search/?q=piz returns matching food, restaurants and categories."""

    permission_classes = [AllowAny]

    def get(self, request):
        query = request.query_params.get("q", "").strip()[:60]
        if len(query) < 2:
            return Response({"detail": "Type at least 2 letters.", "foods": [], "restaurants": [], "categories": []})

        foods = (
            FoodItem.objects.filter(is_available=True)
            .filter(
                Q(name__icontains=query)
                | Q(description__icontains=query)
                | Q(category__name__icontains=query)
                | Q(restaurant__name__icontains=query)
            )
            .select_related("restaurant", "category")
            .prefetch_related("images")
            .order_by("-is_popular", "name")[:5]
        )
        restaurants = (
            Restaurant.objects.filter(
                Q(name__icontains=query) | Q(location__icontains=query) | Q(cuisines__name__icontains=query)
            )
            .prefetch_related("cuisines")
            .distinct()
            .order_by("-is_open", "name")[:4]
        )
        categories = Category.objects.filter(is_active=True, name__icontains=query)[:4]

        context = {"request": request}
        return Response(
            {
                "query": query,
                "foods": FoodItemListSerializer(foods, many=True, context=context).data,
                "restaurants": RestaurantSerializer(restaurants, many=True, context=context).data,
                "categories": CategorySerializer(categories, many=True, context=context).data,
            }
        )


# ======================= Cart =======================

def _cart_data(request):
    items = cart_service.cart_items(cart_service.get_cart(request.user))
    summary = cart_service.build_summary(items)
    restaurant = summary["restaurant"]

    def image_url(food):
        picture = food.primary_image
        return request.build_absolute_uri(picture.image.url) if picture else None

    return {
        "restaurant": {"id": restaurant.id, "name": restaurant.name, "slug": restaurant.slug} if restaurant else None,
        "items": [
            {
                "id": line.pk,
                "food": {"id": line.food_item.id, "name": line.food_item.name, "slug": line.food_item.slug,
                         "image": image_url(line.food_item)},
                "size": line.size.name if line.size else None,
                "extras": [extra.name for extra in line.extras.all()],
                "unit_price": str(cart_service.money(line.unit_price)),
                "quantity": line.quantity,
                "line_total": str(cart_service.money(line.line_total)),
            }
            for line in items
        ],
        "count": summary["count"],
        "subtotal": str(summary["subtotal"]),
        "delivery_fee": str(summary["delivery_fee"]),
        "tax": str(summary["tax"]),
        "discount": str(summary["discount"]),
        "total": str(summary["total"]),
        "min_order_amount": str(summary["min_order_amount"]),
        "meets_minimum": summary["meets_minimum"],
    }


class CartAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(_cart_data(request))

    def delete(self, request):
        """Empties the cart."""
        cart_service.get_cart(request.user).items.all().delete()
        return Response(_cart_data(request))


class CartItemsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = CartAddSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            cart_service.add_item(
                request.user, data["food_id"], data.get("size_id"), data["extra_ids"],
                data["quantity"], data["replace"],
            )
        except CartError as error:
            return _cart_error(error)
        return Response(_cart_data(request), status=status.HTTP_201_CREATED)


class CartItemDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, item_id):
        serializer = CartUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            cart_service.update_quantity(request.user, item_id, serializer.validated_data["quantity"])
        except CartError as error:
            return _cart_error(error)
        return Response(_cart_data(request))

    def delete(self, request, item_id):
        try:
            cart_service.remove_item(request.user, item_id)
        except CartError as error:
            return _cart_error(error)
        return Response(_cart_data(request))


# ======================= Orders =======================

class OrderViewSet(
    mixins.CreateModelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    """Customers see their own orders. Staff see all orders. POST places an order from the cart."""

    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "order_number"
    lookup_value_regex = "[A-Za-z0-9]+"

    def get_queryset(self):
        queryset = (
            Order.objects.select_related("restaurant", "user")
            .prefetch_related("items", "payments", "status_history")
        )
        if not self.request.user.is_staff:
            queryset = queryset.filter(user=self.request.user)
        if status_filter := self.request.query_params.get("status"):
            queryset = queryset.filter(status=status_filter)
        if search := self.request.query_params.get("search"):
            queryset = queryset.filter(
                Q(order_number__icontains=search) | Q(restaurant_name__icontains=search)
                | Q(user__username__icontains=search)
            )
        return queryset

    def create(self, request, *args, **kwargs):
        form = CheckoutForm(request.data, user=request.user)  # same rules as the website checkout
        if not form.is_valid():
            return Response({"errors": form.errors}, status=status.HTTP_400_BAD_REQUEST)
        try:
            order = place_order(request.user, form.cleaned_data)
        except CartError as error:
            return _cart_error(error)
        order = self.get_queryset().get(pk=order.pk)
        return Response(self.get_serializer(order).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"])
    def tracking(self, request, order_number=None):
        order = self.get_object()
        timeline = build_timeline(order)
        return Response(
            {
                "order_number": order.order_number,
                "status": order.status,
                "status_display": order.get_status_display(),
                "message": timeline["message"],
                "final": timeline["final"],
                "cancelled": timeline["cancelled"],
                "estimated_delivery_at": order.estimated_delivery_at,
                "steps": timeline["steps"],
            }
        )

    @action(detail=True, methods=["post"])
    def cancel(self, request, order_number=None):
        order = self.get_object()
        if order.status not in (Order.Status.PLACED, Order.Status.CONFIRMED):
            return Response(
                {"detail": "This order can no longer be cancelled."}, status=status.HTTP_409_CONFLICT
            )
        order.update_status(Order.Status.CANCELLED, note="Cancelled by customer")
        return Response(self.get_serializer(order).data)

    @action(detail=True, methods=["post"], url_path="status", permission_classes=[IsStaff])
    def set_status(self, request, order_number=None):
        order = self.get_object()
        new_status = request.data.get("status")
        if new_status not in Order.Status.values:
            return Response(
                {"detail": f"Status must be one of: {', '.join(Order.Status.values)}."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        order.update_status(new_status, note=request.data.get("note", ""))
        return Response(self.get_serializer(order).data)


# ======================= Reviews =======================

class ReviewViewSet(viewsets.ModelViewSet):
    """Filters: ?food=<food id>. Reviews are written after delivery. Staff can hide any review."""

    serializer_class = ReviewSerializer
    permission_classes = [IsAuthenticatedOrReadOnly, IsOwnerOrStaff]

    def get_queryset(self):
        queryset = Review.objects.select_related("user", "food_item")
        if not self.request.user.is_staff:
            queryset = queryset.filter(is_approved=True)
        if (food := _number(self.request.query_params.get("food"), int)) is not None:
            queryset = queryset.filter(food_item_id=food)
        return queryset

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


# ======================= Wishlist =======================

class WishlistViewSet(
    mixins.ListModelMixin, mixins.CreateModelMixin, mixins.DestroyModelMixin, viewsets.GenericViewSet
):
    """GET lists saved food. POST {"food_id": 3} saves one. DELETE /api/wishlist/3/ removes it."""

    serializer_class = WishlistItemSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "food_item_id"
    lookup_url_kwarg = "food_id"

    def get_queryset(self):
        return (
            Wishlist.objects.filter(user=self.request.user)
            .select_related("food_item__restaurant", "food_item__category")
            .prefetch_related("food_item__images")
        )

    def create(self, request, *args, **kwargs):
        serializer = WishlistCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        food = get_object_or_404(FoodItem, pk=serializer.validated_data["food_id"])
        item, created = Wishlist.objects.get_or_create(user=request.user, food_item=food)
        return Response(
            self.get_serializer(item).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )
        

# ======================= Dashboard analytics (staff only) =======================

class DashboardAPIView(APIView):
    """GET /api/dashboard/?days=30 returns the numbers and chart data for the admin dashboard."""

    permission_classes = [IsStaff]

    def get(self, request):
        days = min(max(_number(request.query_params.get("days"), int) or 30, 1), 365)
        today = timezone.localdate()
        start = today - timedelta(days=days - 1)
        day_list = [start + timedelta(days=offset) for offset in range(days)]

        live_orders = Order.objects.exclude(status=Order.Status.CANCELLED)
        recent = live_orders.filter(created_at__date__gte=start)

        # Revenue and orders per day (days with no orders show as zero)
        per_day = {
            row["day"]: row
            for row in recent.annotate(day=TruncDate("created_at")).values("day")
            .annotate(revenue=Sum("total"), orders=Count("id"))
        }
        revenue = [per_day.get(day, {}).get("revenue") or Decimal("0") for day in day_list]
        orders = [per_day.get(day, {}).get("orders") or 0 for day in day_list]

        # Customers joined per day, and the running total
        joined = {
            row["day"]: row["count"]
            for row in User.objects.filter(is_staff=False, date_joined__date__gte=start)
            .annotate(day=TruncDate("date_joined")).values("day").annotate(count=Count("id"))
        }
        total_before = User.objects.filter(is_staff=False, date_joined__date__lt=start).count()
        growth, running = [], total_before
        for day in day_list:
            running += joined.get(day, 0)
            growth.append(running)

        sold = OrderItem.objects.exclude(order__status=Order.Status.CANCELLED)
        popular = sold.values("name").annotate(sold=Sum("quantity")).order_by("-sold", "name")[:5]
        by_category = (
            sold.filter(food_item__category__isnull=False)
            .values("food_item__category__name").annotate(sold=Sum("quantity")).order_by("-sold")
        )
        by_status = Order.objects.values("status").annotate(count=Count("id"))
        status_counts = {row["status"]: row["count"] for row in by_status}

        return Response(
            {
                "days": days,
                "totals": {
                    "revenue": live_orders.aggregate(total=Sum("total"))["total"] or Decimal("0"),
                    "orders": Order.objects.count(),
                    "customers": User.objects.filter(is_staff=False).count(),
                    "restaurants": Restaurant.objects.count(),
                    "products": FoodItem.objects.count(),
                    "pending_orders": Order.objects.filter(
                        status__in=[Order.Status.PLACED, Order.Status.CONFIRMED, Order.Status.PREPARING]
                    ).count(),
                },
                "charts": {
                    "labels": [day.isoformat() for day in day_list],
                    "revenue": revenue,
                    "orders": orders,
                    "customer_growth": growth,
                    "popular_foods": [{"name": row["name"], "sold": row["sold"]} for row in popular],
                    "orders_by_category": [
                        {"category": row["food_item__category__name"], "sold": row["sold"]} for row in by_category
                    ],
                    "status_distribution": [
                        {"status": value, "label": label, "count": status_counts.get(value, 0)}
                        for value, label in Order.Status.choices
                    ],
                },
            }
        )