"""
Management command to seed the LegacyOrder table with 500,000 sample records.

Usage:
    python manage.py seed_legacy_data

This command generates realistic legacy order data with randomized customer
emails, varying numbers of line items (1-5), and realistic SKUs and prices.
It uses bulk_create for efficient insertion.
"""

import random
import string
import time
from decimal import Decimal

from django.core.management.base import BaseCommand

from orders.models import LegacyOrder


class Command(BaseCommand):
    """Seed the LegacyOrder table with 500,000 sample records."""

    help = "Seed the LegacyOrder table with 500,000 sample legacy order records."

    TOTAL_RECORDS = 500_000
    BATCH_SIZE = 5_000

    # Sample data pools for realistic generation
    FIRST_NAMES = [
        "alice", "bob", "charlie", "diana", "eve", "frank", "grace",
        "hank", "iris", "jack", "kate", "leo", "mia", "noah", "olivia",
        "paul", "quinn", "rachel", "sam", "tina", "uma", "victor",
        "wendy", "xander", "yara", "zane",
    ]
    DOMAINS = [
        "gmail.com", "yahoo.com", "outlook.com", "example.com",
        "company.org", "mail.net", "proton.me", "fastmail.com",
    ]
    SKU_PREFIXES = ["SKU", "PROD", "ITEM", "ART", "GDS"]
    SKU_SUFFIXES = list(string.ascii_uppercase)

    def handle(self, *args, **options):
        """Execute the seed command."""
        existing_count = LegacyOrder.objects.count()
        if existing_count >= self.TOTAL_RECORDS:
            self.stdout.write(
                self.style.WARNING(
                    f"LegacyOrder table already has {existing_count} records. "
                    "Skipping seed to maintain idempotency."
                )
            )
            return

        if existing_count > 0:
            self.stdout.write(
                self.style.WARNING(
                    f"Found {existing_count} existing records. "
                    "Clearing table before re-seeding."
                )
            )
            LegacyOrder.objects.all().delete()

        self.stdout.write(
            self.style.NOTICE(
                f"Seeding {self.TOTAL_RECORDS:,} legacy order records..."
            )
        )

        start_time = time.perf_counter()
        total_created = 0

        for batch_start in range(1, self.TOTAL_RECORDS + 1, self.BATCH_SIZE):
            batch_end = min(batch_start + self.BATCH_SIZE, self.TOTAL_RECORDS + 1)
            batch = []

            for i in range(batch_start, batch_end):
                external_id = f"legacy-{i:06d}"
                raw_data = self._generate_raw_data()
                batch.append(
                    LegacyOrder(
                        external_id=external_id,
                        raw_data=raw_data,
                        migrated=False,
                    )
                )

            LegacyOrder.objects.bulk_create(batch)
            total_created += len(batch)

            # Progress reporting every 10 batches
            if (total_created % (self.BATCH_SIZE * 10)) == 0 or total_created == self.TOTAL_RECORDS:
                elapsed = time.perf_counter() - start_time
                rate = total_created / elapsed if elapsed > 0 else 0
                self.stdout.write(
                    f"  Seeded {total_created:>8,} / {self.TOTAL_RECORDS:,} records "
                    f"({total_created * 100 / self.TOTAL_RECORDS:.1f}%) "
                    f"[{rate:,.0f} records/sec]"
                )

        elapsed = time.perf_counter() - start_time
        rate = self.TOTAL_RECORDS / elapsed if elapsed > 0 else 0

        self.stdout.write(
            self.style.SUCCESS(
                f"\nSuccessfully seeded {self.TOTAL_RECORDS:,} legacy order records "
                f"in {elapsed:.2f} seconds ({rate:,.0f} records/sec)."
            )
        )

    def _generate_raw_data(self):
        """Generate a realistic raw_data JSON structure for a legacy order."""
        customer_email = (
            f"{random.choice(self.FIRST_NAMES)}"
            f"{random.randint(1, 999)}@{random.choice(self.DOMAINS)}"
        )

        num_items = random.randint(1, 5)
        items = []
        total = Decimal("0.00")

        for _ in range(num_items):
            prefix = random.choice(self.SKU_PREFIXES)
            suffix = random.choice(self.SKU_SUFFIXES)
            sku_num = random.randint(100, 999)
            sku = f"{prefix}-{suffix}{sku_num}"

            quantity = random.randint(1, 10)
            unit_price = Decimal(str(round(random.uniform(5.99, 299.99), 2)))
            item_total = unit_price * quantity
            total += item_total

            items.append(
                {
                    "sku": sku,
                    "quantity": quantity,
                    "unit_price": str(unit_price),
                }
            )

        return {
            "customer_email": customer_email,
            "total": str(total.quantize(Decimal("0.01"))),
            "items": items,
        }
