import os
import spacy
import PyPDF2
import logging
from typing import Dict, Any, List
from langchain_groq import ChatGroq  # Changed from OpenAI import
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field
from datetime import datetime

class JobRecommendation(BaseModel):
    title: str = Field(description="Recommended job title")
    match_score: float = Field(description="Score indicating how well the candidate matches this role (0-100)")
    required_skills: List[str] = Field(description="Skills required for this role")
    missing_skills: List[str] = Field(description="Skills the candidate needs to develop")
    next_steps: List[str] = Field(description="Recommended steps to qualify for this role")
    job_search_advice: str = Field(description="Specific advice for pursuing this role")

class EnhancedResumeAnalysis(BaseModel):
    key_skills: List[str] = Field(description="Top skills extracted from the resume")
    experience_summary: str = Field(description="Brief summary of professional experience")
    education_level: str = Field(description="Highest level of education")
    career_objectives: str = Field(description="Potential career objectives based on resume")
    recommended_jobs: List[JobRecommendation] = Field(description="List of recommended job titles with details")
    skill_gaps: Dict[str, List[str]] = Field(description="Skills to develop for different career paths")
    improvement_areas: List[str] = Field(description="General areas for professional development")
    experience_level: List[str] = Field(description="General areas for experience level")

class ResumeAnalyzerAgent:
    def __init__(self, llm: ChatGroq = None, api_key: str = None, temperature: float = 0.7):
        """
        Initialize Enhanced Resume Analyzer Agent
        
        Args:
            llm (ChatGroq, optional): Language model for analysis
            api_key (str, optional): Groq API key
            temperature (float, optional): Creativity/randomness of model responses
        """
        # Use provided LLM or create a new one
        if llm is None:
            # Validate API key
            if api_key is None:
                api_key = os.getenv('GROQ_API_KEY')
            
            if not api_key:
                raise ValueError("Groq API key must be provided either as an argument or via GROQ_API_KEY environment variable")
            
            # Default to Llama3-70b as it's typically the most capable Groq model
            self.llm = ChatGroq(
                temperature=temperature, 
                groq_api_key=api_key, 
                model_name="llama3-70b-8192"
            )
        else:
            self.llm = llm
        
        self.logger = logging.getLogger(__name__)
        
        # Load spaCy model for text processing
        try:
            self.nlp = spacy.load("en_core_web_sm")
        except OSError:
            self.logger.warning("spaCy model not found. Downloading...")
            spacy.cli.download("en_core_web_sm")
            self.nlp = spacy.load("en_core_web_sm")

    def _extract_text_from_pdf(self, pdf_path: str) -> str:
        """
        Extract text from PDF resume
        
        Args:
            pdf_path (str): Path to PDF resume
            
        Returns:
            str: Extracted text from PDF
        """
        try:
            with open(pdf_path, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                text = " ".join(page.extract_text() for page in reader.pages)
            return text
        except Exception as e:
            self.logger.error(f"Error extracting PDF text: {e}")
            raise

    def analyze_resume(self, resume_path: str) -> Dict[str, Any]:
        """
        Enhanced resume analysis with career recommendations aligned with template structure
        
        Args:
            resume_path (str): Path to resume PDF
                
        Returns:
            Dict with comprehensive career insights and recommendations
        """
        # Extract text from PDF
        resume_text = self._extract_text_from_pdf(resume_path)
        
        # Create output parser
        parser = PydanticOutputParser(pydantic_object=EnhancedResumeAnalysis)
        
        # Create detailed prompt template
        prompt = PromptTemplate(
            template="""
            Provide detailed career analysis for the following resume:
            {resume_text}
            
            Focus on:
            - Detailed skill assessment
            - Multiple career path recommendations
            - Specific job titles with match scores (as integers 0-100)
            - Required vs. missing skills
            - Concrete improvement steps
            - Job search strategies
            
            {format_instructions}
            """,
            input_variables=["resume_text"],
            partial_variables={"format_instructions": parser.get_format_instructions()}
        )
        
        # Generate chain
        chain = prompt | self.llm | parser
        
        try:
            # Analyze resume
            analysis = chain.invoke({"resume_text": resume_text})
            
            # Process with spaCy for additional insights
            doc = self.nlp(resume_text)
            
            # Extract relevant entities
            organizations = [ent.text for ent in doc.ents if ent.label_ == "ORG"]
            
            # Compile comprehensive insights matching template structure
            resume_insights = {
                "Career_Recommendations": [
                    {
                        "Job_Title": job.title,
                        "Match_Score": job.match_score,  # Integer 0-100
                        "Required_Skills": job.required_skills,
                        "Skills_to_Develop": job.missing_skills,
                        "Action_Plan": job.next_steps,
                        "Search_Tips": job.job_search_advice
                    }
                    for job in analysis.recommended_jobs
                ],
                "Current_Profile": {
                    "Key_Skills": analysis.key_skills,
                    "Experience_Summary": analysis.experience_summary,
                    "Education_Level": analysis.education_level,
                    "Organizations": list(set(organizations))
                },
                "Development_Areas": {
                    "Improvement_Areas": analysis.improvement_areas,
                    "Skill_Gaps": analysis.skill_gaps,
                    "Action_Items": [
                        step for job in analysis.recommended_jobs 
                        for step in job.next_steps
                    ]
                },
                "Career_Context": {
                    "Objectives": analysis.career_objectives,
                    "Industries": [job.industry for job in analysis.recommended_jobs if hasattr(job, 'industry')],
                    "Experience_Level": analysis.experience_level if hasattr(analysis, 'experience_level') else "Not specified"
                }
            }
            
            # Add template-specific metadata
            resume_insights["metadata"] = {
                "last_updated": datetime.now().isoformat(),
                "version": "2.0",
                "analysis_quality": "complete" if all(
                    len(resume_insights[key]) > 0 for key in ["Career_Recommendations", "Current_Profile", "Development_Areas"]
                ) else "partial"
            }
            
            return resume_insights
                
        except Exception as e:
            self.logger.error(f"Resume analysis error: {e}")
            return {
                "error": "Could not fully analyze resume",
                "details": str(e),
                "timestamp": datetime.now().isoformat()
            }


    def process(self, query: str, resume_path: str = None) -> Dict[str, Any]:
        """
        Process resume-related queries
        
        Args:
            query (str): User query
            resume_path (str, optional): Path to resume PDF
        
        Returns:
            Dict with processed query results
        """
        if resume_path:
            # If resume is provided, perform a comprehensive analysis
            return self.analyze_resume(resume_path)
        
        # Handle general resume-related queries without a specific resume
        response = self.llm.invoke(query)
        return {"response": response.content}
    
    
    def _create_career_prompt(self, resume_text: str) -> str:
        """
        Create a detailed prompt for career analysis
        
        Args:
            resume_text (str): Extracted resume text
            
        Returns:
            str: Formatted prompt
        """
        return f"""
        Analyze this resume in detail and provide comprehensive career insights:
        
        Resume Text:
        {resume_text}
        
        Please analyze for:
        1. Current skill set and expertise level
        2. Career trajectory and potential
        3. Industry-relevant job titles
        4. Required skills for recommended roles
        5. Specific steps for career advancement
        6. Job search strategies
        
        Focus on practical, actionable recommendations and realistic job matches.
        """

    

    def get_job_search_strategy(self, job_title: str, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate specific job search strategy for a recommended role
        
        Args:
            job_title (str): Target job title
            analysis (Dict[str, Any]): Previous analysis results
            
        Returns:
            Dict with detailed job search strategy
        """
        try:
            # Find matching job recommendation
            job_rec = next(
                (job for job in analysis["Career Recommendations"] 
                 if job["Job Title"].lower() == job_title.lower()),
                None
            )
            
            if job_rec:
                return {
                    "job_title": job_title,
                    "qualification_plan": {
                        "required_skills": job_rec["Required Skills"],
                        "skill_development": job_rec["Skills to Develop"],
                        "action_steps": job_rec["Action Plan"]
                    },
                    "search_strategy": {
                        "recommended_approach": job_rec["Job Search Tips"],
                        "target_companies": analysis["Career Context"]["Notable Organizations"],
                        "networking_suggestions": [
                            "Connect with professionals in target companies",
                            "Join relevant professional associations",
                            "Attend industry events and conferences",
                            "Engage in online communities"
                        ]
                    }
                }
            else:
                return {
                    "error": "Job title not found in recommendations",
                    "suggestion": "Please choose from the recommended job titles in the analysis"
                }
                
        except Exception as e:
            self.logger.error(f"Error generating job search strategy: {e}")
            return {
                "error": "Could not generate job search strategy",
                "details": str(e)
            }
        

   