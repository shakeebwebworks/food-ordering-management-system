from rest_framework import serializers

from menu.models import Category, FoodExtra, FoodImage, FoodItem, FoodSize, Wishlist
from orders.models import Order, OrderItem
from payments.models import Payment
from restaurants.models import Cuisine, Restaurant
from reviews.models import Review


# ---------- Catalogue ----------

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ("id", "name", "slug", "icon", "image", "display_order", "is_active")
        read_only_fields = ("slug",)


class CuisineSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cuisine
        fields = ("id", "name", "slug")


class RestaurantSerializer(serializers.ModelSerializer):
    cuisines = CuisineSerializer(many=True, read_only=True)
    cuisine_ids = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Cuisine.objects.all(), source="cuisines", write_only=True, required=False
    )
    price_range_display = serializers.CharField(source="get_price_range_display", read_only=True)

    class Meta:
        model = Restaurant
        fields = (
            "id", "name", "slug", "description", "image", "cuisines", "cuisine_ids", "location", "city",
            "price_range", "price_range_display", "delivery_time_minutes", "delivery_fee",
            "min_order_amount", "is_veg_only", "is_open", "avg_rating", "review_count",
        )
        read_only_fields = ("slug", "avg_rating", "review_count")


class RestaurantBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = Restaurant
        fields = ("id", "name", "slug", "is_open")


class FoodImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = FoodImage
        fields = ("id", "image", "alt_text", "is_primary")


class FoodSizeSerializer(serializers.ModelSerializer):
    class Meta:
        model = FoodSize
        fields = ("id", "name", "price_delta", "is_default")


class FoodExtraSerializer(serializers.ModelSerializer):
    class Meta:
        model = FoodExtra
        fields = ("id", "name", "price")


class FoodItemListSerializer(serializers.ModelSerializer):
    restaurant = RestaurantBriefSerializer(read_only=True)
    category = serializers.SlugRelatedField(slug_field="slug", read_only=True)
    category_name = serializers.CharField(source="category.name", read_only=True)
    image = serializers.SerializerMethodField()

    class Meta:
        model = FoodItem
        fields = (
            "id", "name", "slug", "description", "price", "is_veg", "is_available", "is_popular",
            "avg_rating", "review_count", "restaurant", "category", "category_name", "image",
        )

    def get_image(self, food):
        picture = food.primary_image  # uses prefetched images
        if picture is None:
            return None
        request = self.context.get("request")
        return request.build_absolute_uri(picture.image.url) if request else picture.image.url


class FoodItemDetailSerializer(FoodItemListSerializer):
    ingredients = serializers.ListField(source="ingredient_list", child=serializers.CharField(), read_only=True)
    images = FoodImageSerializer(many=True, read_only=True)
    sizes = FoodSizeSerializer(many=True, read_only=True)
    extras = serializers.SerializerMethodField()

    class Meta(FoodItemListSerializer.Meta):
        fields = FoodItemListSerializer.Meta.fields + ("ingredients", "images", "sizes", "extras")

    def get_extras(self, food):
        return FoodExtraSerializer([extra for extra in food.extras.all() if extra.is_available], many=True).data


class FoodItemWriteSerializer(serializers.ModelSerializer):
    """Used by staff to create and edit food."""

    class Meta:
        model = FoodItem
        fields = (
            "id", "restaurant", "category", "name", "slug", "description", "ingredients",
            "price", "is_veg", "is_available", "is_popular",
        )
        read_only_fields = ("slug",)


# ---------- Cart ----------

class CartAddSerializer(serializers.Serializer):
    food_id = serializers.IntegerField()
    size_id = serializers.IntegerField(required=False, allow_null=True)
    extra_ids = serializers.ListField(child=serializers.IntegerField(), required=False, default=list)
    quantity = serializers.IntegerField(min_value=1, max_value=20, default=1)
    replace = serializers.BooleanField(default=False)


class CartUpdateSerializer(serializers.Serializer):
    quantity = serializers.IntegerField(min_value=1, max_value=20)


# ---------- Orders ----------

class OrderItemSerializer(serializers.ModelSerializer):
    line_total = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = OrderItem
        fields = ("id", "name", "size_name", "extras", "unit_price", "quantity", "line_total")


class PaymentSerializer(serializers.ModelSerializer):
    method_display = serializers.CharField(source="get_method_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Payment
        fields = ("id", "method", "method_display", "status", "status_display", "amount", "transaction_id", "paid_at")


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    payments = PaymentSerializer(many=True, read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    customer = serializers.CharField(source="user.username", read_only=True, default=None)

    class Meta:
        model = Order
        fields = (
            "order_number", "status", "status_display", "customer", "restaurant_name", "contact_name",
            "contact_phone", "delivery_address", "notes", "subtotal", "delivery_fee", "tax", "discount",
            "total", "estimated_delivery_at", "created_at", "items", "payments",
        )
        read_only_fields = fields


# ---------- Reviews ----------

class ReviewSerializer(serializers.ModelSerializer):
    food = serializers.PrimaryKeyRelatedField(source="food_item", queryset=FoodItem.objects.all())
    food_name = serializers.CharField(source="food_item.name", read_only=True)
    username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = Review
        fields = ("id", "food", "food_name", "username", "rating", "comment", "is_approved", "created_at")
        read_only_fields = ("created_at",)

    def validate(self, attrs):
        request = self.context["request"]

        if not request.user.is_staff:
            attrs.pop("is_approved", None)  # only staff can hide or approve reviews

        if self.instance is not None:
            attrs.pop("food_item", None)  # a review can't be moved to another food
            return attrs

        food = attrs["food_item"]
        delivered = OrderItem.objects.filter(
            order__user=request.user, order__status=Order.Status.DELIVERED, food_item=food
        )
        if not delivered.exists():
            raise serializers.ValidationError("You can review a food after it has been delivered to you.")
        if Review.objects.filter(user=request.user, food_item=food).exists():
            raise serializers.ValidationError("You have already reviewed this food.")
        return attrs


# ---------- Wishlist ----------

class WishlistItemSerializer(serializers.ModelSerializer):
    food = FoodItemListSerializer(source="food_item", read_only=True)

    class Meta:
        model = Wishlist
        fields = ("id", "food", "created_at")


class WishlistCreateSerializer(serializers.Serializer):
    food_id = serializers.IntegerField()