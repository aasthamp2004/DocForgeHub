import streamlit as st
import requests
import json

from docx import Document
from io import BytesIO

# =====================================================
# PAGE CONFIG
# =====================================================
st.set_page_config(layout="wide")
st.title("📄 AP's Document Generator")

# =====================================================
# LOAD SCHEMA
# =====================================================
with open("schemas.json") as f:
    schema = json.load(f)

# =====================================================
# SELECT CATEGORY & DOCUMENT
# =====================================================
category = st.selectbox(
    "Select Category",
    list(schema["categories"].keys())
)

document = st.selectbox(
    "Select Document Type",
    list(schema["categories"][category].keys())
)

doc_schema = schema["categories"][category][document]

st.header(f"📝 {document}")

# =====================================================
# SMART RENDER FUNCTION
# =====================================================
def render_field(key, value, path=""):
    field_key = f"{path}.{key}" if path else key

    # -----------------------------
    # STRING
    # -----------------------------
    if isinstance(value, str):

        if value == "string":
            return st.text_input(key)

        if "YYYY-MM-DD" in value:
            selected_date = st.date_input(key)
            return selected_date.isoformat() if selected_date else ""


        return st.text_input(key)

    # -----------------------------
    # NUMBER
    # -----------------------------
    elif isinstance(value, (int, float)):
        return st.number_input(key, value=0.0)

    # -----------------------------
    # BOOLEAN
    # -----------------------------
    elif isinstance(value, bool):
        return st.checkbox(key)

    # -----------------------------
    # LIST
    # -----------------------------
    elif isinstance(value, list):

        # ----------------------------------
        # CASE 1: Predefined string list
        # Example: ["Cash", "Inventory"]
        # ----------------------------------
        if value and all(isinstance(item, str) for item in value):

            st.subheader(key)
            result = {}

            for item in value:
                result[item] = st.text_input(item)

            return result

        # ----------------------------------
        # CASE 2: Predefined list of dicts
        # Example: Balance sheet rows
        # ----------------------------------
        elif value and all(isinstance(item, dict) for item in value):

            st.subheader(key)
            items = []

            for i, row in enumerate(value):

                with st.expander(f"{key} - Section {i+1}", expanded=True):

                    row_data = {}

                    for k, v in row.items():

                        # Make category field read-only
                        if k.lower() == "category":
                            st.markdown(f"### {v}")
                            row_data[k] = v
                        else:
                            row_data[k] = render_field(
                                k,
                                v,
                                f"{field_key}[{i}]"
                            )

                    items.append(row_data)

            return items

        # ----------------------------------
        # CASE 3: Empty list = Dynamic list
        # ----------------------------------
        else:

            items = []

            with st.expander(f"{key} (List)"):

                count = st.number_input(
                    f"How many items for {key}?",
                    min_value=0,
                    step=1,
                    key=f"{field_key}_count"
                )

                for i in range(int(count)):

                    if value:
                        items.append(
                            render_field(
                                f"{key}_{i+1}",
                                value[0],
                                field_key
                            )
                        )
                    else:
                        items.append(
                            st.text_input(
                                f"{key}_{i+1}",
                                key=f"{field_key}_{i}"
                            )
                        )

            return items

    # -----------------------------
    # DICTIONARY (Nested Object)
    # -----------------------------
    elif isinstance(value, dict):

        obj = {}

        with st.expander(key, expanded=False):

            for k, v in value.items():
                obj[k] = render_field(k, v, field_key)

        return obj

    return None


# =====================================================
# CAPTURE USER INPUT
# =====================================================
user_data = {}

for field, structure in doc_schema.items():
    user_data[field] = render_field(field, structure)

st.divider()

# =====================================================
# VALIDATION
# =====================================================
def validate_data(data):
    errors = []

    def recurse(obj, path="root"):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if v in ["", None]:
                    errors.append(f"Missing: {path}.{k}")
                recurse(v, f"{path}.{k}")
        elif isinstance(obj, list):
            if len(obj) == 0:
                errors.append(f"Empty list: {path}")
            for i, item in enumerate(obj):
                recurse(item, f"{path}[{i}]")

    recurse(data)
    return errors

# =====================================================
# WORD DOC
# =====================================================

def create_word_document(text):
    doc = Document()
    
    # Split by lines and add paragraphs
    for line in text.split("\n"):
        doc.add_paragraph(line)

    file_stream = BytesIO()
    doc.save(file_stream)
    file_stream.seek(0)

    return file_stream

# =====================================================
# SUBMIT BUTTON
# =====================================================
if st.button("🚀 Generate Document"):

    errors = validate_data(user_data)

    if errors:
        st.error("⚠ Validation Errors")
        for e in errors:
            st.write(e)

    else:

        payload = {
            "category": category,
            "document_type": document,
            "content": user_data
        }

        with st.spinner("🤖 Generating document via LangChain + Azure OpenAI..."):

            try:

                response = requests.post(
                    "http://127.0.0.1:8000/generate",
                    json=payload,
                    timeout=120   # LLMs may take longer
                )

                # ------------------------------
                # SUCCESS
                # ------------------------------
                if response.status_code == 200:

                    result = response.json()
                    generated_text = result.get(
                        "generated_document",
                        "No content returned from LLM."
                    )

                    st.success("✅ Document Generated Successfully")

                    st.subheader("📄 Generated Document")
                    st.markdown(generated_text)

                    st.divider()
                    st.subheader("📥 Download Options")

                    col1, col2 = st.columns(2)

                    # TXT Download
                    with col1:
                        st.download_button(
                            label="⬇ Download as TXT",
                            data=generated_text,
                            file_name=f"{document}.txt",
                            mime="text/plain"
                        )

                    # WORD Download
                    with col2:
                        word_file = create_word_document(generated_text)

                        st.download_button(
                            label="⬇ Download as Word (.docx)",
                            data=word_file,
                            file_name=f"{document}.docx",
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                        )

                # ------------------------------
                # VALIDATION / 400 ERRORS
                # ------------------------------
                elif response.status_code == 400:
                    error_data = response.json()
                    st.error("⚠ Validation Error from Backend")
                    st.write(error_data.get("detail", error_data))

                # ------------------------------
                # SERVER / LLM ERRORS
                # ------------------------------
                else:
                    st.error("❌ Backend Error")
                    st.write(response.json())

            except requests.exceptions.Timeout:
                st.error("⏳ LLM generation timed out. Try again.")

            except Exception as e:
                st.error(f"Error connecting to backend: {e}")

st.sidebar.title("📚 Generated Documents History")

if st.sidebar.button("Load History"):

    response = requests.get("http://127.0.0.1:8000/documents")

    if response.ok:
        docs = response.json()

        for doc in docs:
            st.sidebar.write(
                f"ID: {doc['id']} | {doc['document_type']} | {doc['created_at']}"
            )
