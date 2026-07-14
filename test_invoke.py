import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langchain_groq import ChatGroq
from langchain_mistralai import ChatMistralAI
from langchain_cohere import ChatCohere
from langchain_cerebras import ChatCerebras

load_dotenv()

def test_model(name, model, test_message="Hello! Can you hear me? Respond with a short yes."):
    print(f"\n--- Testing {name} ---")
    try:
        response = model.invoke(test_message)
        print(f"✅ Success! Response: {response.content}")
    except Exception as e:
        print(f"❌ Failed: {e}")

def main():
    print("Testing LLM API Connections...\n")
    
    # 1. Test Gemini directly
    gemini_model = ChatGoogleGenerativeAI(model="gemini-2.5-flash")
    test_model("Google Gemini (Direct)", gemini_model)

    # 2. Test OpenAI directly
    openai_model = ChatOpenAI(model="gpt-4o-mini")
    test_model("OpenAI (Direct)", openai_model)

    # 3. Test Groq directly
    groq_model = ChatGroq(model="llama-3.1-8b-instant")
    test_model("Groq (Direct)", groq_model)

    # 4. Test OpenRouter (Nvidia Nemotron Free from your screenshot)
    openrouter_nvidia = ChatOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=os.getenv("OPENROUTER_API_KEY"),
        model="nvidia/nemotron-3-ultra-550b-a55b:free"
    )
    test_model("OpenRouter (Nvidia Nemotron Free)", openrouter_nvidia)

    # 5. Test OpenRouter (Tencent Hy3 Free from your screenshot)
    openrouter_tencent = ChatOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=os.getenv("OPENROUTER_API_KEY"),
        model="tencent/hy3:free"
    )
    test_model("OpenRouter (Tencent Hy3 Free)", openrouter_tencent)

    # 6. Test Mistral directly
    mistral_model = ChatMistralAI(model="mistral-large-latest")
    test_model("Mistral (Direct)", mistral_model)

    # 7. Test Cohere directly
    cohere_model = ChatCohere(model="command-r-plus-08-2024")
    test_model("Cohere (Direct)", cohere_model)

    # 8. Test Cerebras directly
    cerebras_model = ChatCerebras(model="gpt-oss-120b")
    test_model("Cerebras (Direct)", cerebras_model)


if __name__ == "__main__":
    main()
