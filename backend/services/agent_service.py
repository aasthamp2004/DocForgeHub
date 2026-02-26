import os
from dotenv import load_dotenv
from typing import Dict

from langchain_openai import AzureChatOpenAI
from langchain.agents import create_agent
from langchain_core.tools import tool


# =====================================================
# LOAD ENV VARIABLES
# =====================================================

load_dotenv()


# =====================================================
# LLM INITIALIZATION (Azure OpenAI)
# =====================================================

llm = AzureChatOpenAI(
    api_key=os.getenv("AZURE_OPENAI_LLM_KEY"),
    azure_endpoint=os.getenv("AZURE_OPENAI_LLM_ENDPOINT"),
    api_version=os.getenv("AZURE_OPENAI_LLM_API_VERSION"),
    azure_deployment=os.getenv("AZURE_OPENAI_LLM_DEPLOYMENT"),
    temperature=0.7
)


# =====================================================
# TOOL 1: CLARIFICATION TOOL
# =====================================================

@tool
def clarify_requirements(user_input: str) -> str:
    """
    Checks whether sufficient information is provided
    for enterprise document generation.

    If missing details → ask structured follow-up questions.
    If sufficient → return 'SUFFICIENT INFORMATION'.
    """
    response = llm.invoke(
        f"""
        You are an enterprise documentation analyst.

        Check if the following information is sufficient
        to generate a high-quality professional document.

        If important details are missing,
        ask clear and structured follow-up questions.

        If sufficient, respond ONLY with:
        SUFFICIENT INFORMATION

        User Input:
        {user_input}
        """
    )

    return response.content


# =====================================================
# AGENT CREATION (LangChain 1.x Correct API)
# =====================================================

tools = [clarify_requirements]

agent = create_agent(
    model=llm,
    tools=tools,
    system_prompt="""
    You are an intelligent enterprise document generation agent.

    Step 1:
    Check if the user input is sufficient using clarify_requirements tool.

    Step 2:
    If sufficient → generate full professional document.
    If not sufficient → ask structured follow-up questions.

    Always ensure professional formatting with headings.
    """
)


# =====================================================
# MAIN ENTRY FUNCTION
# =====================================================

def generate_document(category: str, document_type: str, content: Dict):

    user_context = f"""
    Industry: {category}
    Document Type: {document_type}
    Structured Input: {content}
    """

    # Step 1 — Run agent
    result = agent.invoke({
        "messages": [
            {"role": "user", "content": user_context}
        ]
    })

    # Extract last message
    output = result["messages"][-1].content

    # Step 2 — If clarification needed
    if "SUFFICIENT INFORMATION" not in output:
        return {
            "status": "clarification_needed",
            "questions": output
        }

    # Step 3 — Generate full structured document
    final_doc = llm.invoke(
        f"""
        Generate a detailed, structured, professional enterprise document.

        Industry: {category}
        Document Type: {document_type}
        Content: {content}

        Use proper headings, formatting, and structured flow.
        """
    )

    return {
        "status": "success",
        "document": final_doc.content
    }
