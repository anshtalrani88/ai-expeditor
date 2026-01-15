from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from config import AUTOMATION_DATABASE_URL

engine = create_engine(AUTOMATION_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def create_tables() -> None:
    # Import models so metadata is populated
    from db import automation_models  # noqa: F401

    Base.metadata.create_all(bind=engine)
