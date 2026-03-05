import json
from backend.services.langchain_service import llm


def generate_document_sections(title, sections, user_answers):

    # Separate filled answers from empty ones so LLM knows what was provided
    filled = {q: a for q, a in user_answers.items() if str(a).strip()}
    empty_sections = [s for s in sections if not any(
        s.lower() in q.lower() for q in filled
    )]

    prompt = f"""
You are a professional document writer with deep expertise across business, legal, technical, and operational domains.

Document Title: {title}
Sections to write: {sections}

User-provided context:
{json.dumps(filled, indent=2) if filled else "No specific inputs provided."}

Instructions:
1. Write detailed, professional content for EVERY section listed above.
2. For sections where the user provided context, incorporate their input naturally.
3. For sections where NO input was provided, generate realistic, high-quality professional content
   appropriate for a "{title}" document — do NOT write "No content provided" or leave sections empty.
4. Each section should be 2-5 sentences minimum with substance and detail.
5. Use industry-standard language and structure.

Return strictly valid JSON with this exact structure:
{{
  "Section Name": "Full generated content here as a string",
  "Another Section": "Full generated content here"
}}

No explanation. No markdown. Only JSON.
"""

    response = llm.invoke(prompt)
    raw = response.content.strip()

    # Strip markdown fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    result = json.loads(raw)

    # Safety net: replace any empty/placeholder values with a retry
    empty_keys = [k for k, v in result.items() if not str(v).strip()
                  or str(v).lower() in ("no content provided.", "no content provided", "n/a", "")]

    if empty_keys:
        retry_prompt = f"""
You are a professional document writer.
Document: {title}

Write content for these specific sections: {empty_keys}
Generate realistic, professional content for each — do not leave anything empty.

Return strictly valid JSON:
{{
  "Section Name": "Content here"
}}
No explanation. No markdown. Only JSON.
"""
        retry_response = llm.invoke(retry_prompt)
        retry_raw = retry_response.content.strip()
        if retry_raw.startswith("```"):
            retry_raw = retry_raw.split("```")[1]
            if retry_raw.startswith("json"):
                retry_raw = retry_raw[4:]
        try:
            retry_result = json.loads(retry_raw.strip())
            result.update(retry_result)
        except Exception:
            pass

    return result