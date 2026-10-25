"""Seed default roles and permissions for every existing tenant.

Run after migrations:
    python -m scripts.seed_rbac
"""
from database import SessionLocal
from services.rbac_service import seed_all_tenants


def main() -> None:
    db = SessionLocal()
    try:
        count = seed_all_tenants(db)
    finally:
        db.close()
    print(f"Seeded roles/permissions for {count} tenant(s).")


if __name__ == "__main__":
    main()
