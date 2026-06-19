# Production-Grade Django ETL Pipeline

A robust, memory-efficient, and resumable data migration pipeline built with Django management commands. This project demonstrates advanced Django ORM optimization techniques for handling large-scale data processing tasks.

## Overview

This project simulates a real-world ETL (Extract, Transform, Load) scenario: migrating **500,000 legacy order records** from a denormalized JSON format into a normalized relational database schema using PostgreSQL.

### Architecture

```
┌─────────────────────┐     ┌──────────────────────────────────────┐
│   LegacyOrder       │     │   Normalized Schema                  │
│  ┌───────────────┐  │     │  ┌──────────────┐                   │
│  │ external_id   │  │     │  │ Order         │                   │
│  │ raw_data (JSON│──┼────▶│  │ external_id   │                   │
│  │ migrated      │  │     │  │ customer_email│                   │
│  └───────────────┘  │     │  │ total_price   │                   │
│                     │     │  └──────┬───────┘                   │
│  500,000 records    │     │         │ 1:N                        │
│                     │     │  ┌──────▼───────┐                   │
│                     │     │  │ OrderLine     │                   │
│                     │     │  │ sku           │                   │
│                     │     │  │ quantity      │                   │
│                     │     │  │ unit_price    │                   │
│                     │     │  └──────────────┘                   │
└─────────────────────┘     └──────────────────────────────────────┘
```

### Key Features

- **Memory-efficient**: Uses `QuerySet.iterator()` to avoid loading entire tables into memory
- **High-performance**: Uses `bulk_create()` to minimize database round trips
- **Idempotent**: Safe to re-run; only processes unmigrated records
- **Resumable**: `--start-from` flag allows resuming from a specific point after failures
- **Atomic**: Each batch is wrapped in `transaction.atomic()` for data integrity
- **Configurable**: Adjustable batch size, dry-run mode, and resume point
- **Observable**: Real-time progress reporting and comprehensive summary metrics

## Tech Stack

- **Python** 3.12
- **Django** 5.1+
- **PostgreSQL** 16
- **Docker** & Docker Compose

## Quick Start

### Prerequisites

- Docker and Docker Compose installed on your system

### 1. Clone and Configure

```bash
git clone <repository-url>
cd etl_pipeline

# Copy and review environment variables
cp .env.example .env
```

### 2. Build and Start Services

```bash
docker-compose up --build -d
```

Wait for all services to be healthy. The PostgreSQL database will start first, and the Django app will wait for it to be ready.

### 3. Run Database Migrations

```bash
docker-compose exec app python manage.py migrate
```

### 4. Seed Legacy Data

```bash
docker-compose exec app python manage.py seed_legacy_data
```

This creates **500,000** `LegacyOrder` records with realistic randomized data.

### 5. Run the Migration

```bash
# Full migration with default settings (batch_size=1000)
docker-compose exec app python manage.py migrate_orders

# Custom batch size
docker-compose exec app python manage.py migrate_orders --batch-size=5000

# Dry run (preview only, no changes)
docker-compose exec app python manage.py migrate_orders --dry-run

# Resume from a specific point
docker-compose exec app python manage.py migrate_orders --start-from=legacy-050001
```

## Management Commands

### `seed_legacy_data`

Populates the `LegacyOrder` table with 500,000 sample records.

```bash
docker-compose exec app python manage.py seed_legacy_data
```

- Generates unique `external_id` values (`legacy-000001` through `legacy-500000`)
- Creates realistic JSON data with randomized emails, SKUs, quantities, and prices
- Uses `bulk_create` for efficient insertion
- Idempotent: skips if records already exist

### `migrate_orders`

The production-grade ETL migration command.

```bash
docker-compose exec app python manage.py migrate_orders [OPTIONS]
```

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--batch-size` | Integer | 1000 | Records per batch |
| `--dry-run` | Flag | False | Preview without making changes |
| `--start-from` | String | None | Resume from this `external_id` |

### `migrate_orders_naive`

The deliberately unoptimized version for benchmarking comparison.

```bash
docker-compose exec app python manage.py migrate_orders_naive --limit=1000
```

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--limit` | Integer | 1000 | Max records to process |

## Benchmarking

See [benchmark.md](benchmark.md) for detailed performance analysis comparing:

1. **Memory Usage**: Naive vs. optimized approach
2. **Execution Time**: Across different batch sizes (100, 500, 1000, 5000)
3. **Database Query Counts**: One-by-one vs. bulk operations

### Running Benchmarks Yourself

```bash
# 1. Seed data
docker-compose exec app python manage.py seed_legacy_data

# 2. Run naive benchmark (limited to 1000 records)
docker-compose exec app python manage.py migrate_orders_naive --limit=1000

# 3. Reset migrated flags and run optimized version
docker-compose exec app python manage.py migrate_orders --batch-size=1000
```

## Project Structure

```
etl_pipeline/
├── docker-compose.yml          # Docker services (app + PostgreSQL)
├── Dockerfile                  # Django app container
├── requirements.txt            # Python dependencies
├── manage.py                   # Django management entry point
├── .env.example                # Environment variables template
├── .gitignore                  # Git ignore rules
├── README.md                   # This file
├── benchmark.md                # Performance benchmarking results
├── etl_project/                # Django project settings
│   ├── __init__.py
│   ├── settings.py
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
└── orders/                     # Orders app
    ├── __init__.py
    ├── apps.py
    ├── models.py               # LegacyOrder, Order, OrderLine
    ├── admin.py                # Admin registration
    └── management/
        └── commands/
            ├── seed_legacy_data.py       # Data seeder
            ├── migrate_orders.py         # Production ETL command
            └── migrate_orders_naive.py   # Naive benchmark command
```

## License

This project is for educational and demonstration purposes.
