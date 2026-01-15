import requests
from datetime import datetime

API_BASE_URL = "http://localhost:8000"

def populate():
    print("--- Starting Database Population ---")

    suppliers = [
        {"name": "Gulf Industrial Valves LLC", "contact_person": "Sales Team", "email": "sales@gulfvalves.com"},
        {"name": "PetroTech Electrical Supplies", "contact_person": "Support", "email": "support@petrotech.com"},
        {"name": "Delta Measurement Systems", "contact_person": "Accounts", "email": "accounts@deltams.com"}
    ]

    supplier_ids = {}
    for supplier_data in suppliers:
        try:
            response = requests.post(f"{API_BASE_URL}/suppliers/", json=supplier_data)
            response.raise_for_status()
            created_supplier = response.json()
            supplier_ids[created_supplier['name']] = created_supplier['id']
            print(f"Created/verified supplier: {created_supplier['name']}")
        except requests.exceptions.RequestException as e:
            print(f"Error creating supplier {supplier_data['name']}: {e}")
            return

    purchase_orders = [
        {"po_number": "PO-OG-201", "supplier_name": "Gulf Industrial Valves LLC", "expected_delivery_date": "2026-01-20T00:00:00"},
        {"po_number": "PO-OG-202", "supplier_name": "PetroTech Electrical Supplies", "expected_delivery_date": "2026-01-10T00:00:00"},
        {"po_number": "PO-OG-203", "supplier_name": "Delta Measurement Systems", "expected_delivery_date": "2026-01-15T00:00:00"}
    ]

    for po_data in purchase_orders:
        try:
            payload = {
                "po_number": po_data["po_number"],
                "supplier_id": supplier_ids[po_data["supplier_name"]],
                "expected_delivery_date": po_data["expected_delivery_date"]
            }
            response = requests.post(f"{API_BASE_URL}/purchase_orders/", json=payload)
            response.raise_for_status()
            print(f"Created purchase order: {po_data['po_number']}")
        except requests.exceptions.RequestException as e:
            print(f"Error creating PO {po_data['po_number']}: {e}")

    print("--- Database Population Complete ---")

if __name__ == "__main__":
    populate()
