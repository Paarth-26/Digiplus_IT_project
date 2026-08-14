"""Environment loading.

Imported for its side effect by ``app.database`` and ``app.main`` before anything
reads ``os.getenv``. Keeping ``load_dotenv()`` here (rather than inline in main.py)
guarantees ordering: module-level ``os.getenv`` calls in other modules run at import
time, which is *before* any statement in main.py's body would execute.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"

# override=False: a real shell/CI environment variable wins over the .env file.
load_dotenv(dotenv_path=ENV_PATH, override=False)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")


def require_groq_api_key() -> str:
    """Fetch the Groq key or fail loudly. For use by the AI layer later."""
    key = os.getenv("GROQ_API_KEY")
    if not key:
        raise RuntimeError(f"GROQ_API_KEY is not set. Add it to {ENV_PATH} or the environment.")
    return key
