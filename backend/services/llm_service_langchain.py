mport os
from dotenv import load_dotenv

from langchain_openai import AzureChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

load_dotenv()


class LLMService:

    def __init__(self):

        self.llm = AzureChatOpenAI(
            azure_endpoint=os.getenv("AZURE_OPENAI_LLM_ENDPOINT"),
            api_key=os.getenv("AZURE_OPENAI_LLM_KEY"),
            api_version=os.getenv("AZURE_OPENAI_LLM_API_VERSION"),
            deployment_name=os.getenv("AZURE_OPENAI_LLM_DEPLOYMENT"),
            temperature=0.2
        )

    # ✅ industry removed
    def build_prompt(self, category, document_type, user_data):

        system_prompt = f"""
You are a professional document generation AI.

Your task:
Generate a complete, professional, well-structured {document_type}
under the {category} category.

Rules:
- Use clear headings
- Maintain professional tone
- Expand on given inputs intelligently
- Fill missing context logically
- Make it business ready
"""

        human_prompt = f"""
Here is the structured input data provided by the user:

{user_data}

Generate the final document now.
"""

        return [
            SystemMessage(content=system_prompt.strip()),
            HumanMessage(content=human_prompt.strip())
        ]

    # ✅ industry removed
    def generate_document(self, category, document_type, user_data):

        messages = self.build_prompt(
            category,
            document_type,
            user_data
        )

        response = self.llm.invoke(messages)

        return response.content
