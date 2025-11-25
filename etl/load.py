"""
Step 4: LOAD — Write dimension and fact DataFrames into PostgreSQL.

Uses SQLAlchemy for connection management and executes raw DDL
from models.schema to create tables on first run. Dimensions use
upsert logic (ON CONFLICT DO UPDATE); facts use unique-constraint
dedup (ON CONFLICT DO NOTHING).
"""

from __future__ import annotations

import pandas as pd
from sqlalchemy import create_engine, text

from config.settings import DATABASE_URL
from etl.extract import ExtractedFile
from etl.transform import StarSchemaData
from models.schema import ALL_DDL
from utils.file_tracker import mark_processed
from utils.logger import logger


def _get_engine():
    """Create a SQLAlchemy engine from the DATABASE_URL."""
    return create_engine(DATABASE_URL, echo=False)


def _ensure_tables(engine) -> None:
    """Execute DDL statements to create tables if they don't exist."""
    with engine.begin() as conn:
        for ddl in ALL_DDL:
            conn.execute(text(ddl))
    logger.info("Schema tables verified / created.")


def _upsert_dimension(
    engine,
    df: pd.DataFrame,
    table_name: str,
    conflict_column: str,
) -> int:
    """
    Insert dimension rows, updating on conflict.
    Returns the number of rows written.
    """
    if df.empty:
        return 0

    cols = list(df.columns)
    placeholders = ", ".join(f":{c}" for c in cols)
    col_list = ", ".join(cols)
    update_set = ", ".join(
        f"{c} = EXCLUDED.{c}" for c in cols if c != conflict_column
    )

    sql = f"""
        INSERT INTO {table_name} ({col_list})
        VALUES ({placeholders})
        ON CONFLICT ({conflict_column}) DO UPDATE SET {update_set}
    """

    with engine.begin() as conn:
        for _, row in df.iterrows():
            conn.execute(text(sql), dict(row))

    return len(df)


def _append_fact(
    engine,
    df: pd.DataFrame,
    table_name: str,
    unique_column: str,
) -> int:
    """
    Append fact rows, skipping duplicates via ON CONFLICT DO NOTHING.
    Returns the number of rows written.
    """
    if df.empty:
        return 0

    cols = list(df.columns)
    placeholders = ", ".join(f":{c}" for c in cols)
    col_list = ", ".join(cols)

    sql = f"""
        INSERT INTO {table_name} ({col_list})
        VALUES ({placeholders})
        ON CONFLICT ({unique_column}) DO NOTHING
    """

    inserted = 0
    with engine.begin() as conn:
        for _, row in df.iterrows():
            result = conn.execute(text(sql), dict(row))
            inserted += result.rowcount

    return inserted


