from functools import lru_cache
from pathlib import Path


PROMPT_ROOT = Path(__file__).resolve().parent


@lru_cache(maxsize=16)
def load_prompt(
    version: str,
    name: str,
) -> str:

    allowed_names = {
        "supervisor",
        "agent",
        "response",
    }

    if name not in allowed_names:
        raise ValueError("Unknown prompt name")

    if (
        not version.startswith("v")
        or not version[1:].isdigit()
    ):
        raise ValueError("Invalid prompt version")

    path = PROMPT_ROOT / version / f"{name}.txt"

    return path.read_text(
        encoding="utf-8"
    )