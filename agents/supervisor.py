import os
import logging
from typing import Dict, Any, List

from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage

# Import individual agents
from .job_search import JobSearchAgent
from .resume_analyzer import ResumeAnalyzerAgent
from .cover_letter_generator import CoverLetterAgent
from .web_researcher import ScrapyWebResearchAgent


class JobAssistantSupervisor:
    def __init__(self, temperature: float = 0.7, api_key: str = None):
        """
        Initialize the job assistant with multiple specialized agents using Groq.

        Args:
            temperature (float): Controls randomness in language model responses.
            api_key (str, optional): Groq API key. If not provided, uses GROQ_API_KEY environment variable.
        """
        self.resume_path = None
        self.resume_insights = None
        self.conversation_history: List[BaseMessage] = []

        # Set up API key and language model
        api_key = api_key or os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("Groq API key must be provided via argument or GROQ_API_KEY environment variable.")
        self.llm = ChatGroq(
            temperature=temperature,
            groq_api_key=api_key,
            model_name="llama3-70b-8192",
        )

        self.agents = self._register_agents()
        self.logger = self._setup_logger()

    @staticmethod
    def _setup_logger() -> logging.Logger:
        """Set up logging."""
        logger = logging.getLogger(__name__)
        logging.basicConfig(level=logging.INFO)
        return logger

    def _register_agents(self) -> Dict[str, Any]:
        """
        Register all specialized agents.

        Returns:
            Dict of registered agents.
        """
        return {
            "job_search": JobSearchAgent(self.llm),
            "resume_analyzer": ResumeAnalyzerAgent(self.llm),
            "cover_letter": CoverLetterAgent(self.llm),
            "web_researcher": ScrapyWebResearchAgent,  # Store the class for instantiation
        }

    def set_resume(self, resume_path: str) -> Dict[str, Any]:
        """
        Set and analyze the uploaded resume.

        Args:
            resume_path (str): Path to the uploaded resume PDF.

        Returns:
            Dict with resume insights.
        """
        if not os.path.exists(resume_path):
            raise FileNotFoundError(f"Resume not found at {resume_path}")

        self.resume_path = resume_path
        self.resume_insights = self.agents["resume_analyzer"].analyze_resume(resume_path)

        # Share resume context with other agents
        for agent_name in ["job_search", "cover_letter"]:
            agent = self.agents.get(agent_name)
            if hasattr(agent, "set_resume_context"):
                agent.set_resume_context(self.resume_insights)

        self.logger.info("Resume analyzed and context shared with agents.")
        return self.resume_insights

    def process_query(self, query: str) -> Dict[str, Any]:
        """
        Process user query by routing to the appropriate agent.

        Args:
            query (str): User's input query.

        Returns:
            Dict with agent's response and metadata.
        """
        intent = self._classify_intent(query)

        try:
            if intent == "research":
                research_results = self._handle_web_research(query)
                return {"intent": intent, "response": research_results, "agent": "ScrapyWebResearchAgent"}

            if intent == "unknown":
                return {"intent": "unknown", "response": "Please clarify your query.", "agent": None}

            response = self._process_with_agent(intent, query)
            return {"intent": intent, "response": response, "agent": intent.capitalize() + "Agent"}

        except KeyError:
            self.logger.error(f"Agent for intent '{intent}' not available.")
            return {"intent": intent, "response": "Agent not available.", "error": "Agent missing.", "agent": None}

        except Exception as e:
            self.logger.error(f"Error processing query: {e}")
            return {"intent": intent, "response": "An error occurred.", "error": str(e), "agent": None}

    def _process_with_agent(self, intent: str, query: str) -> str:
        """
        Process the query using the appropriate agent.

        Args:
            intent (str): Classified intent.
            query (str): User's input query.

        Returns:
            str: Formatted response.
        """
        agent = self.agents[intent]
        resume_path = self.resume_path if intent in ["job_search", "cover_letter"] else None
        response = agent.process(query, resume_path=resume_path)
        return self._format_response(intent, response)

    def _handle_web_research(self, query: str) -> Any:
        """
        Handle queries related to web research.

        Args:
            query (str): User's input query.

        Returns:
            Any: Research results.
        """
        web_researcher = self.agents["web_researcher"](query)
        return web_researcher.run_research()

    def _classify_intent(self, query: str) -> str:
        """
        Classify user query intent.

        Args:
            query (str): User input query.

        Returns:
            str: Classified intent.
        """
        query = query.lower()
        intents_mapping = {
            "job_search": ["job", "position", "career", "opportunity", "roles"],
            "cover_letter": ["cover letter", "application", "recommendation", "letter"],
            "resume": ["resume", "cv", "skill", "experience", "profile"],
            "research": ["research", "information", "learn", "find out", "details"],
        }
        for intent, keywords in intents_mapping.items():
            if any(keyword in query for keyword in keywords):
                return intent
        return "unknown"

    def _format_response(self, intent: str, response: Dict[str, Any]) -> str:
        """
        Format the agent response based on intent.

        Args:
            intent (str): Query intent.
            response (Dict[str, Any]): Agent response.

        Returns:
            str: Formatted response.
        """
        if response.get("status") == "error":
            return response.get("message", "An error occurred.")

        if intent == "job_search":
            listings = response.get("results", {}).get("listings", [])
            if not listings:
                return "No job listings found."

            return "\n\n".join(
                f"Position: {job['title']}\n"
                f"Company: {job['company']}\n"
                f"Location: {job['location']}\n"
                f"Match Score: {job['match_score']:.0f}%\n"
                f"Requirements: {', '.join(job['requirements'])}\n---"
                for job in listings
            )

        if intent == "cover_letter":
            return response.get("content", "No cover letter content generated.")

        if intent == "resume":
            return "\n".join(f"{k}: {v}" for k, v in response.items())

        return str(response)