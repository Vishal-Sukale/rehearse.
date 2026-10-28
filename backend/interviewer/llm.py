import os

# Groq free tier, no credit card. Override with INTERVIEW_MODEL in .env
DEFAULT_MODEL = "groq:openai/gpt-oss-120b"


def get_llm(model: str | None = None):
    """Provider-agnostic chat model.

    Default is Groq (needs GROQ_API_KEY). To switch provider, change INTERVIEW_MODEL, e.g.
      "google_genai:gemini-2.5-flash"  (+ pip install langchain-google-genai, GOOGLE_API_KEY)
      "ollama:llama3.1"                (+ pip install langchain-ollama, no key)

    Optional speed-up for reasoning models such as gpt-oss: set REASONING_EFFORT=low in .env.
    """
    from langchain.chat_models import init_chat_model

    kwargs = {"temperature": 0.1}
    effort = os.getenv("REASONING_EFFORT")
    if effort:
        kwargs["reasoning_effort"] = effort
    return init_chat_model(model or os.getenv("INTERVIEW_MODEL", DEFAULT_MODEL), **kwargs)