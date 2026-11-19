"""CLI entrypoint for seeding initial database records."""

from app.core.database import Base, SessionLocal, engine
from app.services.seed_service import seed_initial_data


def main() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_initial_data(db)
        print("LDI database seeded successfully.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
