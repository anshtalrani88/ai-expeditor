from sqlalchemy import Column, Integer, String, Enum
from .database import Base
import enum

class UserRole(enum.Enum):
    ENGINEER = "engineer"
    PURCHASING_TEAM = "purchasing_team"

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    email = Column(String, unique=True, index=True)
    role = Column(Enum(UserRole))
