import asyncio

from app.config import Settings
from app.llm.provider import LLMProvider
from app.prompts.loader import load_prompt
from app.schemas.conversation import IntentDecision


async def main():

    settings = Settings()
    llm = LLMProvider(settings)

    try:

        result = await llm.structured(
            load_prompt(
                settings.prompt_version,
                "supervisor",
            ),
            (
                "Maine recharge kar diya hai "
                "lekin channels nahi chal rahe."
            ),
            IntentDecision,
        )

        print(
            result.model_dump_json(indent=2)
        )

    finally:
        await llm.close()


if __name__ == "__main__":
    asyncio.run(main())