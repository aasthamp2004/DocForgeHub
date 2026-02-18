mport os
from openai import AzureOpenAI
from dotenv import load_dotenv

load_dotenv()

llm_client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_LLM_KEY"),
    api_version=os.getenv("AZURE_OPENAI_LLM_API_VERSION"),
    azure_endpoint=os.getenv("AZURE_OPENAI_LLM_ENDPOINT"),
)

LLM_DEPLOYMENT = os.getenv("AZURE_OPENAI_LLM_DEPLOYMENT")


def generate_document(category: str, document_type: str, content: dict):

    prompt = f"""
    You are a professional enterprise document generator.

    Industry: {category}
    Document Type: {document_type}

    Structured Input:
    {content}

    Generate a well-structured, formal, industry-ready document.
    Include headings and proper formatting.
    """

    response = llm_client.chat.completions.create(
        model=LLM_DEPLOYMENT,  # Azure uses deployment name here
        messages=[
            {"role": "system", "content": "You are an expert business document writer."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7,
        max_tokens=1500
    )

    return response.choices[0].message.content
