from statistics import mean


def record(case, result):
    expected = [case["intent"]] if case["intent"] else []
    by_tool = {item["tool"]: item for item in result.tool_results}
    want = case.get("proposal")
    actual = result.pending_confirmation
    tool_selection = set(by_tool) == set(case["tools"]) and (
        (actual or {}).get("tool") == (want or {}).get("tool")
    )
    tool_arguments = (actual or {}).get("arguments") == want["arguments"] if want else None
    facts = all(
        by_tool.get(tool, {}).get("ok")
        and all(by_tool[tool]["data"].get(key) == value for key, value in fields.items())
        for tool, fields in case["tools"].items()
    )
    source = case.get("source")
    retrieval = source in result.sources if source else None
    keywords = all(term.casefold() in result.answer.casefold() for term in case["answer_contains"])
    intent = result.intents == expected
    language = result.language == case["language"]
    return {
        "intent": intent,
        "language": language,
        "tool_selection": tool_selection,
        "tool_arguments": tool_arguments,
        "verified_facts": facts,
        "retrieval_hit": retrieval,
        "answer_keywords": keywords,
        "task_success": all(value is not False for value in (
            intent, language, tool_selection, tool_arguments, facts, retrieval, keywords,
        )),
    }


def summarize(rows):
    return {
        name: {"score": mean(values), "samples": len(values)}
        for name in rows[0]
        if (values := [row[name] for row in rows if row[name] is not None])
    }
