import json
from backend.database import SessionLocal
from backend.models.category import Category
from backend.models.document_type import DocumentType
from backend.models.field import Field


def create_fields(db, fields_dict, document_type_id, parent_id=None):
    for field_name, field_value in fields_dict.items():

        field_type = type(field_value).__name__

        new_field = Field(
            field_name=field_name,
            field_type=field_type,
            is_required=True,
            document_type_id=document_type_id,
            parent_field_id=parent_id
        )

        db.add(new_field)
        db.flush()  # Get ID before recursion

        if isinstance(field_value, dict):
            create_fields(db, field_value, document_type_id, new_field.id)

        elif isinstance(field_value, list) and field_value:
            if isinstance(field_value[0], dict):
                create_fields(db, field_value[0], document_type_id, new_field.id)


if __name__ == "__main__":
    db = SessionLocal()

    with open("schemas.json") as f:
        schema = json.load(f)

    categories = schema.get("categories", {})

    for category_name, documents in categories.items():

        category = Category(name=category_name)
        db.add(category)
        db.flush()

        for doc_name, fields in documents.items():

            document_type = DocumentType(
                name=doc_name,
                category_id=category.id
            )
            db.add(document_type)
            db.flush()

            create_fields(db, fields, document_type.id)

    db.commit()
    db.close()

    print("Schema loaded successfully ✅")
