import argparse
import asyncio
import json
import tempfile
from pathlib import Path
from time import perf_counter

from langgraph.checkpoint.memory import InMemorySaver

from app.agents.graph import build_graph
from app.agents.memory import ChatEngine
from app.config import Settings
from app.core.exceptions import BusinessError
from app.db.database import Database
from app.db.seed import seed_database
from app.llm.provider import LLMProvider
from app.schemas.conversation import IntentDecision
from app.services.business import BusinessService
from app.tools.executor import ToolExecutor
from evaluations.llm_judge import judge
from evaluations.metrics import record, summarize

ROOT = Path(__file__).resolve().parents[1]


class FixtureModel:
    """Replay deterministic model decisions to exercise the offline orchestration."""

    def __init__(self, case, degrade=False):
        self.case = case
        self.degrade = degrade

    async def structured(self, system_prompt, user_prompt, schema):
        intent = "general" if self.degrade and self.case["id"] == "balance-hi" else self.case["intent"]
        return IntentDecision(intents=[intent], language=self.case["language"])

    async def choose_tool(self, system_prompt, user_prompt, tools):
        proposal = self.case.get("proposal")
        if proposal is None:
            return None
        return {"name": proposal["tool"], "arguments": proposal["arguments"]}

    async def generate(self, system_prompt, user_prompt):
        return self.case["response"]


class FixtureRetrieval:
    """Replay a known document for offline graph tests."""

    def __init__(self, filename):
        self.documents = []
        if filename:
            path = ROOT / "knowledge_base" / filename
            self.documents.append({"source": filename, "text": path.read_text(encoding="utf-8"), "score": 1.0})

    async def retrieve(self, query):
        return self.documents


async def evaluate(version="v1", live=False, use_judge=False, degrade=False, case_ids=None):
    cases = json.loads((ROOT / "evaluations/golden_dataset.json").read_text(encoding="utf-8"))
    if case_ids:
        cases = [case for case in cases if case["id"] in case_ids]
    if not cases:
        raise ValueError("No selected evaluation cases")
    with tempfile.TemporaryDirectory() as directory:
        overrides = {} if live else {"jwt_secret": "offline-evaluation-signing-secret-only"}
        settings = Settings(prompt_version=version, database_path=Path(directory) / "eval.db", **overrides)
        db = Database(settings.database_path)
        await db.initialize()
        await seed_database(db)
        executor = ToolExecutor(BusinessService(db))
        provider = LLMProvider(settings) if live else None
        rows = []
        try:
            for case in cases:
                llm = provider or FixtureModel(case, degrade)
                knowledge = FixtureRetrieval(case.get("source"))
                graph = build_graph(settings, llm, executor, knowledge, InMemorySaver())
                started = perf_counter()
                try:
                    result = await ChatEngine(graph).chat(case.get("customer", "CUST001"), case["message"])
                    scores = record(case, result)
                    elapsed = round((perf_counter() - started) * 1000, 3)
                    entry = {"id": case["id"], "latency_ms": elapsed, "scores": scores}
                    if use_judge:
                        try:
                            entry["judge"] = (await judge(
                                llm, case["message"], result.answer,
                                {"tools": result.tool_results, "documents": knowledge.documents,
                                 "pending_confirmation": bool(result.pending_confirmation)},
                            )).model_dump()
                        except BusinessError as exc:
                            entry["judge_error"] = exc.code
                except BusinessError as exc:
                    entry = {
                        "id": case["id"], "error": exc.code,
                        "latency_ms": round((perf_counter() - started) * 1000, 3),
                        "scores": dict.fromkeys(
                            ("intent", "language", "tool_selection", "verified_facts",
                             "answer_keywords", "task_success"), False,
                        ) | {"tool_arguments": False if case.get("proposal") else None,
                             "retrieval_hit": False if case.get("source") else None},
                    }
                rows.append(entry)
        finally:
            if provider is not None:
                await provider.close()
    return {
        "mode": "live-model-with-fixture-retrieval" if live else "offline-fixture-replay",
        "prompt_version": version, "summary": summarize([row["scores"] for row in rows]), "cases": rows,
    }


def main():
    parser = argparse.ArgumentParser(description="Run the DishCare golden evaluation")
    parser.add_argument("--prompt-version", default="v1")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--judge", action="store_true")
    parser.add_argument("--simulate-regression", action="store_true")
    parser.add_argument("--case", action="append")
    parser.add_argument("--require-pass", action="store_true")
    args = parser.parse_args()
    if args.judge and not args.live:
        parser.error("--judge requires --live")
    result = asyncio.run(evaluate(
        args.prompt_version, args.live, args.judge, args.simulate_regression, args.case,
    ))
    print(json.dumps(result, indent=2, ensure_ascii=True))
    if args.require_pass and result["summary"]["task_success"]["score"] < 1:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
