import os
import logging
from typing import Dict, Any, List

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage

# Import individual agents
from .job_search import JobSearchAgent
from .resume_analyzer import ResumeAnalyzerAgent
from .cover_letter_generator import CoverLetterAgent
from .web_researcher import ScrapyWebResearchAgent

class JobAssistantSupervisor:
    def __init__(self, temperature: float = 0.7):
        """
        Initialize the job assistant with multiple specialized agents
        
        Args:
            temperature (float): Controls randomness in language model responses
        """
        self.resume_path = None
        self.conversation_history: List[BaseMessage] = []
        self.llm = ChatOpenAI(temperature=temperature)
        self.agents = {}
        self.logger = logging.getLogger(__name__)
        logging.basicConfig(level=logging.INFO)

        # Dynamically register agents
        self._register_agents()

    def _register_agents(self):
        """
        Register all specialized agents.
        """
        self.agents = {
            'job_search': JobSearchAgent(self.llm),
            'resume_analyzer': ResumeAnalyzerAgent(self.llm),
            'cover_letter': CoverLetterAgent(self.llm),
            'web_researcher': ScrapyWebResearchAgent  # Store the class, not an instance
        }
        
        # Setup logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
    
    def set_resume(self, resume_path: str) -> Dict[str, Any]:
        """
        Set and analyze the uploaded resume
        
        Args:
            resume_path (str): Path to the uploaded resume PDF
        
        Returns:
            Dict with resume insights
        """
        if not os.path.exists(resume_path):
            raise FileNotFoundError(f"Resume not found at {resume_path}")
        
        self.resume_path = resume_path
        
        # Analyze resume using resume analyzer agent
        resume_insights = self.agents['resume_analyzer'].analyze_resume(resume_path)
        
        self.logger.info(f"Resume analyzed: {resume_insights}")
        return resume_insights
    
    def process_query(self, query: str) -> Dict[str, Any]:
        """
        Process user query by routing to the appropriate agent.
        
        Args:
            query (str): User's input query.
        
        Returns:
            Dict with agent's response and metadata.
        """
        # Classify query intent
        intent = self._classify_intent(query)
        
        try:
            # Handle web research separately due to Scrapy-based implementation
            if intent == 'research':
                # Create a new instance of ScrapyWebResearchAgent for each query
                web_researcher = self.agents['web_researcher'](query)
                research_results = web_researcher.run_research()
                return {
                    'intent': intent,
                    'response': research_results,
                    'agent': 'ScrapyWebResearchAgent'
                }
            
            # Handle unknown intent
            if intent == 'unknown':
                return {
                    "intent": "unknown",
                    "response": "Please clarify your query.",
                    "agent": None
                }
            
            # Process query with the selected agent
            selected_agent = self._select_agent(intent)
            response = selected_agent.process(query, resume_path=self.resume_path)
            
            # Format response based on agent type and response structure
            formatted_response = self._format_agent_response(intent, response)
            
            # Log the interaction
            self.logger.info(f"Processed query with intent '{intent}'.")
            
            return {
                "intent": intent,
                "response": formatted_response,
                "agent": type(selected_agent).__name__
            }
        
        except KeyError as e:
            self.logger.error(f"Agent for intent '{intent}' is not available: {e}")
            return {
                "intent": intent,
                "response": "The requested operation could not be performed.",
                "error": str(e),
                "agent": None
            }
        except Exception as e:
            self.logger.error(f"Error processing query with intent '{intent}': {e}")
            return {
                "intent": intent,
                "response": "An error occurred while processing your request.",
                "error": str(e),
                "agent": None
            }
    
    def _format_agent_response(self, intent: str, response: Dict[str, Any]) -> str:
        """
        Format the agent response based on intent and response structure
        
        Args:
            intent (str): Query intent
            response (Dict[str, Any]): Agent response
        
        Returns:
            str: Formatted response
        """
        if intent == 'cover_letter':
            if response.get("status") == "error":
                return f"Error generating cover letter: {response.get('message', 'Unknown error')}"
            
            # Return the actual cover letter content
            return response.get("content", "No cover letter content generated")
            
        elif intent == 'job_search':
            # Format job search results
            if response.get("status") == "error":
                return f"Error searching jobs: {response.get('message', 'Unknown error')}"
                
            results = response.get("results", {})
            listings = results.get("listings", [])
            
            if not listings:
                return "No job listings found matching your criteria."
                
            # Format each job listing
            formatted_jobs = []
            for job in listings:
                formatted_job = (
                    f"Position: {job['title']}\n"
                    f"Company: {job['company']}\n"
                    f"Location: {job['location']}\n"
                    f"Match Score: {job['match_score']:.0%}\n"
                    f"Requirements: {', '.join(job['requirements'])}\n"
                    f"---"
                )
                formatted_jobs.append(formatted_job)
    
            return "\n\n".join(formatted_jobs)
            
        elif intent == 'resume':
            # Format resume analysis
            if isinstance(response, dict):
                return "\n".join([f"{k}: {v}" for k, v in response.items()])
            return str(response)
            
        # Default formatting for other responses
        return str(response)
    
    def _classify_intent(self, query: str) -> str:
        """
        Classify user query intent
        
        Args:
            query (str): User input query
        
        Returns:
            str: Classified intent
        """
        query = query.lower()
        intents_mapping = {
            'job_search': ['job', 'position', 'career', 'opportunity'],
            'cover_letter': ['cover letter', 'application', 'recommendation'],
            'resume': ['resume', 'cv', 'skill', 'experience'],
            'research': ['research', 'information', 'learn', 'find out']
        }
        for intent, keywords in intents_mapping.items():
            if any(keyword in query for keyword in keywords):
                return intent
        return 'unknown'  # Fallback intent
    
    def _select_agent(self, intent: str):
        """
        Select the appropriate agent based on intent
        
        Args:
            intent (str): Query intent
        
        Returns:
            Agent instance
        """
        agent_mapping = {
            'job_search': self.agents['job_search'],
            'cover_letter': self.agents['cover_letter'],
            'resume': self.agents['resume_analyzer']
        }
        
        return agent_mapping.get(intent, self.agents['resume_analyzer'])