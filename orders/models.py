"""
Data models for the ETL pipeline.

Defines three models:
- LegacyOrder: The source (denormalized) data with a JSONField.
- Order: The target normalized order table.
- OrderLine: Normalized line items linked to Order via ForeignKey.
"""

from django.db import models


class LegacyOrder(models.Model):
    """
    Represents a legacy order record with denormalized data stored as JSON.

    The `migrated` flag tracks whether this record has been successfully
    processed by the ETL pipeline. A composite index on (migrated, external_id)
    ensures efficient querying of unprocessed records in order.
    """

    external_id = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        help_text="Unique identifier from the legacy system.",
    )
    raw_data = models.JSONField(
        help_text="Denormalized order data in JSON format.",
    )
    migrated = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Whether this record has been migrated to the new schema.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(
                fields=["migrated", "external_id"],
                name="idx_legacy_migrated_extid",
            ),
        ]
        ordering = ["external_id"]
        verbose_name = "Legacy Order"
        verbose_name_plural = "Legacy Orders"

    def __str__(self):
        return f"LegacyOrder({self.external_id}, migrated={self.migrated})"


class Order(models.Model):
    """
    Normalized order model representing the target schema.

    Each Order corresponds to one LegacyOrder record and contains the
    top-level order information extracted from the legacy JSON data.
    """

    external_id = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        help_text="Unique identifier linking back to the legacy order.",
    )
    customer_email = models.EmailField(
        help_text="Customer email address.",
    )
    total_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Total order price.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["external_id"]
        verbose_name = "Order"
        verbose_name_plural = "Orders"

    def __str__(self):
        return f"Order({self.external_id}, {self.customer_email})"


class OrderLine(models.Model):
    """
    Normalized line item model linked to an Order.

    Each order can have multiple line items representing individual
    products in the order.
    """

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="lines",
        help_text="Parent order for this line item.",
    )
    sku = models.CharField(
        max_length=50,
        help_text="Stock Keeping Unit identifier.",
    )
    quantity = models.PositiveIntegerField(
        help_text="Number of units ordered.",
    )
    unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Price per unit.",
    )

    class Meta:
        verbose_name = "Order Line"
        verbose_name_plural = "Order Lines"

    def __str__(self):
        return f"OrderLine(order={self.order.external_id}, sku={self.sku})"