def load_to_database(
    schema: StarSchemaData,
    files: list[ExtractedFile] | None = None,
    dry_run: bool = False,
) -> dict[str, int]:
    """
    Load all star-schema data into PostgreSQL.

    Parameters
    ----------
    schema : StarSchemaData
        Transformed dimension and fact DataFrames.
    files : list[ExtractedFile], optional
        Original extracted files — marked as processed on success.
    dry_run : bool
        If True, validate but don't actually write to DB.

    Returns
    -------
    dict[str, int]
        Row counts loaded per table.
    """
    logger.info("-- Loading to Database --")

    if dry_run:
        counts = {}
        for name in ["dim_branch", "dim_service", "dim_room", "dim_time", "fact_sales", "fact_bookings"]:
            df = getattr(schema, name)
            counts[name] = len(df)
            logger.info("  [DRY RUN] %-16s | %d rows would be loaded", name, len(df))
        logger.info("Dry run complete — no data written.")
        return counts

    engine = _get_engine()
    _ensure_tables(engine)

    counts: dict[str, int] = {}

    # -- Dimensions (upsert) ----------------------------------------------
    counts["dim_branch"] = _upsert_dimension(
        engine, schema.dim_branch, "dim_branch", "branch_id"
    )
    counts["dim_service"] = _upsert_dimension(
        engine, schema.dim_service, "dim_service", "service_id"
    )

    # dim_room needs branch_key from DB (SERIAL), so we fetch actual keys
    if not schema.dim_room.empty:
        with engine.connect() as conn:
            db_branches = pd.read_sql(
                "SELECT branch_key, branch_name FROM dim_branch", conn
            )
        branch_key_map = dict(zip(db_branches["branch_name"], db_branches["branch_key"]))

        # Re-map branch_key using DB values (dim_branch has branch_name via dim_branch)
        # dim_room already has branch_key set during transform, but we need the DB SERIAL keys
        if not schema.dim_branch.empty:
            transform_to_db = dict(zip(
                range(1, len(schema.dim_branch) + 1),
                [branch_key_map.get(name) for name in schema.dim_branch["branch_name"]]
            ))
            schema.dim_room["branch_key"] = schema.dim_room["branch_key"].map(transform_to_db)

    counts["dim_room"] = _upsert_dimension(
        engine, schema.dim_room, "dim_room", "room_id"
    )
    counts["dim_time"] = _upsert_dimension(
        engine, schema.dim_time, "dim_time", "full_date"
    )

    # -- Re-map fact foreign keys to DB SERIAL values ---------------------
    with engine.connect() as conn:
        db_branches = pd.read_sql("SELECT branch_key, branch_name FROM dim_branch", conn)
        db_services = pd.read_sql("SELECT service_key, service_name FROM dim_service", conn)
        db_rooms = pd.read_sql("SELECT room_key, room_id FROM dim_room", conn)
        db_time = pd.read_sql("SELECT time_key, full_date FROM dim_time", conn)

    # Build re-mapping dicts: transform_key → db_key
    branch_remap = dict(zip(
        range(1, len(schema.dim_branch) + 1),
        [dict(zip(db_branches["branch_name"], db_branches["branch_key"])).get(n)
         for n in schema.dim_branch["branch_name"]]
    )) if not schema.dim_branch.empty else {}

    service_remap = dict(zip(
        range(1, len(schema.dim_service) + 1),
        [dict(zip(db_services["service_name"], db_services["service_key"])).get(n)
         for n in schema.dim_service["service_name"]]
    )) if not schema.dim_service.empty else {}

    room_remap = dict(zip(
        range(1, len(schema.dim_room) + 1),
        [dict(zip(db_rooms["room_id"], db_rooms["room_key"])).get(n)
         for n in schema.dim_room["room_id"]]
    )) if not schema.dim_room.empty else {}

    db_time["full_date"] = pd.to_datetime(db_time["full_date"]).dt.date
    time_remap = dict(zip(
        range(1, len(schema.dim_time) + 1),
        [dict(zip(db_time["full_date"], db_time["time_key"])).get(d)
         for d in schema.dim_time["full_date"]]
    )) if not schema.dim_time.empty else {}

    # -- Facts (append with dedup) ----------------------------------------
    if not schema.fact_sales.empty:
        fact_s = schema.fact_sales.copy()
        fact_s["branch_key"] = fact_s["branch_key"].map(branch_remap)
        fact_s["service_key"] = fact_s["service_key"].map(service_remap)
        fact_s["time_key"] = fact_s["time_key"].map(time_remap)
        fact_s = fact_s.dropna(subset=["branch_key", "service_key", "time_key"])
        fact_s[["branch_key", "service_key", "time_key"]] = fact_s[
            ["branch_key", "service_key", "time_key"]
        ].astype(int)
        counts["fact_sales"] = _append_fact(engine, fact_s, "fact_sales", "transaction_id")
    else:
        counts["fact_sales"] = 0

    if not schema.fact_bookings.empty:
        fact_b = schema.fact_bookings.copy()
        fact_b["branch_key"] = fact_b["branch_key"].map(branch_remap)
        fact_b["room_key"] = fact_b["room_key"].map(room_remap)
        fact_b["time_key"] = fact_b["time_key"].map(time_remap)
        fact_b = fact_b.dropna(subset=["branch_key", "room_key", "time_key"])
        fact_b[["branch_key", "room_key", "time_key"]] = fact_b[
            ["branch_key", "room_key", "time_key"]
        ].astype(int)
        counts["fact_bookings"] = _append_fact(engine, fact_b, "fact_bookings", "booking_id")
    else:
        counts["fact_bookings"] = 0

    # -- Mark files as processed ------------------------------------------
    if files:
        for ef in files:
            mark_processed(ef.filepath)

    # -- Summary ----------------------------------------------------------
    for table, count in counts.items():
        logger.info("  Loaded %-16s | %d rows", table, count)

    total = sum(counts.values())
    logger.info("Load complete — %d total rows written.", total)
    return counts

