from sqlalchemy import Column, Integer, String, JSON, DateTime, ForeignKey
from sqlalchemy.sql import func
from backend.database import Base

class Schema(Base):
    __tablename__ = "schemas"

    id = Column(Integer, primary_key=True, index=True)

    category_id = Column(Integer, ForeignKey("categories.id"))

    document_type = Column(String(255), nullable=False)

    schema_definition = Column(JSON, nullable=False)

    version = Column(String(50), default="1.0")

    created_at = Column(DateTime(timezone=True), server_default=func.now())
