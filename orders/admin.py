"""Admin registration for orders app models."""

from django.contrib import admin

from .models import LegacyOrder, Order, OrderLine


@admin.register(LegacyOrder)
class LegacyOrderAdmin(admin.ModelAdmin):
    """Admin interface for LegacyOrder."""

    list_display = ("external_id", "migrated", "created_at")
    list_filter = ("migrated",)
    search_fields = ("external_id",)
    readonly_fields = ("created_at",)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    """Admin interface for Order."""

    list_display = ("external_id", "customer_email", "total_price", "created_at")
    search_fields = ("external_id", "customer_email")
    readonly_fields = ("created_at",)


@admin.register(OrderLine)
class OrderLineAdmin(admin.ModelAdmin):
    """Admin interface for OrderLine."""

    list_display = ("order", "sku", "quantity", "unit_price")
    search_fields = ("sku",)
    list_filter = ("sku",)
