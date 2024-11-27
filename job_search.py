from langchain_openai import ChatOpenAI

# Initialize the analyzer
llm = ChatOpenAI(temperature=0.7)
analyzer = ResumeAnalyzerAgent(llm)

# Get comprehensive analysis
analysis = analyzer.analyze_resume("path_to_resume.pdf")

# Get specific job search strategy
strategy = analyzer.get_job_search_strategy("Software Engineer", analysis)