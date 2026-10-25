"""Create tables and seed RBAC for quick local setup.

Prefer Alembic in production:
    alembic upgrade head && python -m scripts.seed_rbac
"""
from database import SessionLocal, init_db
from services.rbac_service import seed_all_tenants


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
        count = seed_all_tenants(db)
    finally:
        db.close()
    print(f"Database initialized. Seeded {count} tenant(s).")


if __name__ == "__main__":
    main()
