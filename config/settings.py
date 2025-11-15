"""
Centralized configuration for the ETL pipeline.
Reads from .env file or environment variables.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# -- Load .env ----------------------------------------------------------------
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# -- Database -----------------------------------------------------------------
DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/karaoke_analytics",
)

# -- Paths --------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DATA_DIR = Path(os.getenv("RAW_DATA_DIR", PROJECT_ROOT / "raw_branch_data"))
PROCESSED_LOG = PROJECT_ROOT / "processed_files.json"

# -- Logging ------------------------------------------------------------------
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()

# -- Branch name normalization ------------------------------------------------
# Maps folder names → canonical branch records used by Project 1
BRANCH_MAP: dict[str, dict] = {
    "branch_hanoi": {
        "branch_name": "Ha Noi - Hoan Kiem",
        "city": "Ha Noi",
        "district": "Hoan Kiem",
        "region": "North",
        "manager": "Nguyen Van An",
        "capacity": 25,
        "open_date": "2021-03-15",
    },
    "branch_hcm": {
        "branch_name": "TP.HCM - Quan 1",
        "city": "TP.HCM",
        "district": "Quan 1",
        "region": "South",
        "manager": "Tran Thi Bich",
        "capacity": 32,
        "open_date": "2020-08-01",
    },
    "branch_danang": {
        "branch_name": "Da Nang - Hai Chau",
        "city": "Da Nang",
        "district": "Hai Chau",
        "region": "Central",
        "manager": "Le Hoang Cuong",
        "capacity": 18,
        "open_date": "2022-01-10",
    },
    "branch_cantho": {
        "branch_name": "Can Tho - Ninh Kieu",
        "city": "Can Tho",
        "district": "Ninh Kieu",
        "region": "South",
        "manager": "Pham Minh Duc",
        "capacity": 15,
        "open_date": "2022-06-20",
    },
    "branch_haiphong": {
        "branch_name": "Hai Phong - Le Chan",
        "city": "Hai Phong",
        "district": "Le Chan",
        "region": "North",
        "manager": "Vo Thanh Hang",
        "capacity": 20,
        "open_date": "2021-11-05",
    },
}

# -- Room types by capacity ---------------------------------------------------
ROOM_TYPES = {
    "Small": {"capacity": 6, "hourly_rate": 120_000},
    "Medium": {"capacity": 12, "hourly_rate": 200_000},
    "Large": {"capacity": 20, "hourly_rate": 350_000},
    "VIP": {"capacity": 30, "hourly_rate": 550_000},
}

# -- Service categories -------------------------------------------------------
SERVICE_CATEGORIES = ["Room Rental", "Food & Beverage", "Events", "Membership"]

# -- Payment methods ----------------------------------------------------------
PAYMENT_METHODS = ["Cash", "Card", "Bank Transfer", "MoMo", "ZaloPay"]
