from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from menu.models import Category, FoodExtra, FoodItem, FoodSize
from restaurants.models import Cuisine, Restaurant

# (name, Bootstrap icon, display order)
CATEGORIES = [
    ("Pizza", "bi-pie-chart-fill", 1),
    ("Burgers", "bi-egg-fried", 2),
    ("Indian", "bi-cup-hot", 3),
    ("Chinese", "bi-fire", 4),
    ("Desserts", "bi-cake2", 5),
    ("Beverages", "bi-cup-straw", 6),
    ("Healthy", "bi-heart-pulse", 7),
    ("Fast Food", "bi-lightning-charge", 8),
]

CUISINES = ["American", "Italian", "Indian", "Chinese", "Healthy"]

RESTAURANTS = [
    {
        "name": "Burger Hub", "cuisine": "American", "location": "Bandra West", "city": "Mumbai",
        "price_range": 1, "delivery_time_minutes": 25, "delivery_fee": "30", "min_order_amount": "0",
        "is_veg_only": False, "description": "Juicy burgers, crispy fries and cold coffee, made fresh to order.",
    },
    {
        "name": "Pizza Palace", "cuisine": "Italian", "location": "Andheri West", "city": "Mumbai",
        "price_range": 2, "delivery_time_minutes": 35, "delivery_fee": "0", "min_order_amount": "199",
        "is_veg_only": False, "description": "Stone-baked pizzas with fresh mozzarella and slow-cooked sauce.",
    },
    {
        "name": "Spice Route", "cuisine": "Indian", "location": "Powai", "city": "Mumbai",
        "price_range": 3, "delivery_time_minutes": 45, "delivery_fee": "49", "min_order_amount": "299",
        "is_veg_only": False, "description": "Slow-cooked North Indian classics and fragrant biryani.",
    },
    {
        "name": "Green Bowl", "cuisine": "Healthy", "location": "Juhu", "city": "Mumbai",
        "price_range": 2, "delivery_time_minutes": 30, "delivery_fee": "25", "min_order_amount": "0",
        "is_veg_only": True, "description": "Fresh, light and fully vegetarian bowls, toasts and smoothies.",
    },
    {
        "name": "Dragon Wok", "cuisine": "Chinese", "location": "Lower Parel", "city": "Mumbai",
        "price_range": 2, "delivery_time_minutes": 40, "delivery_fee": "35", "min_order_amount": "149",
        "is_veg_only": False, "description": "Wok-fired noodles, rice and street-style Indo-Chinese favourites.",
    },
]

BURGER_EXTRAS = [("Extra Cheese", "30"), ("Extra Sauce", "20")]
PIZZA_EXTRAS = [("Extra Cheese", "40"), ("Extra Toppings", "60")]
PIZZA_SIZES = [("Regular", "0", True), ("Large", "120", False)]
DRINK_SIZES = [("Regular", "0", True), ("Large", "40", False)]

