from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError

from app.db import async_session
from app.models.category import Category

CATEGORIES: Sequence[str] = (
    "Groceries",
    "Dining & Restaurants",
    "Food Delivery",
    "Transport & Taxi",
    "Utilities",
    "Subscriptions",
    "Shopping & Clothing",
    "Pharmacy & Health",
    "Travel & Flights",
    "Home & Furniture",
    "Parking",
    "Fuel",
    "Online Shopping",
    "Income & Transfers",
    "Other",
)


async def seed_categories() -> tuple[int, int]:
    async with async_session() as session:
        existing_names = set(
            (await session.execute(select(Category.name))).scalars().all()
        )

        rows = [{"name": name} for name in CATEGORIES]
        stmt = insert(Category).values(rows).on_conflict_do_nothing(index_elements=["name"])
        result = await session.execute(stmt)
        await session.commit()

    inserted = result.rowcount or 0
    existing = len(existing_names)
    return inserted, existing


async def _main() -> int:
    try:
        inserted, existing_before = await seed_categories()
    except SQLAlchemyError as exc:
        print(
            "Category seed failed. Ensure the DB is reachable and run migrations first: "
            f"{exc}"
        )
        return 1

    total = len(CATEGORIES)
    existing_after = total - inserted
    print(
        "Seed complete: "
        f"inserted={inserted}, existing_before={existing_before}, "
        f"existing_after={existing_after}, total_expected={total}"
    )
    return 0


if __name__ == "__main__":
    import asyncio

    raise SystemExit(asyncio.run(_main()))
