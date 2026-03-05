import json
from backend.services.planner_agent import llm


def generate_questions(title, sections):

    prompt = f"""
You are an intelligent business analyst.

Document Title:
{title}

Sections:
{sections}

For each section, generate 3-5 important input questions required to write that section.

Return strict JSON format:

{{
  "Section Name": ["Question 1", "Question 2"]
}}

No explanation.
No markdown.
"""

    response = llm.invoke(prompt).content.strip()
    return json.loads(response)