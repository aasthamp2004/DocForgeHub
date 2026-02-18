from sqlalchemy import Column, Integer, String, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from backend.database import Base

class Field(Base):
    __tablename__ = "fields"

    id = Column(Integer, primary_key=True, index=True)
    field_name = Column(String, nullable=False)
    field_type = Column(String, nullable=False)  # string, array, object
    is_required = Column(Boolean, default=False)

    document_type_id = Column(Integer, ForeignKey("document_types.id"))
    parent_field_id = Column(Integer, ForeignKey("fields.id"), nullable=True)

    document_type = relationship("DocumentType", back_populates="fields")
    children = relationship("Field")
