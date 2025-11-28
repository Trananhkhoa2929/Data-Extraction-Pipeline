"""
Generate realistic synthetic CSV data for 5 karaoke branches.

Creates 24 months of daily sales transactions and room bookings,
organized in raw_branch_data/{branch_folder}/ matching the structure
expected by the ETL pipeline.

Usage:
    python generate_sample_data.py
    python generate_sample_data.py --months 6
"""

from __future__ import annotations

import argparse
import csv
import random
import uuid
from datetime import date, timedelta
from pathlib import Path

from config.settings import BRANCH_MAP, ROOM_TYPES, PAYMENT_METHODS, RAW_DATA_DIR

# -- Seed for reproducibility ------------------------------------------------
random.seed(42)

# -- Service catalog ----------------------------------------------------------
SERVICES = [
    # Room Rental (linked to bookings, but also appears as sales line items)
    {"service_name": "Small Room Rental",  "category": "Room Rental",      "unit_price": 120_000},
    {"service_name": "Medium Room Rental", "category": "Room Rental",      "unit_price": 200_000},
    {"service_name": "Large Room Rental",  "category": "Room Rental",      "unit_price": 350_000},
    {"service_name": "VIP Room Rental",    "category": "Room Rental",      "unit_price": 550_000},
    # Food & Beverage
    {"service_name": "Soft Drink",         "category": "Food & Beverage",  "unit_price": 25_000},
    {"service_name": "Beer",               "category": "Food & Beverage",  "unit_price": 35_000},
    {"service_name": "Cocktail",           "category": "Food & Beverage",  "unit_price": 65_000},
    {"service_name": "Fruit Platter",      "category": "Food & Beverage",  "unit_price": 85_000},
    {"service_name": "Snack Combo",        "category": "Food & Beverage",  "unit_price": 55_000},
    {"service_name": "Hot Pot Set",        "category": "Food & Beverage",  "unit_price": 250_000},
    # Events
    {"service_name": "Birthday Package",   "category": "Events",           "unit_price": 1_500_000},
    {"service_name": "Corporate Event",    "category": "Events",           "unit_price": 3_000_000},
    {"service_name": "Karaoke Contest",    "category": "Events",           "unit_price": 2_000_000},
    # Membership
    {"service_name": "Monthly Pass",       "category": "Membership",       "unit_price": 800_000},
    {"service_name": "VIP Annual Card",    "category": "Membership",       "unit_price": 5_000_000},
]

# -- Room inventory per branch ------------------------------------------------
ROOM_INVENTORY = {
    "branch_hanoi": [
        ("HN-S01", "Lotus Small 1",  "Small"),
        ("HN-S02", "Lotus Small 2",  "Small"),
        ("HN-S03", "Lotus Small 3",  "Small"),
        ("HN-M01", "Orchid Medium 1", "Medium"),
        ("HN-M02", "Orchid Medium 2", "Medium"),
        ("HN-L01", "Dragon Large 1",  "Large"),
        ("HN-V01", "Imperial VIP",    "VIP"),
    ],
    "branch_hcm": [
        ("HCM-S01", "Saigon Small 1",  "Small"),
        ("HCM-S02", "Saigon Small 2",  "Small"),
        ("HCM-S03", "Saigon Small 3",  "Small"),
        ("HCM-S04", "Saigon Small 4",  "Small"),
        ("HCM-M01", "Pearl Medium 1",  "Medium"),
        ("HCM-M02", "Pearl Medium 2",  "Medium"),
        ("HCM-M03", "Pearl Medium 3",  "Medium"),
        ("HCM-L01", "Landmark Large 1", "Large"),
        ("HCM-L02", "Landmark Large 2", "Large"),
        ("HCM-V01", "Prestige VIP",     "VIP"),
    ],
    "branch_danang": [
        ("DN-S01", "Beach Small 1",    "Small"),
        ("DN-S02", "Beach Small 2",    "Small"),
        ("DN-M01", "Marble Medium 1",  "Medium"),
        ("DN-M02", "Marble Medium 2",  "Medium"),
        ("DN-L01", "Hai Van Large",    "Large"),
    ],
    "branch_cantho": [
        ("CT-S01", "Mekong Small 1",   "Small"),
        ("CT-S02", "Mekong Small 2",   "Small"),
        ("CT-M01", "Ninh Kieu Medium", "Medium"),
        ("CT-L01", "Can Tho Large",    "Large"),
    ],
    "branch_haiphong": [
        ("HP-S01", "Harbor Small 1",   "Small"),
        ("HP-S02", "Harbor Small 2",   "Small"),
        ("HP-S03", "Harbor Small 3",   "Small"),
        ("HP-M01", "Lach Tray Medium", "Medium"),
        ("HP-M02", "Cat Ba Medium",    "Medium"),
        ("HP-L01", "Do Son Large",     "Large"),
    ],
}