# restaurant, category, name, description, price, veg, popular, ingredients, sizes, extras
FOODS = [
    ("Burger Hub", "Burgers", "Chicken Burger", "Juicy grilled chicken, fresh vegetables and signature sauce",
     "249", False, True, "Grilled chicken, Brioche bun, Lettuce, Tomato, Signature sauce", [], BURGER_EXTRAS),
    ("Burger Hub", "Burgers", "Veggie Burger", "Crispy veggie patty with fresh lettuce and creamy mayo",
     "199", True, False, "Veggie patty, Brioche bun, Lettuce, Onion, Mayo", [], BURGER_EXTRAS),
    ("Burger Hub", "Fast Food", "Cheese Fries", "Golden fries loaded with warm cheese sauce and herbs",
     "129", True, False, "Potato, Cheese sauce, Oregano, Chilli flakes", [], []),
    ("Burger Hub", "Beverages", "Cold Coffee", "Chilled creamy coffee blended with ice",
     "129", True, True, "Coffee, Milk, Ice, Sugar", DRINK_SIZES, []),

    ("Pizza Palace", "Pizza", "Margherita Pizza", "Classic tomato sauce, fresh mozzarella and basil",
     "299", True, True, "Pizza dough, Tomato sauce, Mozzarella, Basil, Olive oil", PIZZA_SIZES, PIZZA_EXTRAS),
    ("Pizza Palace", "Pizza", "Pepperoni Pizza", "Loaded with spicy pepperoni and melted cheese",
     "399", False, False, "Pizza dough, Tomato sauce, Mozzarella, Pepperoni", PIZZA_SIZES, PIZZA_EXTRAS),
    ("Pizza Palace", "Desserts", "Chocolate Brownie", "Warm fudgy brownie with a rich chocolate centre",
     "149", True, False, "Dark chocolate, Butter, Flour, Cocoa", [], []),
    ("Pizza Palace", "Beverages", "Fresh Lime Soda", "Sparkling lime soda, sweet, salted or mixed",
     "89", True, False, "Lime, Soda, Sugar, Salt, Mint", [], []),

    ("Spice Route", "Indian", "Butter Chicken", "Tender chicken in a creamy tomato and butter gravy",
     "349", False, True, "Chicken, Tomato, Butter, Cream, Kasuri methi", [], []),
    ("Spice Route", "Indian", "Paneer Tikka Masala", "Smoky paneer tikka simmered in a spiced onion gravy",
     "299", True, False, "Paneer, Onion, Tomato, Cream, Garam masala", [], []),
    ("Spice Route", "Indian", "Veg Biryani", "Fragrant basmati rice layered with vegetables and whole spices",
     "249", True, False, "Basmati rice, Mixed vegetables, Saffron, Mint, Whole spices", [], []),
    ("Spice Route", "Desserts", "Gulab Jamun", "Soft milk dumplings soaked in warm cardamom syrup",
     "99", True, False, "Khoya, Sugar syrup, Cardamom, Saffron", [], []),

    ("Green Bowl", "Healthy", "Quinoa Salad Bowl", "Quinoa, roasted vegetables, chickpeas and lemon dressing",
     "279", True, True, "Quinoa, Chickpeas, Cucumber, Cherry tomato, Lemon dressing", [], []),
    ("Green Bowl", "Healthy", "Avocado Toast", "Sourdough topped with smashed avocado, seeds and chilli",
     "199", True, False, "Sourdough, Avocado, Pumpkin seeds, Chilli flakes, Lime", [], []),
    ("Green Bowl", "Beverages", "Berry Smoothie", "Mixed berries blended with yoghurt and honey",
     "169", True, False, "Strawberry, Blueberry, Yoghurt, Honey", DRINK_SIZES, []),

    ("Dragon Wok", "Chinese", "Veg Hakka Noodles", "Wok-tossed noodles with crunchy vegetables and soy",
     "219", True, False, "Noodles, Cabbage, Carrot, Capsicum, Soy sauce", [], []),
    ("Dragon Wok", "Chinese", "Chicken Manchurian", "Crispy chicken in a tangy, garlicky Manchurian sauce",
     "299", False, True, "Chicken, Garlic, Spring onion, Soy sauce, Chilli", [], []),
    ("Dragon Wok", "Chinese", "Spring Rolls", "Crispy rolls filled with spiced vegetables, served with dip",
     "169", True, False, "Cabbage, Carrot, Spring roll sheet, Sweet chilli dip", [], []),
]


class Command(BaseCommand):
    help = "Adds demo categories, restaurants and food so the site has something to show. Safe to run again."

    @transaction.atomic
    def handle(self, *args, **options):
        categories = {}
        for name, icon, order in CATEGORIES:
            categories[name], _ = Category.objects.get_or_create(
                name=name, defaults={"icon": icon, "display_order": order}
            )

        cuisines = {name: Cuisine.objects.get_or_create(name=name)[0] for name in CUISINES}

        restaurants = {}
        for data in RESTAURANTS:
            data = dict(data)
            name, cuisine = data.pop("name"), data.pop("cuisine")
            restaurants[name], created = Restaurant.objects.get_or_create(name=name, defaults=data)
            if created:
                restaurants[name].cuisines.add(cuisines[cuisine])

        added = 0
        for restaurant, category, name, description, price, veg, popular, ingredients, sizes, extras in FOODS:
            food, created = FoodItem.objects.get_or_create(
                restaurant=restaurants[restaurant], name=name,
                defaults={
                    "category": categories[category], "description": description, "price": Decimal(price),
                    "is_veg": veg, "is_popular": popular, "ingredients": ingredients,
                },
            )
            if not created:
                continue
            added += 1
            for size_name, delta, default in sizes:
                FoodSize.objects.create(food_item=food, name=size_name, price_delta=Decimal(delta), is_default=default)
            for extra_name, extra_price in extras:
                FoodExtra.objects.create(food_item=food, name=extra_name, price=Decimal(extra_price))

        self.stdout.write(self.style.SUCCESS(
            f"Done. {added} new food items added "
            f"({FoodItem.objects.count()} in total, {Restaurant.objects.count()} restaurants, "
            f"{Category.objects.count()} categories)."
        ))