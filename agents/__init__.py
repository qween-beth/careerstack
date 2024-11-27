# Import all agents to make them easily accessible
from .supervisor import JobAssistantSupervisor
from .job_search import JobSearchAgent
from .resume_analyzer import ResumeAnalyzerAgent
from .cover_letter_generator import CoverLetterAgent
from .web_researcher import ScrapyWebResearchAgent

__all__ = [
    'JobAssistantSupervisor',
    'JobSearchAgent',
    'ResumeAnalyzerAgent',
    'CoverLetterAgent',
    'ScrapyWebResearchAgent'
]