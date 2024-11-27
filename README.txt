# Job Search Assistant Multi-Agent Application

## Prerequisites
- Python 3.9+
- pip
- virtualenv (recommended)

## Setup Instructions

1. Clone the Repository
```bash
git clone https://your-repo-url/job-search-assistant.git
cd job-search-assistant
```

2. Create Virtual Environment
```bash
python -m venv venv
source venv/bin/activate  # On Windows use: venv\Scripts\activate
```

3. Install Dependencies
```bash
pip install -r requirements.txt
```

4. Download SpaCy Language Model
```bash
python -m spacy download en_core_web_sm
```

5. Create .env File
```bash
cp .env.template .env
```
Edit the .env file and add your OpenAI API key and other configurations

6. Run the Application
```bash
python run.py
```

## Additional Configuration Notes
- Ensure you have an OpenAI API key
- Some agents use placeholder API calls - you may need to replace with actual API integrations
- The web research and job search agents are conceptual and will require actual API integration

## Potential Improvements
- Implement proper error handling
- Add logging
- Integrate actual job search and web search APIs
- Enhance resume parsing