# -- Vietnamese names for customer generation ---------------------------------
_LAST_NAMES = ["Nguyen", "Tran", "Le", "Pham", "Hoang", "Vu", "Vo", "Dang", "Bui", "Do"]
_FIRST_NAMES = [
    "An", "Binh", "Cuong", "Dung", "Hoa", "Hung", "Lan", "Minh",
    "Nam", "Phuong", "Quang", "Son", "Thanh", "Tuan", "Yen",
    "Duc", "Hai", "Khanh", "Linh", "Mai", "Ngoc", "Phuc", "Thao",
]


def _random_name() -> str:
    return f"{random.choice(_LAST_NAMES)} {random.choice(_FIRST_NAMES)}"


# -- Seasonality multiplier --------------------------------------------------

def _seasonality(month: int, branch_folder: str) -> float:
    """Return a demand multiplier for a given month and branch."""
    import math

    base = 1.0 + 0.12 * math.sin((month / 12) * 2 * math.pi)

    # Tet holiday season (Jan-Feb): big spike
    if month in (1, 2):
        base *= 1.25

    # Summer peak (Jun-Aug)
    if month in (6, 7, 8):
        base *= 1.10

    # Da Nang typhoon season dip (Sep-Oct)
    if branch_folder == "branch_danang" and month in (9, 10):
        base *= 0.75

    # HCM always busy
    if branch_folder == "branch_hcm":
        base *= 1.08

    return base


# -- Sales data generator ----------------------------------------------------

def _generate_sales_for_month(
    branch_folder: str,
    year: int,
    month: int,
    base_daily_transactions: int = 80,
) -> list[dict]:
    """Generate daily sales transactions for one branch-month."""
    import calendar

    days_in_month = calendar.monthrange(year, month)[1]
    multiplier = _seasonality(month, branch_folder)
    rows = []

    for day in range(1, days_in_month + 1):
        current_date = date(year, month, day)
        weekday = current_date.weekday()
        is_weekend = weekday >= 5

        # More transactions on weekends
        daily_count = int(base_daily_transactions * multiplier * (1.35 if is_weekend else 1.0))
        daily_count = max(20, daily_count + random.randint(-15, 15))

        for _ in range(daily_count):
            service = random.choice(SERVICES)

            # F&B items have higher quantity
            if service["category"] == "Food & Beverage":
                qty = random.randint(1, 6)
            elif service["category"] == "Events":
                qty = 1
            elif service["category"] == "Membership":
                qty = 1
            else:
                qty = random.randint(1, 3)

            unit_price = service["unit_price"]

            # Random discount (0-15%)
            discount_pct = random.choice([0, 0, 0, 0, 5, 10, 15])
            discount_amount = round(unit_price * qty * discount_pct / 100)
            total = unit_price * qty - discount_amount

            rows.append({
                "transaction_id": f"TXN-{uuid.uuid4().hex[:10].upper()}",
                "date": current_date.isoformat(),
                "service_name": service["service_name"],
                "category": service["category"],
                "quantity": qty,
                "unit_price": unit_price,
                "discount_amount": discount_amount,
                "total_amount": total,
                "payment_method": random.choice(PAYMENT_METHODS),
            })

    return rows


# -- Bookings data generator -------------------------------------------------

