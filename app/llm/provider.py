import asyncio
import json
import logging

from google import genai
from google.genai import errors, types
from groq import AsyncGroq

from app.config import Settings
from app.core.exceptions import BusinessError

logger = logging.getLogger(__name__)


class LLMProvider:

    def __init__(self, settings: Settings):

        self.settings = settings

        self.gemini = None
        self.groq = None

        gemini_key = (
            settings.gemini_api_key.get_secret_value()
        )

        groq_key = (
            settings.groq_api_key.get_secret_value()
        )

        if gemini_key:
            self.gemini = genai.Client(
                api_key=gemini_key
            ).aio

        if groq_key:
            self.groq = AsyncGroq(
                api_key=groq_key,
                timeout=settings.llm_timeout_seconds,
                max_retries=0,
            )

        if not self.gemini and not self.groq:
            raise ValueError(
                "Configure GEMINI_API_KEY or GROQ_API_KEY"
            )

    async def close(self):

        if self.gemini:
            await self.gemini.aclose()

        if self.groq:
            await self.groq.close()

    async def _fallback(
        self,
        gemini_operation,
        groq_operation,
    ):

        operations = [
            ("gemini", self.gemini, gemini_operation),
            ("groq", self.groq, groq_operation),
        ]

        for name, client, operation in operations:

            if client is None:
                continue

            try:
                result = await asyncio.wait_for(
                    operation(),
                    timeout=self.settings.llm_timeout_seconds,
                )

                logger.info(
                    "LLM operation successful: %s",
                    name,
                )

                return result

            except Exception as exc:  # noqa: BLE001 - isolate provider failures

                logger.warning(
                    "LLM provider failed: %s, type=%s, http_status=%s",
                    name,
                    type(exc).__name__,
                    exc.code if isinstance(exc, errors.APIError) else None,
                )

        raise BusinessError(
            503,
            "LLM_UNAVAILABLE",
            "AI service temporarily unavailable",
        )

    async def structured(
        self,
        system_prompt,
        user_prompt,
        schema,
    ):

        async def gemini_call():

            response = (
                await self.gemini.models.generate_content(
                    model=self.settings.gemini_model,
                    contents=user_prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=system_prompt,
                        response_mime_type="application/json",
                        response_json_schema=schema.model_json_schema(),
                    ),
                )
            )

            return schema.model_validate_json(
                response.text or ""
            )

        async def groq_call():

            schema_text = json.dumps(
                schema.model_json_schema(),
                ensure_ascii=False,
            )

            response = (
                await self.groq.chat.completions.create(
                    model=self.settings.groq_model,
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                system_prompt
                                + "\nReturn JSON matching: "
                                + schema_text
                            ),
                        },
                        {
                            "role": "user",
                            "content": user_prompt,
                        },
                    ],
                    response_format={
                        "type": "json_object"
                    },
                )
            )

            content = (
                response.choices[0].message.content
            )

            return schema.model_validate_json(
                content or ""
            )

        return await self._fallback(
            gemini_call,
            groq_call,
        )

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> str:

        async def gemini_call():

            response = (
                await self.gemini.models.generate_content(
                    model=self.settings.gemini_model,
                    contents=user_prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=system_prompt,
                        max_output_tokens=1500,
                    ),
                )
            )

            if not response.text:
                raise ValueError("Empty Gemini response")

            return response.text

        async def groq_call():

            response = (
                await self.groq.chat.completions.create(
                    model=self.settings.groq_model,
                    messages=[
                        {
                            "role": "system",
                            "content": system_prompt,
                        },
                        {
                            "role": "user",
                            "content": user_prompt,
                        },
                    ],
                    max_completion_tokens=1500,
                )
            )

            content = (
                response.choices[0].message.content
            )

            if not content:
                raise ValueError("Empty Groq response")

            return content

        return await self._fallback(
            gemini_call,
            groq_call,
        )

    async def choose_tool(
        self,
        system_prompt: str,
        user_prompt: str,
        tools: list[dict],
    ) -> dict | None:

        async def gemini_call():

            declarations = [
                types.FunctionDeclaration(
                    name=tool["name"],
                    description=tool["description"],
                    parameters_json_schema=tool["parameters"],
                )
                for tool in tools
            ]

            response = (
                await self.gemini.models.generate_content(
                    model=self.settings.gemini_model,
                    contents=user_prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=system_prompt,
                        tools=[
                            types.Tool(
                                function_declarations=declarations
                            )
                        ],
                        automatic_function_calling=(
                            types.AutomaticFunctionCallingConfig(
                                disable=True
                            )
                        ),
                    ),
                )
            )

            calls = response.function_calls or []

            if not calls:
                return None

            if len(calls) != 1:
                raise ValueError(
                    "Only one tool call is permitted"
                )

            call = calls[0]

            return {
                "name": call.name,
                "arguments": dict(call.args or {}),
            }

        async def groq_call():

            groq_tools = [
                {
                    "type": "function",
                    "function": tool,
                }
                for tool in tools
            ]

            response = (
                await self.groq.chat.completions.create(
                    model=self.settings.groq_model,
                    messages=[
                        {
                            "role": "system",
                            "content": system_prompt,
                        },
                        {
                            "role": "user",
                            "content": user_prompt,
                        },
                    ],
                    tools=groq_tools,
                    tool_choice="auto",
                    parallel_tool_calls=False,
                )
            )

            calls = (
                response.choices[0].message.tool_calls
                or []
            )

            if not calls:
                return None

            if len(calls) != 1:
                raise ValueError(
                    "Only one tool call is permitted"
                )

            call = calls[0].function

            return {
                "name": call.name,
                "arguments": json.loads(
                    call.arguments
                ),
            }

        return await self._fallback(
            gemini_call,
            groq_call,
        )
