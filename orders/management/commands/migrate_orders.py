"""
Production-grade ETL migration command for migrating legacy orders.

This command implements a robust, memory-efficient, resumable, and idempotent
data migration pipeline using:
- iterator() for memory-efficient queryset traversal
- bulk_create() for high-performance batch inserts
- transaction.atomic() for data integrity guarantees
- tracemalloc for memory profiling

Usage:
    python manage.py migrate_orders
    python manage.py migrate_orders --batch-size=5000
    python manage.py migrate_orders --dry-run
    python manage.py migrate_orders --start-from=legacy-050001
"""

import time
import tracemalloc
from decimal import Decimal, InvalidOperation

from django.core.management.base import BaseCommand
from django.db import connection, transaction

from orders.models import LegacyOrder, Order, OrderLine


class Command(BaseCommand):
    """
    Production-grade migration of legacy orders to normalized schema.

    Features:
    - Memory-efficient iteration via QuerySet.iterator()
    - Batch processing with configurable batch size
    - Atomic transactions per batch for data integrity
    - Idempotent: only processes unmigrated records
    - Resumable via --start-from flag
    - Dry-run mode for safe previewing
    - Progress and summary reporting with throughput metrics
    """

    help = (
        "Migrate legacy order records to the normalized Order/OrderLine schema. "
        "Supports --batch-size, --dry-run, and --start-from options."
    )

    def add_arguments(self, parser):
        """Define command-line arguments."""
        parser.add_argument(
            "--batch-size",
            type=int,
            default=1000,
            help="Number of records to process per batch (default: 1000).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Preview the migration without making any database changes.",
        )
        parser.add_argument(
            "--start-from",
            type=str,
            default=None,
            help=(
                "Resume migration from this external_id (inclusive). "
                "Useful for resuming after a failure."
            ),
        )

    def handle(self, *args, **options):
        """Execute the production-grade migration pipeline."""
        batch_size = options["batch_size"]
        dry_run = options["dry_run"]
        start_from = options["start_from"]

        # Header
        self.stdout.write("=" * 70)
        self.stdout.write(
            self.style.HTTP_INFO("  PRODUCTION ETL MIGRATION PIPELINE")
        )
        self.stdout.write("=" * 70)
        self.stdout.write(f"  Batch size:  {batch_size:,}")
        self.stdout.write(f"  Dry run:     {dry_run}")
        self.stdout.write(f"  Start from:  {start_from or '(beginning)'}")
        self.stdout.write("=" * 70 + "\n")

        # Build the base queryset
        queryset = (
            LegacyOrder.objects
            .filter(migrated=False)
            .order_by("external_id")
        )

        if start_from:
            queryset = queryset.filter(external_id__gte=start_from)

        # Count total records to process
        total_pending = queryset.count()
        if total_pending == 0:
            self.stdout.write(
                self.style.SUCCESS(
                    "No unmigrated records found. Migration is already complete."
                )
            )
            return

        self.stdout.write(f"Found {total_pending:,} records pending migration.\n")

        # Start profiling
        tracemalloc.start()
        start_time = time.perf_counter()

        # Reset query log for counting (if DEBUG)
        if hasattr(connection, "queries_log"):
            connection.queries_log.clear()

        # Batch accumulators
        orders_to_create = []
        lines_to_create = []  # list of (external_id, OrderLine)
        processed_ids = []
        total_processed = 0
        total_orders_created = 0
        total_lines_created = 0
        batch_number = 0

        # Main processing loop with memory-efficient iterator
        for legacy_order in queryset.iterator(chunk_size=batch_size):
            raw_data = legacy_order.raw_data

            # --- TRANSFORM ---
            try:
                new_order = Order(
                    external_id=legacy_order.external_id,
                    customer_email=raw_data["customer_email"],
                    total_price=Decimal(raw_data["total"]),
                )
                orders_to_create.append(new_order)

                for item in raw_data.get("items", []):
                    line = OrderLine(
                        # Temporarily store None; will be linked after bulk_create
                        order=None,
                        sku=item["sku"],
                        quantity=int(item["quantity"]),
                        unit_price=Decimal(item["unit_price"]),
                    )
                    # Tag the line with its parent's external_id for later mapping
                    line._parent_external_id = legacy_order.external_id
                    lines_to_create.append(line)

                processed_ids.append(legacy_order.id)

            except (KeyError, InvalidOperation, ValueError, TypeError) as e:
                self.stdout.write(
                    self.style.ERROR(
                        f"Skipping {legacy_order.external_id}: "
                        f"data validation error - {e}"
                    )
                )
                continue

            # --- LOAD (when batch is full) ---
            if len(orders_to_create) >= batch_size:
                batch_number += 1
                orders_count, lines_count = self._process_batch(
                    orders_to_create,
                    lines_to_create,
                    processed_ids,
                    batch_number,
                    dry_run,
                )
                total_orders_created += orders_count
                total_lines_created += lines_count
                total_processed += len(orders_to_create)

                # Clear accumulators
                orders_to_create = []
                lines_to_create = []
                processed_ids = []

                # Progress report
                elapsed = time.perf_counter() - start_time
                rate = total_processed / elapsed if elapsed > 0 else 0
                self.stdout.write(
                    f"  Progress: {total_processed:>8,} / {total_pending:,} "
                    f"({total_processed * 100 / total_pending:.1f}%) "
                    f"[{rate:,.0f} records/sec]"
                )

        # Process remaining partial batch
        if orders_to_create:
            batch_number += 1
            orders_count, lines_count = self._process_batch(
                orders_to_create,
                lines_to_create,
                processed_ids,
                batch_number,
                dry_run,
            )
            total_orders_created += orders_count
            total_lines_created += lines_count
            total_processed += len(orders_to_create)

        # Collect profiling data
        elapsed = time.perf_counter() - start_time
        snapshot = tracemalloc.take_snapshot()
        tracemalloc.stop()

        top_stats = snapshot.statistics("lineno")
        peak_memory = sum(stat.size for stat in top_stats)

        # Query count (if DEBUG is enabled)
        query_count = len(connection.queries) if hasattr(connection, "queries") else "N/A"

        # Summary report
        self.stdout.write("\n" + "=" * 70)
        self.stdout.write(
            self.style.HTTP_INFO("  MIGRATION SUMMARY")
        )
        self.stdout.write("=" * 70)

        if dry_run:
            self.stdout.write(
                self.style.WARNING("  MODE: DRY RUN (no changes were made)")
            )

        self.stdout.write(f"  Records processed:    {total_processed:,}")
        self.stdout.write(f"  Orders created:       {total_orders_created:,}")
        self.stdout.write(f"  Order lines created:  {total_lines_created:,}")
        self.stdout.write(f"  Batches:              {batch_number:,}")
        self.stdout.write(f"  Total time:           {elapsed:.2f} seconds")

        if elapsed > 0 and total_processed > 0:
            throughput = total_processed / elapsed
            self.stdout.write(
                f"  Throughput:           {throughput:,.1f} records per second"
            )

        self.stdout.write(f"  Peak memory (traced): {peak_memory / 1024 / 1024:.2f} MB")
        self.stdout.write(f"  Total DB queries:     {query_count}")
        self.stdout.write("=" * 70)

        self.stdout.write(
            self.style.SUCCESS(
                f"\nMigration {'preview' if dry_run else 'completed'} successfully."
            )
        )

    def _process_batch(self, orders, lines, legacy_ids, batch_number, dry_run):
        """
        Process a single batch of orders within an atomic transaction.

        Args:
            orders: List of unsaved Order instances.
            lines: List of unsaved OrderLine instances with _parent_external_id.
            legacy_ids: List of LegacyOrder PKs to mark as migrated.
            batch_number: Current batch number for logging.
            dry_run: If True, skip database writes.

        Returns:
            Tuple of (orders_created_count, lines_created_count).
        """
        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"  [Dry Run] Batch {batch_number}: "
                    f"Would process {len(orders)} orders "
                    f"with {len(lines)} line items."
                )
            )
            return 0, 0

        try:
            with transaction.atomic():
                # Step 1: Bulk create Order records
                Order.objects.bulk_create(orders)

                # Step 2: Re-fetch created orders by external_id to get PKs
                # This is necessary because bulk_create may not return PKs
                # on all database backends.
                external_ids = [o.external_id for o in orders]
                created_orders = Order.objects.filter(
                    external_id__in=external_ids
                ).in_bulk(field_name="external_id")

                # Step 3: Link OrderLines to their parent Orders
                for line in lines:
                    parent_ext_id = line._parent_external_id
                    line.order = created_orders[parent_ext_id]

                # Step 4: Bulk create OrderLine records
                OrderLine.objects.bulk_create(lines)

                # Step 5: Mark legacy orders as migrated
                LegacyOrder.objects.filter(id__in=legacy_ids).update(migrated=True)

            self.stdout.write(
                self.style.SUCCESS(
                    f"  Successfully processed batch {batch_number}: "
                    f"{len(orders)} orders, {len(lines)} line items."
                )
            )
            return len(orders), len(lines)

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(
                    f"  ERROR in batch {batch_number}: {e}"
                )
            )
            # Re-raise to allow the caller to handle the failure
            raise
