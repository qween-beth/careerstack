import os
import logging
from typing import Dict, Any

from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field

class CoverLetterContent(BaseModel):
    opening_paragraph: str = Field(description="Engaging opening paragraph")
    skills_paragraph: str = Field(description="Paragraph highlighting relevant skills")
    motivation_paragraph: str = Field(description="Paragraph explaining motivation")
    closing_paragraph: str = Field(description="Strong closing paragraph")

class CoverLetterAgent:
    def __init__(self, llm: ChatOpenAI):
        """
        Initialize Cover Letter Generator Agent
        
        Args:
            llm (ChatOpenAI): Language model for generation
        """
        self.llm = llm
        self.logger = logging.getLogger(__name__)
    
    def process(self, query: str, resume_path: str = None) -> Dict[str, Any]:
        """
        Process a cover letter generation request
        
        Args:
            query (str): Job description or request details
            resume_path (str, optional): Path to resume PDF
        
        Returns:
            Dict containing the generated cover letter content
        """
        if not resume_path:
            return {
                "status": "error",
                "message": "Resume path is required for cover letter generation"
            }
            
        try:
            # Extract job description from query if needed
            job_description = query.strip()
            if not job_description:
                return {
                    "status": "error",
                    "message": "Job description is required for cover letter generation"
                }
                
            # Generate cover letter using existing method
            result = self.generate_cover_letter(job_description, resume_path)
            
            # Return in standardized format
            if result["status"] == "success":
                return {
                    "status": "success",
                    "content": result["content"],
                    "details": result["paragraphs"]
                }
            else:
                return result
                
        except Exception as e:
            self.logger.error(f"Error in cover letter processing: {e}")
            return {
                "status": "error",
                "message": f"Failed to generate cover letter: {str(e)}"
            }
    
    def _extract_resume_details(self, resume_path: str) -> Dict[str, str]:
        """
        Extract key details from resume
        
        Args:
            resume_path (str): Path to resume PDF
        
        Returns:
            Dict with resume key details
        """
        # This is a placeholder. In a real implementation, 
        # you'd use the ResumeAnalyzerAgent to extract details
        from .resume_analyzer import ResumeAnalyzerAgent
        
        analyzer = ResumeAnalyzerAgent(self.llm)
        resume_insights = analyzer.analyze_resume(resume_path)
        
        return {
            "skills": resume_insights.get("Key Skills", ""),
            "experience": resume_insights.get("Experience Summary", ""),
            "education": resume_insights.get("Education Level", "")
        }
    
    def generate_cover_letter(self, job_description: str, resume_path: str) -> Dict[str, Any]:
        """
        Generate a tailored cover letter
        
        Args:
            job_description (str): Job description to tailor cover letter
            resume_path (str): Path to resume PDF
        
        Returns:
            Dict with cover letter content and metadata
        """
        # Extract resume details
        resume_details = self._extract_resume_details(resume_path)
        
        # Create output parser
        parser = PydanticOutputParser(pydantic_object=CoverLetterContent)
        
        # Create comprehensive prompt
        prompt = PromptTemplate(
            template="""
            Generate a professional cover letter based on:
            
            Job Description:
            {job_description}
            
            Candidate Resume Details:
            Skills: {skills}
            Experience: {experience}
            Education: {education}
            
            Generate a cover letter with:
            1. A compelling opening paragraph
            2. A paragraph showcasing relevant skills
            3. A paragraph explaining motivation for the role
            4. A strong closing paragraph
            
            {format_instructions}
            """,
            input_variables=[
                "job_description", "skills", "experience", "education"
            ],
            partial_variables={
                "format_instructions": parser.get_format_instructions()
            }
        )
        
        # Generate chain
        chain = prompt | self.llm | parser
        
        try:
            # Generate cover letter
            cover_letter_content = chain.invoke({
                "job_description": job_description,
                "skills": resume_details["skills"],
                "experience": resume_details["experience"],
                "education": resume_details["education"]
            })
            
            # Combine paragraphs
            full_cover_letter = "\n\n".join([
                cover_letter_content.opening_paragraph,
                cover_letter_content.skills_paragraph,
                cover_letter_content.motivation_paragraph,
                cover_letter_content.closing_paragraph
            ])
            
            return {
                "status": "success",
                "content": full_cover_letter,
                "paragraphs": {
                    "opening": cover_letter_content.opening_paragraph,
                    "skills": cover_letter_content.skills_paragraph,
                    "motivation": cover_letter_content.motivation_paragraph,
                    "closing": cover_letter_content.closing_paragraph
                }
            }
        
        except Exception as e:
            self.logger.error(f"Cover letter generation error: {e}")
            return {
                "status": "error",
                "message": str(e)
            }