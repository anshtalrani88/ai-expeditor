from fastapi import FastAPI, File, UploadFile, Depends
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session
from db.database import create_tables, SessionLocal
from rag.file_processor import process_file
from rag.rag_pipeline import create_index, query_index
from erp import crud, schemas
from main_flow import run_po_evaluation
import os

app = FastAPI()

class EvaluationRequest(BaseModel):
    email_content: Optional[str] = None

UPLOAD_DIR = "docs"
INDEX = None

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.on_event("startup")
def on_startup():
    global INDEX
    create_tables()
    if not os.path.exists(UPLOAD_DIR):
        os.makedirs(UPLOAD_DIR)
    INDEX = create_index(UPLOAD_DIR)

@app.post("/uploadfile/")
async def create_upload_file(file: UploadFile = File(...)):
    file_location = os.path.join(UPLOAD_DIR, file.filename)
    with open(file_location, "wb+") as file_object:
        file_object.write(file.file.read())
    
    global INDEX
    INDEX = create_index(UPLOAD_DIR)
    
    return {"filename": file.filename, "status": "indexed"}

@app.get("/query/")
def query(query_text: str):
    global INDEX
    response = query_index(INDEX, query_text)
    return {"response": str(response)}

@app.post("/purchase_orders/", response_model=schemas.PurchaseOrder)
def create_purchase_order(po: schemas.PurchaseOrderCreate, db: Session = Depends(get_db)):
    return crud.create_purchase_order(db=db, po=po)

@app.get("/purchase_orders/", response_model=list[schemas.PurchaseOrder])
def read_purchase_orders(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return crud.get_purchase_orders(db, skip=skip, limit=limit)

@app.post("/evaluate-po/{po_number}")
def evaluate_purchase_order(po_number: str, request: EvaluationRequest, db: Session = Depends(get_db)):
    return run_po_evaluation(db, po_number, email_content=request.email_content)

@app.post("/suppliers/", response_model=schemas.Supplier)
def create_supplier(supplier: schemas.SupplierCreate, db: Session = Depends(get_db)):
    db_supplier = crud.get_supplier_by_name(db, name=supplier.name)
    if db_supplier:
        return db_supplier
    return crud.create_supplier(db=db, supplier=supplier)

@app.get("/")
def read_root():
    return {"Hello": "World"}
