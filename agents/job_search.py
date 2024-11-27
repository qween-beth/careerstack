import os
from typing import Dict, List, Any, Optional
import logging
from datetime import datetime
import requests
from bs4 import BeautifulSoup
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from pydantic import BaseModel, Field
from .resume_analyzer import ResumeAnalyzerAgent

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class JobSearchResult(BaseModel):
    title: str = Field(description="Job title")
    company: str = Field(description="Company name")
    location: str = Field(description="Job location")
    match_score: float = Field(description="Relevance score to resume")
    url: str = Field(description="Job listing URL")
    description: str = Field(description="Job description")
    posted_date: str = Field(description="Job posting date")
    skill_matches: List[str] = Field(description="Matching skills from resume")
    missing_skills: List[str] = Field(description="Required skills not found in resume")

class JobSearchAgent:
    def __init__(self, llm: ChatOpenAI):
        """
        Initialize Integrated Job Search Agent
        
        Args:
            llm (ChatOpenAI): Language model for analysis
        """
        self.llm = llm
        self.resume_analyzer = ResumeAnalyzerAgent(llm)
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

    def _search_jobs(self, search_params: Dict[str, Any]) -> List[Dict]:
        """
        Search jobs using public APIs
        
        Args:
            search_params: Dictionary containing search parameters
            
        Returns:
            List of job listings
        """
        try:
            # Initialize empty list for all jobs
            all_jobs = []
            
            # Use GitHub Jobs API (public)
            github_jobs = self._search_github_jobs(search_params)
            if github_jobs:
                all_jobs.extend(github_jobs)
            
            # Use Indeed API if you have API key
            if os.getenv('INDEED_API_KEY'):
                indeed_jobs = self._search_indeed_jobs(search_params)
                if indeed_jobs:
                    all_jobs.extend(indeed_jobs)
            
            return all_jobs

        except Exception as e:
            logger.error(f"Job search failed: {e}")
            return []

    def _search_github_jobs(self, search_params: Dict[str, Any]) -> List[Dict]:
        """
        Search GitHub Jobs
        """
        try:
            base_url = "https://jobs.github.com/positions.json"
            params = {
                'description': search_params["position"],
                'location': search_params["location"],
                'full_time': 'true'
            }
            
            response = requests.get(base_url, params=params, headers=self.headers)
            if response.status_code == 200:
                jobs = response.json()
                return [{
                    'title': job.get('title'),
                    'company': job.get('company'),
                    'location': job.get('location'),
                    'url': job.get('url'),
                    'description': job.get('description'),
                    'posted_date': job.get('created_at')
                } for job in jobs]
            return []
        except Exception as e:
            logger.warning(f"GitHub Jobs search failed: {e}")
            return []

    def _search_indeed_jobs(self, search_params: Dict[str, Any]) -> List[Dict]:
        """
        Search Indeed Jobs if API key is available
        """
        api_key = os.getenv('INDEED_API_KEY')
        if not api_key:
            return []
            
        try:
            base_url = "https://api.indeed.com/ads/apisearch"
            params = {
                'publisher': api_key,
                'q': search_params["position"],
                'l': search_params["location"],
                'format': 'json',
                'v': '2',
                'limit': 25
            }
            
            response = requests.get(base_url, params=params, headers=self.headers)
            if response.status_code == 200:
                data = response.json()
                return [{
                    'title': job.get('jobtitle'),
                    'company': job.get('company'),
                    'location': job.get('formattedLocation'),
                    'url': job.get('url'),
                    'description': job.get('snippet'),
                    'posted_date': job.get('formattedRelativeTime')
                } for job in data.get('results', [])]
            return []
        except Exception as e:
            logger.warning(f"Indeed Jobs search failed: {e}")
            return []

    def _match_jobs_to_analysis(self, jobs: List[Dict], resume_analysis: Dict[str, Any]) -> List[JobSearchResult]:
        """
        Match jobs using the resume analysis results
        """
        current_profile = resume_analysis["Current Profile"]
        skill_gaps = resume_analysis["Development Areas"]["Skill Gaps"]
        matched_jobs = []
        
        for job in jobs:
            try:
                prompt = PromptTemplate.from_template("""
                    Analyze this job posting against the candidate's profile:
                    
                    Job Title: {title}
                    Job Description: {description}
                    
                    Candidate Skills: {skills}
                    Candidate Experience: {experience}
                    
                    Provide:
                    1. Match score (0-100)
                    2. List of matching skills
                    3. List of missing skills required for this role
                    
                    Format as: Score: X, Matching Skills: [skills], Missing Skills: [skills]
                """)
                
                result = self.llm.invoke(prompt.format(
                    title=job["title"],
                    description=job["description"],
                    skills=", ".join(current_profile["Key Skills"]),
                    experience=current_profile["Experience Summary"]
                ))
                
                # Parse the response
                parts = str(result).split(", ")
                score = float(parts[0].split(": ")[1])
                matching_skills = parts[1].split(": ")[1].strip("[]").split(", ")
                missing_skills = parts[2].split(": ")[1].strip("[]").split(", ")
                
                matched_jobs.append(JobSearchResult(
                    title=job["title"],
                    company=job["company"],
                    location=job["location"],
                    match_score=score,
                    url=job["url"],
                    description=job["description"],
                    posted_date=job["posted_date"],
                    skill_matches=matching_skills,
                    missing_skills=missing_skills
                ))
                
            except Exception as e:
                logger.warning(f"Job matching error: {e}")
                continue
        
        return sorted(matched_jobs, key=lambda x: x.match_score, reverse=True)

    def search_jobs(self, resume_path: str, query: str) -> Dict[str, Any]:
        """
        Main job search method with chat integration
        """
        try:
            # Get resume analysis
            resume_analysis = self.resume_analyzer.analyze_resume(resume_path)
            
            # Get search preferences from query instead of terminal input
            search_params = self._get_search_preferences(resume_analysis, query)
            
            # Search jobs
            raw_jobs = self._search_jobs(search_params)
            
            if not raw_jobs:
                return {
                    "status": "no_results",
                    "message": "No jobs found matching your criteria. Try broadening your search or changing location.",
                    "resume_analysis": resume_analysis,
                    "search_criteria": search_params
                }
            
            # Match jobs
            matched_jobs = self._match_jobs_to_analysis(raw_jobs, resume_analysis)
            
            # Format response for chat interface
            response = {
                "status": "success",
                "message": self._format_chat_response(matched_jobs, search_params),
                "results": {
                    "resume_analysis": {
                        "skills": resume_analysis["Current Profile"]["Key Skills"],
                        "experience": resume_analysis["Current Profile"]["Experience Summary"],
                        "career_objectives": resume_analysis["Career Context"]["Objectives"]
                    },
                    "search_criteria": search_params,
                    "total_jobs": len(matched_jobs),
                    "top_matches": [
                        {
                            "title": job.title,
                            "company": job.company,
                            "location": job.location,
                            "match_score": job.match_score,
                            "url": job.url,
                            "posted_date": job.posted_date,
                            "matching_skills": job.skill_matches,
                            "skills_to_develop": job.missing_skills,
                            "description_preview": job.description[:200] + "..."
                        } for job in matched_jobs[:5]
                    ]
                }
            }
            
            return response
            
        except Exception as e:
            logger.error(f"Job search failed: {e}")
            return {
                "status": "error",
                "message": f"Job search failed: {str(e)}",
                "resume_analysis": resume_analysis if 'resume_analysis' in locals() else None,
                "search_criteria": search_params if 'search_params' in locals() else None
            }

    def _format_chat_response(self, matched_jobs: List[JobSearchResult], search_params: Dict[str, Any]) -> str:
        """Format job search results for chat interface"""
        if not matched_jobs:
            return "I couldn't find any matching jobs. Try adjusting your search criteria."
            
        response_parts = [
            f"I found {len(matched_jobs)} jobs matching your search for {search_params['position']} "
            f"in {search_params['location'] or 'any location'}. Here are the top matches:\n"
        ]
        
        for i, job in enumerate(matched_jobs[:5], 1):
            response_parts.append(
                f"{i}. {job.title} at {job.company}\n"
                f"📍 {job.location}\n"
                f"Match Score: {job.match_score}%\n"
                f"Posted: {job.posted_date}\n"
                f"Matching Skills: {', '.join(job.skill_matches[:3])}...\n"
                f"Skills to Develop: {', '.join(job.missing_skills[:3])}...\n"
                f"More Info: {job.url}\n"
            )
        
        response_parts.append("\nWould you like to refine your search or learn more about any of these positions?")
        return "\n".join(response_parts)
    

    def _get_search_preferences(self, resume_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Get search preferences from user"""
        search_params = self._extract_search_parameters(resume_analysis)
        
        print("\n=== Job Search Preferences ===")
        print("\nBased on your resume analysis:")
        print(f"- Recommended roles: {', '.join(search_params['recent_titles'])}")
        print(f"- Key skills: {', '.join(search_params['skills'][:5])}")
        
        position = input("\nWhat position are you looking for? (Press Enter for top recommendation): ").strip()
        if not position:
            position = search_params['recent_titles'][0]
        
        location = input("\nWhere would you like to work?: ").strip()
        
        return {
            "position": position,
            "location": location,
            "skills": search_params['skills'],
            "industry_keywords": search_params['industry_keywords']
        }

    def _extract_search_parameters(self, resume_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Extract search parameters from resume analysis"""
        current_profile = resume_analysis.get("Current Profile", {})
        career_context = resume_analysis.get("Career Context", {})
        recommendations = resume_analysis.get("Career Recommendations", [])
        
        return {
            "skills": current_profile.get("Key Skills", []),
            "recent_titles": [rec["Job Title"] for rec in recommendations[:3]],
            "industry_keywords": career_context.get("Industry Keywords", [])
        }

    
    def process(self, query: str, resume_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Process a job search query
        
        Args:
            query (str): User's job search query
            resume_path (Optional[str]): Path to user's resume
            
        Returns:
            Dict containing search results and status
        """
        if not resume_path:
            return {
                "status": "error",
                "message": "Resume path is required for job search"
            }
        
        try:
            # Extract search parameters from query
            search_params = self._parse_query(query)
            
            # Perform the job search
            results = self.search_jobs(resume_path)
            
            # Format the response
            return {
                "status": "success",
                "results": {
                    "listings": [
                        {
                            "title": job["title"],
                            "company": job["company"],
                            "location": job["location"],
                            "match_score": job["match_score"],
                            "requirements": job.get("matching_skills", []),
                            "url": job.get("url", ""),
                            "description": job.get("description_preview", "")
                        }
                        for job in results.get("top_matches", [])
                    ],
                    "total_found": results.get("total_jobs", 0),
                    "search_criteria": results.get("search_criteria", {})
                }
            }
            
        except Exception as e:
            logger.error(f"Error processing job search query: {e}")
            return {
                "status": "error",
                "message": str(e)
            }

    def _parse_query(self, query: str) -> Dict[str, str]:
        """
        Parse the search query to extract relevant parameters
        
        Args:
            query (str): User's search query
            
        Returns:
            Dict with parsed search parameters
        """
        # Use the LLM to extract search parameters
        prompt = PromptTemplate.from_template("""
            Extract job search parameters from this query:
            {query}
            
            Return only:
            Position: [job title]
            Location: [location]
        """)
        
        result = str(self.llm.invoke(prompt.format(query=query)))
        
        # Parse the response
        params = {}
        for line in result.split('\n'):
            if ':' in line:
                key, value = line.split(':', 1)
                params[key.strip().lower()] = value.strip().strip('[]')
        
        return {
            "position": params.get("position", ""),
            "location": params.get("location", "")
        }