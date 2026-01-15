from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

def create_test_po_pdf(file_path="test_po.pdf"):
    c = canvas.Canvas(file_path, pagesize=letter)
    width, height = letter

    c.drawString(72, height - 72, "Purchase Order")
    c.drawString(72, height - 108, "PO Number: TEST-12345")
    c.drawString(72, height - 126, "Supplier Name: Test Supplier Inc.")
    c.drawString(72, height - 144, "Expected Delivery Date: 2024-12-31")

    c.drawString(72, height - 200, "Line Items:")
    c.drawString(90, height - 218, "- Description: Widget A, Quantity: 10, Unit Price: $50.00")
    c.drawString(90, height - 236, "- Description: Gadget B, Quantity: 5, Unit Price: $120.00")

    c.save()
    print(f"Test PO PDF created at {file_path}")

if __name__ == "__main__":
    create_test_po_pdf()
