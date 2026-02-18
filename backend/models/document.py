from sqlalchemy import Column, Integer, String, Text, DateTime
from datetime import datetime
from backend.database import Base


class GeneratedDocument(Base):
    __tablename__ = "generated_documents"

    id = Column(Integer, primary_key=True, index=True)
    category = Column(String(255), nullable=False)
    document_type = Column(String(255), nullable=False)
    input_payload = Column(Text, nullable=False)
    generated_content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
