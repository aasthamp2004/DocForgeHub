from backend.services.langchain_service import llm


def refine_section(section_name, original_text, user_feedback):

    prompt = f"""
You are a professional editor.

Section: {section_name}

Original Content:
{original_text}

User Feedback:
{user_feedback}

Rewrite this section incorporating the feedback.
Return only the improved section text.
"""

    response = llm.invoke(prompt)
    return response.content