import sys
import os

# Add the project root to the Python path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

from g_sheets import sheets_handler as db

if __name__ == "__main__":
    print("--- Clearing all data from the Google Sheet ---")
    db.clear_all_data()
    print("--- Sheet cleared successfully ---")

    print("--- Clearing local database (drop & recreate tables) ---")
    try:
        from db.database import engine as erp_engine, Base as ErpBase
        from erp import erp_models  # noqa: F401
        ErpBase.metadata.drop_all(bind=erp_engine)
        ErpBase.metadata.create_all(bind=erp_engine)
        print("Cleared ERP database tables.")
    except Exception as e:
        print(f"WARNING: Failed to clear ERP database: {e}")

    try:
        from db.automation_database import engine as auto_engine, Base as AutoBase
        from db import automation_models  # noqa: F401
        AutoBase.metadata.drop_all(bind=auto_engine)
        AutoBase.metadata.create_all(bind=auto_engine)
        print("Cleared automation database tables.")
    except Exception as e:
        print(f"WARNING: Failed to clear automation database: {e}")

    print("--- Local database cleared successfully ---")
