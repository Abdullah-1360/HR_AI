import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langchain_groq import ChatGroq
from langchain_mistralai import ChatMistralAI
from langchain_cohere import ChatCohere
from langchain_cerebras import ChatCerebras
from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, START, END

# Load environment variables from .env file
load_dotenv()

# Define the State for our graph
class State(TypedDict):
    input_text: str
    response: str
    selected_model: str

def main():
    print("--- LangChain & LangGraph Project Setup ---")
    
    # 1. Verify Environment Variables
    gemini_key = os.getenv("GEMINI_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")
    groq_key = os.getenv("GROQ_API_KEY")
    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    mistral_key = os.getenv("MISTRAL_API_KEY")
    cohere_key = os.getenv("COHERE_API_KEY")
    cerebras_key = os.getenv("CEREBRAS_API_KEY")
    
    print(f"GEMINI_API_KEY configured: {'Yes' if gemini_key else 'No'}")
    print(f"OPENAI_API_KEY configured: {'Yes' if openai_key else 'No'}")
    print(f"GROQ_API_KEY configured: {'Yes' if groq_key else 'No'}")
    print(f"OPENROUTER_API_KEY configured: {'Yes' if openrouter_key else 'No'}")
    print(f"MISTRAL_API_KEY configured: {'Yes' if mistral_key else 'No'}")
    print(f"COHERE_API_KEY configured: {'Yes' if cohere_key else 'No'}")
    print(f"CEREBRAS_API_KEY configured: {'Yes' if cerebras_key else 'No'}")
    
    # 2. Model Initializations (using standard recommended models)
    print("\nInitializing models...")
    try:
        # Gemini model
        gemini_model = ChatGoogleGenerativeAI(model="gemini-2.5-flash")
        print("✓ ChatGoogleGenerativeAI (gemini-2.5-flash) initialized successfully.")
    except Exception as e:
        print(f"✗ Failed to initialize Gemini model: {e}")
        
    try:
        # OpenAI model
        openai_model = ChatOpenAI(model="gpt-4o-mini")
        print("✓ ChatOpenAI (gpt-4o-mini) initialized successfully.")
    except Exception as e:
        print(f"✗ Failed to initialize OpenAI model: {e}")

    try:
        # Groq model
        groq_model = ChatGroq(model="llama-3.1-8b-instant")
        print("✓ ChatGroq (llama-3.1-8b-instant) initialized successfully.")
    except Exception as e:
        print(f"✗ Failed to initialize Groq model: {e}")

    try:
        # OpenRouter model
        openrouter_model = ChatOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=openrouter_key,
            model="openrouter/auto"
        )
        print("✓ ChatOpenAI (OpenRouter) initialized successfully.")
    except Exception as e:
        print(f"✗ Failed to initialize OpenRouter model: {e}")

    try:
        # Mistral model
        mistral_model = ChatMistralAI(model="mistral-large-latest")
        print("✓ ChatMistralAI (mistral-large-latest) initialized successfully.")
    except Exception as e:
        print(f"✗ Failed to initialize Mistral model: {e}")

    try:
        # Cohere model
        cohere_model = ChatCohere(model="command-r-plus-08-2024")
        print("✓ ChatCohere (command-r-plus-08-2024) initialized successfully.")
    except Exception as e:
        print(f"✗ Failed to initialize Cohere model: {e}")

    try:
        # Cerebras model
        cerebras_model = ChatCerebras(model="gpt-oss-120b")
        print("✓ ChatCerebras (gpt-oss-120b) initialized successfully.")
    except Exception as e:
        print(f"✗ Failed to initialize Cerebras model: {e}")

    # 3. Simple LangGraph Definition
    print("\nSetting up a simple LangGraph workflow...")
    
    # Define a simple node
    def process_node(state: State) -> dict:
        print(f"[Node] Processing input with model: {state['selected_model']}")
        
        # Simple conditional check/response formatting
        input_val = state['input_text']
        model_name = state['selected_model']
        
        # Here we could invoke the model, e.g.:
        # model = gemini_model if "gemini" in model_name.lower() else openai_model
        # ai_msg = model.invoke(input_val)
        # response_text = ai_msg.content
        
        # For verification, we'll return a mock response that demonstrates flow works:
        response_text = f"Processed '{input_val}' using {model_name} (mocked API call)"
        
        return {"response": response_text}

    # Build the graph
    workflow = StateGraph(State)
    workflow.add_node("process", process_node)
    workflow.add_edge(START, "process")
    workflow.add_edge("process", END)
    
    # Compile the graph
    app = workflow.compile()
    
    # Run the graph
    print("Running workflow test...")
    initial_state = {
        "input_text": "Hello LangGraph!",
        "selected_model": "Gemini 2.5 Flash"
    }
    result = app.invoke(initial_state)
    print(f"Result response: {result['response']}")
    print("\nSetup complete! You can modify main.py to customize your agent workflow.")

if __name__ == "__main__":
    main()
