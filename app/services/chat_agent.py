from langchain_groq import ChatGroq
from langchain.chains import ConversationChain
from langchain.memory import ConversationBufferMemory

class ChatAgent:
    def __init__(self, temperature: float = 0.7, api_key: str = None):
        """
        Initialize the ChatAgent with Groq LLM integration.

        Args:
            temperature (float): Controls randomness in language model responses.
            api_key (str, optional): Groq API key. Defaults to the GROQ_API_KEY environment variable.
        """
        if api_key is None:
            api_key = os.getenv('GROQ_API_KEY')
            if not api_key:
                raise ValueError("Groq API key must be provided either as an argument or via the GROQ_API_KEY environment variable.")
        
        # Initialize the Groq LLM
        self.llm = ChatGroq(
            temperature=temperature,
            groq_api_key=api_key,
            model_name="llama3-70b-8192"  # Replace with the appropriate model as needed
        )

        # Set up conversation memory and chain
        self.memory = ConversationBufferMemory()
        self.chain = ConversationChain(llm=self.llm, memory=self.memory)

    def process(self, query: str):
        """
        Process a user's query using Groq LLM.

        Args:
            query (str): The user's input query.

        Returns:
            dict: Response data containing the LLM's output and metadata.
        """
        try:
            # Generate a response using Groq LLM
            response = self.chain.run(query)
            return {
                "response": response,
                "intent": "general",  # Update this if you have intent detection
                "agent": "ChatAgent",
                "error": None
            }
        except Exception as e:
            return {
                "response": None,
                "intent": "error",
                "agent": "ChatAgent",
                "error": str(e)
            }
