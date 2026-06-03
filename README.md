# Automated Multi-Branch ETL Pipeline (Project 2)

A Python-based ETL pipeline that processes raw daily CSV/Excel reports from independent karaoke branches and loads them into a centralized PostgreSQL database — the same database used by **Project 1's AI Dashboard** for Text-to-SQL queries and Recharts visualizations.

## Architecture

```
raw_branch_data/          Python ETL Pipeline         PostgreSQL Database
┌─────────────────┐    ┌──────────────────────┐    ┌──────────────────────┐
│ branch_hanoi/   │    │ 1. EXTRACT           │    │ dim_branch           │
│ branch_hcm/     │───▶│ 2. VALIDATE & CLEAN  │───▶│ dim_service           │
│ branch_danang/  │    │ 3. TRANSFORM (Star)  │    │ dim_room              │
│ branch_cantho/  │    │ 4. LOAD (Upsert)     │    │ dim_time              │
│ branch_haiphong/│    └──────────────────────┘    │ fact_sales            │
└─────────────────┘                                │ fact_bookings         │
                                                   └──────────────────────┘
                                                          │
                                                          ▼
                                                   Project 1 AI Dashboard
```

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Database

```bash
cp .env.example .env
# Edit .env with your PostgreSQL connection string
```

### 3. Generate Sample Data

```bash
python generate_sample_data.py
# Creates 24 months of realistic data for 5 branches
```

### 4. Run the Pipeline

```bash
# Full run
python run_pipeline.py

# Validate without loading to database
python run_pipeline.py --dry-run

# Re-process all files (ignore history)
python run_pipeline.py --force-reload

# Process single branch
python run_pipeline.py --branch branch_hcm
```

## Star Schema Design

### Dimension Tables

| Table | Description |
|-------|-------------|
| `dim_branch` | Branch master data (name, city, region, manager) |
| `dim_service` | Services catalog (Room Rental, F&B, Events, Membership) |
| `dim_room` | Room inventory per branch (Small/Medium/Large/VIP) |
| `dim_time` | Date dimension (day, month, quarter, year, weekend/holiday) |

### Fact Tables

| Table | Description |
|-------|-------------|
| `fact_sales` | Daily transactional sales with quantity, price, discounts |
| `fact_bookings` | Room booking events with duration, guests, charges |

## Project Structure

```
├── config/settings.py          # Database URL, branch mapping, constants
├── raw_branch_data/            # Input: raw CSV/Excel files per branch
├── etl/
│   ├── extract.py              # Step 1: File scanning & DataFrame loading
│   ├── validate.py             # Step 2: Quality checks, type casting, dedup
│   ├── transform.py            # Step 3: Star schema dimensional modeling
│   └── load.py                 # Step 4: PostgreSQL upsert with FK remapping
├── models/schema.py            # DDL for all star schema tables
├── utils/
│   ├── logger.py               # Structured pipeline logging
│   └── file_tracker.py         # Tracks processed files (incremental loads)
├── generate_sample_data.py     # Synthetic data generator (24 months × 5 branches)
├── run_pipeline.py             # Main CLI entry point
└── requirements.txt            # Python dependencies
```

## Integration with Project 1

This pipeline writes to the **same PostgreSQL database** that Project 1's Next.js application reads from. The new star schema tables coexist alongside Project 1's existing tables (`branches`, `sales_monthly`, `campaigns`), providing daily-granularity transaction data to complement the monthly aggregates.

## Tech Stack

- **Python 3.10+** — Core language
- **Pandas** — Data manipulation & transformation
- **SQLAlchemy** — Database connection management
- **psycopg2** — PostgreSQL driver
- **python-dotenv** — Environment configuration