def _generate_bookings_for_month(
    branch_folder: str,
    year: int,
    month: int,
    base_daily_bookings: int = 15,
) -> list[dict]:
    """Generate daily room bookings for one branch-month."""
    import calendar

    days_in_month = calendar.monthrange(year, month)[1]
    rooms = ROOM_INVENTORY.get(branch_folder, [])
    if not rooms:
        return []

    multiplier = _seasonality(month, branch_folder)
    rows = []

    for day in range(1, days_in_month + 1):
        current_date = date(year, month, day)
        weekday = current_date.weekday()
        is_weekend = weekday >= 5

        daily_count = int(base_daily_bookings * multiplier * (1.5 if is_weekend else 1.0))
        daily_count = max(5, daily_count + random.randint(-5, 5))

        for _ in range(daily_count):
            room_id, room_name, room_type = random.choice(rooms)
            room_info = ROOM_TYPES[room_type]

            # Peak hours 18-23, some daytime
            if random.random() < 0.7:
                start = random.randint(18, 21)
            else:
                start = random.randint(10, 17)

            duration = random.choice([1, 1, 2, 2, 2, 3, 3, 4])
            end = min(start + duration, 24)
            actual_duration = end - start

            num_guests = min(
                random.randint(2, room_info["capacity"]),
                room_info["capacity"],
            )

            room_fee = room_info["hourly_rate"] * actual_duration
            extra = random.choice([0, 0, 0, 50_000, 100_000, 150_000])
            total = room_fee + extra

            rows.append({
                "booking_id": f"BK-{uuid.uuid4().hex[:10].upper()}",
                "date": current_date.isoformat(),
                "room_id": room_id,
                "room_name": room_name,
                "room_type": room_type,
                "customer_name": _random_name(),
                "start_hour": start,
                "end_hour": end,
                "duration_hours": actual_duration,
                "num_guests": num_guests,
                "room_fee": room_fee,
                "extra_charges": extra,
                "total_charge": total,
            })

    return rows


# -- Main ---------------------------------------------------------------------

def generate_all(months: int = 24, output_dir: Path | None = None) -> None:
    """Generate sample data files for all branches."""
    out = output_dir or RAW_DATA_DIR
    start_year = 2024
    start_month = 1

    total_sales_rows = 0
    total_booking_rows = 0
    total_files = 0

    for branch_folder, branch_info in BRANCH_MAP.items():
        branch_dir = out / branch_folder
        branch_dir.mkdir(parents=True, exist_ok=True)

        # Scale base transactions by branch capacity
        capacity = branch_info.get("capacity", 20)
        base_sales = int(60 + capacity * 2.5)
        base_bookings = int(8 + capacity * 0.5)

        for i in range(months):
            year = start_year + (start_month - 1 + i) // 12
            month = (start_month - 1 + i) % 12 + 1
            period = f"{year}-{month:02d}"

            # -- Sales CSV --------------------------------------------
            sales_rows = _generate_sales_for_month(
                branch_folder, year, month, base_sales
            )
            sales_path = branch_dir / f"sales_{period}.csv"
            if sales_rows:
                with open(sales_path, "w", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=sales_rows[0].keys())
                    writer.writeheader()
                    writer.writerows(sales_rows)
                total_sales_rows += len(sales_rows)
                total_files += 1

            # -- Bookings CSV -----------------------------------------
            booking_rows = _generate_bookings_for_month(
                branch_folder, year, month, base_bookings
            )
            bookings_path = branch_dir / f"bookings_{period}.csv"
            if booking_rows:
                with open(bookings_path, "w", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=booking_rows[0].keys())
                    writer.writeheader()
                    writer.writerows(booking_rows)
                total_booking_rows += len(booking_rows)
                total_files += 1

        print(f"  [OK] {branch_info['branch_name']:30s} | {months} months generated")

    print(f"\n{'='*60}")
    print(f"  Total files created:    {total_files}")
    print(f"  Total sales rows:       {total_sales_rows:,}")
    print(f"  Total booking rows:     {total_booking_rows:,}")
    print(f"  Output directory:       {out}")
    print(f"{'='*60}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate synthetic karaoke branch data.")
    parser.add_argument("--months", type=int, default=24, help="Number of months to generate (default: 24)")
    parser.add_argument("--output", type=str, default=None, help="Output directory (default: raw_branch_data/)")
    args = parser.parse_args()

    output = Path(args.output) if args.output else None
    print(f"Generating {args.months} months of sample data for {len(BRANCH_MAP)} branches...\n")
    generate_all(months=args.months, output_dir=output)
