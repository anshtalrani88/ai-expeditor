import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./test.db")

AUTOMATION_DATABASE_URL = os.getenv("AUTOMATION_DATABASE_URL", "sqlite:///./automation.db")
