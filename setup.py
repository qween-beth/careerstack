from setuptools import setup, find_packages

setup(
    name="job-search-assistant",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "flask",
        "flask-wtf",
        "python-dotenv",
        "langchain",
        "openai",
        "pypdf2",
        "spacy",
        "requests",
        "beautifulsoup4"
    ],
    extras_require={
        'dev': [
            'pytest',
            'flake8',
            'mypy'
        ]
    }
)