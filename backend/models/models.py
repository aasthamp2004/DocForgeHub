from pydantic import BaseModel
from typing import Dict, Any
from datetime import date

class CategoryCreate(BaseModel):
    name: str

class CategoryResponse(BaseModel):
    id: int
    name: str

    class Config:
        orm_mode = True


class DocumentRequest(BaseModel):
    category: str
    document_type: str
    content: Dict[str, Any]

class IncidentMetadata(BaseModel):
    incident_id: str
    date_of_incident: date
    incident_ongoing: bool
