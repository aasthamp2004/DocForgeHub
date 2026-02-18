from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from fastapi.middleware.cors import CORSMiddleware
from fastapi.encoders import jsonable_encoder

from backend.database import get_db, Base, engine
from backend.models.category import Category
from backend.models.models import (
    CategoryCreate,
    CategoryResponse,
    DocumentRequest
)
from backend.services.langchain_service import generate_document


# ------------------------
# APP INITIALIZATION
# ------------------------

app = FastAPI(
    title="DocForge API",
    version="1.0.0"
)

# Create tables
Base.metadata.create_all(bind=engine)

# Enable CORS (for Streamlit frontend)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production restrict this
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ------------------------
# ROOT
# ------------------------

@app.get("/")
def root():
    return {
        "message": "DocForge Backend Running 🚀",
        "status": "healthy"
    }


# ------------------------
# CATEGORY CRUD
# ------------------------

@app.post("/categories", response_model=CategoryResponse)
def create_category(
    category: CategoryCreate,
    db: Session = Depends(get_db)
):
    existing = db.query(Category).filter(
        Category.name == category.name
    ).first()

    if existing:
        raise HTTPException(
            status_code=400,
            detail="Category already exists"
        )

    db_category = Category(name=category.name)
    db.add(db_category)
    db.commit()
    db.refresh(db_category)

    return db_category


@app.get("/categories", response_model=list[CategoryResponse])
def get_categories(db: Session = Depends(get_db)):
    return db.query(Category).all()


@app.get("/categories/{category_id}", response_model=CategoryResponse)
def get_category(
    category_id: int,
    db: Session = Depends(get_db)
):
    category = db.query(Category).filter(
        Category.id == category_id
    ).first()

    if not category:
        raise HTTPException(
            status_code=404,
            detail="Category not found"
        )

    return category


@app.delete("/categories/{category_id}")
def delete_category(
    category_id: int,
    db: Session = Depends(get_db)
):
    category = db.query(Category).filter(
        Category.id == category_id
    ).first()

    if not category:
        raise HTTPException(
            status_code=404,
            detail="Category not found"
        )

    db.delete(category)
    db.commit()

    return {"message": "Category deleted successfully"}


# ------------------------
# GENERATE DOCUMENT (LangChain Orchestrated LLM)
# ------------------------

@app.post("/generate")
def generate_doc(request: DocumentRequest):

    if not request.content:
        raise HTTPException(
            status_code=400,
            detail="Content cannot be empty"
        )

    try:
        generated_text = generate_document(
            category=request.category,
            document_type=request.document_type,
            content=request.content
        )

        response_data = {
            "status": "success",
            "category": request.category,
            "document_type": request.document_type,
            "generated_document": generated_text
        }

        return jsonable_encoder(response_data)

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"LLM generation failed: {str(e)}"
        )
