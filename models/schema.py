"""
Star Schema DDL for the Karaoke Multi-Branch Data Warehouse.

These tables sit alongside Project 1's existing tables
(branches, sales_monthly, campaigns) in the same PostgreSQL database.
"""

# -- Dimension Tables ---------------------------------------------------------

DDL_DIM_BRANCH = """
CREATE TABLE IF NOT EXISTS dim_branch (
    branch_key   SERIAL PRIMARY KEY,
    branch_id    TEXT NOT NULL UNIQUE,
    branch_name  TEXT NOT NULL,
    city         TEXT NOT NULL,
    district     TEXT NOT NULL,
    region       TEXT NOT NULL,
    manager      TEXT,
    capacity     INTEGER,
    open_date    DATE
);

COMMENT ON TABLE dim_branch
    IS 'Dimension table for karaoke branches — master reference.';
"""

DDL_DIM_SERVICE = """
CREATE TABLE IF NOT EXISTS dim_service (
    service_key  SERIAL PRIMARY KEY,
    service_id   TEXT NOT NULL UNIQUE,
    service_name TEXT NOT NULL,
    category     TEXT NOT NULL,
    unit_price   NUMERIC NOT NULL DEFAULT 0,
    unit         TEXT NOT NULL DEFAULT 'item'
);

COMMENT ON TABLE dim_service
    IS 'Dimension table for services offered (Room Rental, F&B, Events, Membership).';
"""

DDL_DIM_ROOM = """
CREATE TABLE IF NOT EXISTS dim_room (
    room_key     SERIAL PRIMARY KEY,
    room_id      TEXT NOT NULL UNIQUE,
    branch_key   INTEGER NOT NULL REFERENCES dim_branch(branch_key),
    room_name    TEXT NOT NULL,
    room_type    TEXT NOT NULL,
    capacity     INTEGER NOT NULL,
    hourly_rate  NUMERIC NOT NULL
);

COMMENT ON TABLE dim_room
    IS 'Dimension table for room inventory per branch (Small/Medium/Large/VIP).';
"""

DDL_DIM_TIME = """
CREATE TABLE IF NOT EXISTS dim_time (
    time_key     SERIAL PRIMARY KEY,
    full_date    DATE NOT NULL UNIQUE,
    day_of_week  INTEGER NOT NULL,
    day_name     TEXT NOT NULL,
    month        INTEGER NOT NULL,
    month_name   TEXT NOT NULL,
    quarter      INTEGER NOT NULL,
    year         INTEGER NOT NULL,
    is_weekend   BOOLEAN NOT NULL DEFAULT FALSE,
    is_holiday   BOOLEAN NOT NULL DEFAULT FALSE
);

COMMENT ON TABLE dim_time
    IS 'Date dimension for slicing facts by day, month, quarter, year.';
"""

# -- Fact Tables --------------------------------------------------------------

DDL_FACT_SALES = """
CREATE TABLE IF NOT EXISTS fact_sales (
    sale_key        SERIAL PRIMARY KEY,
    branch_key      INTEGER NOT NULL REFERENCES dim_branch(branch_key),
    service_key     INTEGER NOT NULL REFERENCES dim_service(service_key),
    time_key        INTEGER NOT NULL REFERENCES dim_time(time_key),
    transaction_id  TEXT NOT NULL UNIQUE,
    quantity        INTEGER NOT NULL DEFAULT 1,
    unit_price      NUMERIC NOT NULL,
    discount_amount NUMERIC NOT NULL DEFAULT 0,
    total_amount    NUMERIC NOT NULL,
    payment_method  TEXT NOT NULL DEFAULT 'Cash'
);

COMMENT ON TABLE fact_sales
    IS 'Fact table for daily transactional sales (F&B, services, etc.).';
"""

DDL_FACT_BOOKINGS = """
CREATE TABLE IF NOT EXISTS fact_bookings (
    booking_key    SERIAL PRIMARY KEY,
    branch_key     INTEGER NOT NULL REFERENCES dim_branch(branch_key),
    room_key       INTEGER NOT NULL REFERENCES dim_room(room_key),
    time_key       INTEGER NOT NULL REFERENCES dim_time(time_key),
    booking_id     TEXT NOT NULL UNIQUE,
    customer_name  TEXT,
    start_hour     INTEGER NOT NULL,
    end_hour       INTEGER NOT NULL,
    duration_hours NUMERIC NOT NULL,
    num_guests     INTEGER NOT NULL DEFAULT 1,
    room_fee       NUMERIC NOT NULL,
    extra_charges  NUMERIC NOT NULL DEFAULT 0,
    total_charge   NUMERIC NOT NULL
);

COMMENT ON TABLE fact_bookings
    IS 'Fact table for room booking events with duration and guest counts.';
"""

# -- Indexes for query performance --------------------------------------------

DDL_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_fact_sales_branch   ON fact_sales(branch_key);
CREATE INDEX IF NOT EXISTS idx_fact_sales_time     ON fact_sales(time_key);
CREATE INDEX IF NOT EXISTS idx_fact_sales_service  ON fact_sales(service_key);
CREATE INDEX IF NOT EXISTS idx_fact_bookings_branch ON fact_bookings(branch_key);
CREATE INDEX IF NOT EXISTS idx_fact_bookings_time   ON fact_bookings(time_key);
CREATE INDEX IF NOT EXISTS idx_fact_bookings_room   ON fact_bookings(room_key);
CREATE INDEX IF NOT EXISTS idx_dim_time_date        ON dim_time(full_date);
"""

# -- Ordered DDL list (dimensions first, then facts, then indexes) ------------

ALL_DDL = [
    DDL_DIM_BRANCH,
    DDL_DIM_SERVICE,
    DDL_DIM_ROOM,
    DDL_DIM_TIME,
    DDL_FACT_SALES,
    DDL_FACT_BOOKINGS,
    DDL_INDEXES,
]
