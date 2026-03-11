import os
import json
from dotenv import load_dotenv
from langchain_openai import AzureChatOpenAI

load_dotenv()

llm = AzureChatOpenAI(
    api_key=os.getenv("AZURE_OPENAI_LLM_KEY"),
    azure_endpoint=os.getenv("AZURE_OPENAI_LLM_ENDPOINT"),
    api_version=os.getenv("AZURE_OPENAI_LLM_API_VERSION"),
    deployment_name=os.getenv("AZURE_OPENAI_LLM_DEPLOYMENT"),
    temperature=0.3
)

# Document types that should be generated as Excel/tabular format
TABULAR_KEYWORDS = [
    "balance sheet", "profit and loss", "p&l", "income statement",
    "cash flow", "trial balance", "depreciation schedule",
    "amortization schedule", "loan schedule", "budget", "forecast",
    "projection", "expense report", "cost breakdown", "payroll",
    "inventory", "fixed asset", "tax schedule", "accounts receivable",
    "accounts payable", "aging report", "kpi", "sales report",
    "financial summary", "schedule", "statement", "ledger",
]


def detect_doc_format(title: str, sections: list) -> str:
    """
    Returns 'excel' if the document is tabular/financial,
    'word' otherwise.
    """
    combined = (title + " " + " ".join(sections)).lower()
    if any(kw in combined for kw in TABULAR_KEYWORDS):
        return "excel"
    return "word"


def plan_document(user_prompt: str) -> dict:
    prompt = f"""
You are a professional document architect.

User Request:
{user_prompt}

Determine:
1. Proper document title
2. Professional sections commonly used for this document type
3. Whether this document is best represented as:
   - "excel" (tabular data: financial statements, schedules, budgets, reports with rows/columns)
   - "word" (prose document: SOPs, business plans, policies, proposals)

Return strictly valid JSON:

{{
  "title": "Document Title",
  "sections": ["Section 1", "Section 2"],
  "doc_format": "excel"
}}

For financial documents (balance sheet, P&L, cash flow, schedules, budgets):
  → always use "excel"
For narrative documents (SOP, business plan, policy, proposal):
  → always use "word"
For "Employee Handbook": 
  → generate 15-20 sections covering key policies, code of conduct, benefits, etc. and use "word"

No explanation. No markdown. Only JSON.
"""

    response = llm.invoke(prompt).content.strip()

    # Clean markdown fences
    if response.startswith("```"):
        response = response.split("```")[1]
        if response.startswith("json"):
            response = response[4:]
    response = response.strip()

    result = json.loads(response)

    # Safety net: if LLM didn't return doc_format, detect it ourselves
    if "doc_format" not in result:
        result["doc_format"] = detect_doc_format(
            result.get("title", ""),
            result.get("sections", [])
        )

    return result