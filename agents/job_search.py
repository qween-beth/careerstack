import os
import logging
from typing import Dict, Any, List
import requests
from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field

# Define models for job listings and search results
class JobListing(BaseModel):
    title: str = Field(description="Job title")
    company: str = Field(description="Company name")
    location: str = Field(description="Job location")
    match_score: float = Field(description="Percentage match with candidate profile (0-100)")
    requirements: List[str] = Field(description="Key job requirements")
    description: str = Field(description="Brief job description")
    salary_range: str = Field(description="Estimated salary range", default="Not provided")
    application_link: str = Field(description="Job application URL", default="")

class JobSearchResults(BaseModel):
    listings: List[JobListing] = Field(description="List of job listings")
    total_results: int = Field(description="Total number of job listings found")
    search_parameters: Dict[str, Any] = Field(description="Parameters used in the job search")

# Define the JobSearchAgent class
class JobSearchAgent:
    def __init__(self, llm: ChatGroq = None, api_key: str = None, temperature: float = 0.7, resume_analyzer=None):
        """
        Initialize Job Search Agent
        
        Args:
            llm (ChatGroq, optional): Language model for analysis
            api_key (str, optional): Groq API key
            temperature (float, optional): Creativity/randomness of model responses
            resume_analyzer: Optional ResumeAnalyzerAgent instance
        """
        # Initialize LLM
        if llm is None:
            api_key = api_key or os.getenv('GROQ_API_KEY')
            if not api_key:
                raise ValueError("Groq API key must be provided either as an argument or via GROQ_API_KEY environment variable")
            self.llm = ChatGroq(temperature=temperature, groq_api_key=api_key, model_name="llama3-70b-8192")
        else:
            self.llm = llm

        self.logger = logging.getLogger(__name__)
        self.resume_analyzer = resume_analyzer  # Optional ResumeAnalyzerAgent
        self.resume_context = None  # Placeholder for resume analysis
        self.job_search_apis = [
            "https://jobs.github.com/positions.json",
            "https://authenticjobs.com/api/", 
            "https://jobs.stackoverflow.com/api"
        ]

    def set_resume_context(self, resume_analysis: Dict[str, Any]):
        """
        Set resume context for personalized job searching
        
        Args:
            resume_analysis (Dict): Resume analysis from ResumeAnalyzerAgent
        """
        self.resume_context = {
            'key_skills': resume_analysis.get('Current_Profile', {}).get('Key_Skills', []),
            'experience_summary': resume_analysis.get('Current_Profile', {}).get('Experience_Summary', ''),
            'career_objectives': resume_analysis.get('Career_Context', {}).get('Objectives', ''),
            'recommended_job_titles': [
                job['Job_Title'] for job in resume_analysis.get('Career_Recommendations', [])
            ],
            'skill_gaps': resume_analysis.get('Development_Areas', {}).get('Skill_Gaps', {})
        }

    def _generate_advanced_search_query(self, base_query: str) -> str:
        """
        Generate enhanced job search query using resume context
        
        Args:
            base_query (str): Initial job search query
        
        Returns:
            str: Enriched search query
        """
        if not self.resume_context:
            return base_query

        # Prompt for LLM to create an enhanced query
        query_enhancement_prompt = PromptTemplate(
            template="""Enhance a job search query based on a candidate's profile:
            Candidate Profile:
            - Key Skills: {key_skills}
            - Experience Summary: {experience_summary}
            - Career Objectives: {career_objectives}
            - Recommended Job Titles: {recommended_job_titles}
            Original Query: {base_query}
            Return the enhanced search query.""",
            input_variables=["key_skills", "experience_summary", "career_objectives", "recommended_job_titles", "base_query"]
        )

        enhanced_query_chain = query_enhancement_prompt | self.llm

        try:
            enhanced_query_result = enhanced_query_chain.invoke({
                "key_skills": ", ".join(self.resume_context.get('key_skills', [])),
                "experience_summary": self.resume_context.get('experience_summary', ''),
                "career_objectives": self.resume_context.get('career_objectives', ''),
                "recommended_job_titles": ", ".join(self.resume_context.get('recommended_job_titles', [])),
                "base_query": base_query
            })
            return enhanced_query_result.content.strip()
        except Exception as e:
            self.logger.warning(f"Query enhancement failed: {e}")
            return base_query

    def _fetch_job_listings(self, query: str) -> List[Dict[str, Any]]:
        """
        Fetch job listings from external APIs
        
        Args:
            query (str): Job search query
        
        Returns:
            List of job listings
        """
        combined_listings = []
        for api_url in self.job_search_apis:
            try:
                response = requests.get(api_url, params={'description': query, 'location': 'remote'})
                if response.status_code == 200:
                    listings = response.json().get('jobs', [])
                    combined_listings.extend(listings)
            except Exception as e:
                self.logger.warning(f"Error searching {api_url}: {e}")
        return combined_listings

    def process(self, query: str, resume_path: str = None) -> Dict[str, Any]:
        """
        Execute job search with optional resume analysis
        
        Args:
            query (str): Job search query
            resume_path (str, optional): Path to resume PDF
        
        Returns:
            Dict with job search results
        """
        # Analyze resume if provided and analyzer is available
        if resume_path and os.path.exists(resume_path) and self.resume_analyzer:
            try:
                resume_analysis = self.resume_analyzer.analyze_resume(resume_path)
                self.set_resume_context(resume_analysis)
            except Exception as e:
                self.logger.warning(f"Resume analysis failed: {e}")

        # Enhance query if resume context exists
        enhanced_query = self._generate_advanced_search_query(query)

        # Fetch and process job listings
        raw_listings = self._fetch_job_listings(enhanced_query)
        processed_listings = [
            JobListing(
                title=job.get('title', 'Untitled Position'),
                company=job.get('company', 'Unknown Company'),
                location=job.get('location', 'Remote/Unspecified'),
                match_score=50.0,  # Placeholder for match score
                requirements=job.get('requirements', []),
                description=job.get('description', 'No description available'),
                salary_range=job.get('salary', 'Not provided'),
                application_link=job.get('url', '')
            )
            for job in raw_listings
        ]

        # Return top 10 listings
        return {
            "status": "success",
            "results": JobSearchResults(
                listings=processed_listings[:10],
                total_results=len(processed_listings),
                search_parameters={"query": query, "resume_used": bool(self.resume_context)}
            ).dict()
        }
