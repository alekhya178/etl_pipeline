"""
Naive (unoptimized) migration command for benchmarking purposes.

This command deliberately uses inefficient patterns:
- Loads entire queryset into memory (no iterator())
- Creates records one-by-one (no bulk_create)
- Individual saves for each legacy record

Usage:
    python manage.py migrate_orders_naive [--limit N]

WARNING: This command is intentionally inefficient and should only be run
on small subsets of data for benchmarking comparison.
"""

import time
import tracemalloc
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import connection, transaction

from orders.models import LegacyOrder, Order, OrderLine


class Command(BaseCommand):
    """Naive migration command for benchmarking against the optimized version."""

    help = (
        "Run a naive (unoptimized) migration of legacy orders. "
        "For benchmarking purposes only. Use --limit to restrict record count."
    )

    def add_arguments(self, parser):
        """Define command-line arguments."""
        parser.add_argument(
            "--limit",
            type=int,
            default=1000,
            help="Maximum number of records to process (default: 1000).",
        )

    def handle(self, *args, **options):
        """Execute the naive migration."""
        limit = options["limit"]

        self.stdout.write(
            self.style.WARNING(
                f"Running NAIVE migration (limit={limit}). "
                "This is deliberately unoptimized for benchmarking."
            )
        )

        # Reset query log for counting
        connection.queries_log.clear()

        # Start memory tracking
        tracemalloc.start()
        start_time = time.perf_counter()

        # NAIVE PATTERN: Load all records into memory at once (no iterator)
        legacy_orders = LegacyOrder.objects.filter(migrated=False)[:limit]

        processed = 0
        for legacy_order in legacy_orders:
            raw_data = legacy_order.raw_data

            # NAIVE PATTERN: One-by-one create (no bulk_create)
            with transaction.atomic():
                order = Order.objects.create(
                    external_id=legacy_order.external_id,
                    customer_email=raw_data["customer_email"],
                    total_price=Decimal(raw_data["total"]),
                )

                for item in raw_data["items"]:
                    OrderLine.objects.create(
                        order=order,
                        sku=item["sku"],
                        quantity=item["quantity"],
                        unit_price=Decimal(item["unit_price"]),
                    )

                # NAIVE PATTERN: Individual save for each record
                legacy_order.migrated = True
                legacy_order.save()

            processed += 1
            if processed % 100 == 0:
                self.stdout.write(f"  Processed {processed}/{limit} records...")

        # Collect metrics
        elapsed = time.perf_counter() - start_time
        snapshot = tracemalloc.take_snapshot()
        tracemalloc.stop()

        # Memory stats
        top_stats = snapshot.statistics("lineno")
        peak_memory = sum(stat.size for stat in top_stats)

        # Query count
        query_count = len(connection.queries)

        # Report
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(self.style.WARNING("NAIVE MIGRATION BENCHMARK RESULTS"))
        self.stdout.write("=" * 60)
        self.stdout.write(f"Records processed:    {processed:,}")
        self.stdout.write(f"Total time:           {elapsed:.2f} seconds")
        self.stdout.write(
            f"Throughput:           {processed / elapsed:,.1f} records per second"
            if elapsed > 0
            else "Throughput:           N/A"
        )
        self.stdout.write(f"Peak memory (traced): {peak_memory / 1024 / 1024:.2f} MB")
        self.stdout.write(f"Total DB queries:     {query_count:,}")
        self.stdout.write(
            f"Queries per record:   {query_count / processed:.1f}"
            if processed > 0
            else "Queries per record:   N/A"
        )
        self.stdout.write("=" * 60)

        self.stdout.write(
            self.style.SUCCESS(
                f"\nNaive migration completed: {processed} records in {elapsed:.2f}s."
            )
        )
