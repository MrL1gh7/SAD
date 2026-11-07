"""Таблица PostgreSQL и чтение рейсов в двух режимах."""
import os
from datetime import date, datetime, time, timezone, timedelta
from sqlalchemy import (MetaData, Table, Column, BigInteger, Integer, String,
                        DateTime, Date, Index, select, create_engine)
from sqlalchemy.ext.asyncio import create_async_engine

metadata = MetaData()
flights = Table(
    "flights", metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("flight_date", Date, nullable=False),
    Column("carrier", String(12), nullable=False),
    Column("flight_number", String(32), nullable=False),
    Column("origin", String(8), nullable=False),
    Column("destination", String(8), nullable=False),
    Column("departs_at", DateTime(timezone=True), nullable=False),
    Column("arrives_at", DateTime(timezone=True), nullable=False),
    Column("price", Integer, nullable=False),
)
Index("idx_flights_date", flights.c.flight_date)


def db_url(async_mode=False):
    default = "postgresql+psycopg://lab:lab@db:5432/flights"
    value = os.getenv("DATABASE_URL", default)
    return value.replace("+psycopg", "+asyncpg") if async_mode else value


def make_sync_engine():
    return create_engine(db_url(), pool_pre_ping=True)


def make_async_engine():
    return create_async_engine(db_url(True), pool_pre_ping=True)


def to_dict(rows):
    return [{
        "carrier": r["carrier"], "flight_number": r["flight_number"],
        "origin": r["origin"], "destination": r["destination"],
        "departs_at": r["departs_at"].isoformat(),
        "arrives_at": r["arrives_at"].isoformat(), "price": r["price"],
    } for r in rows]


def load_sync(engine, day: date):
    with engine.connect() as conn:
        return to_dict(conn.execute(select(flights).where(flights.c.flight_date == day)).mappings())


async def load_async(engine, day: date):
    async with engine.connect() as conn:
        result = await conn.execute(select(flights).where(flights.c.flight_date == day))
        return to_dict(result.mappings())
