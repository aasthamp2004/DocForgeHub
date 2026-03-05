from backend.services.planner_agent import generate_document_sections
from backend.services.question_agent import generate_questions
from backend.services.generator_agent import generate_document


class DocumentOrchestrator:

    def plan(self, category, document_type):
        return generate_document_sections(category, document_type)

    def ask_questions(self, sections):
        return generate_questions(sections)

    def generate(self, document_type, answers):
        return generate_document(document_type, answers)