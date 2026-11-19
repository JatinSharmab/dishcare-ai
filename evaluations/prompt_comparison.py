import argparse
import asyncio
import json

from evaluations.runner import evaluate


async def compare(baseline, candidate, live=False, simulate=False, case_ids=None):
    before = await evaluate(baseline, live, case_ids=case_ids)
    after = await evaluate(candidate, live, degrade=simulate, case_ids=case_ids)
    deltas = {
        name: round(after["summary"][name]["score"] - metric["score"], 4)
        for name, metric in before["summary"].items()
    }
    return {"mode": after["mode"], "simulated_regression": simulate, "deltas": deltas,
            "baseline": before["summary"], "candidate": after["summary"]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("baseline", nargs="?", default="v1")
    parser.add_argument("candidate", nargs="?", default="v2")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--simulate-regression", action="store_true")
    parser.add_argument("--case", action="append")
    args = parser.parse_args()
    if args.live and args.simulate_regression:
        parser.error("A fixture regression is available only offline")
    result = asyncio.run(compare(args.baseline, args.candidate, args.live, args.simulate_regression, args.case))
    print(json.dumps(result, indent=2))
    raise SystemExit(int(any(delta < 0 for delta in result["deltas"].values())))
