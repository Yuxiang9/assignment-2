"""Deterministic literal-array check (candidate component).

When a task embeds its data as literal number series and the agent's final
plotting code also contains literal number series, the two can be compared
without a model: the same multiset in a different order is a wrong-order
defect, and a near-identical series with a few changed values is a
wrong-values defect. Everything else is left to the judge.

Conservative rules:
* only the LAST successful figure-writing command's code is read -- a
  failed or superseded attempt proves nothing about the saved figure;
* instruction series shorter than 4 numbers are ignored;
* order is only checked when the instruction does not ask for re-ordering
  (sorted/descending/ascending/alphabetical);
* a value mismatch is only reported when the series lengths match and at
  most a third of the positions differ (a wholesale different series means
  the agent computed something, which is the judge's territory);
* any code series that matches exactly clears that instruction series.
"""

from __future__ import annotations

import json
import re

_NUMBER = r"-?\d+(?:\.\d+)?"
#: Instruction series: 4+ numbers separated by commas (optional spaces).
_INSTRUCTION_SERIES = re.compile(rf"{_NUMBER}(?:\s*,\s*{_NUMBER}){{3,}}")
#: Code series: bracketed literal lists/tuples with 4+ numbers.
_CODE_SERIES = re.compile(rf"[\[(]\s*({_NUMBER}(?:\s*,\s*{_NUMBER}){{3,}})\s*[\])]")
_REORDER_WORDS = re.compile(
    r"\bsort(?:ed|ing)?\b|\bdescending\b|\bascending\b|\balphabetical",
    re.IGNORECASE)


def _numbers(text: str) -> tuple[float, ...]:
    return tuple(float(n) for n in re.findall(_NUMBER, text))


def final_plot_code(messages: list[dict]) -> str | None:
    """The last bash command that draws/saves a figure and exited 0."""
    last = None
    pending = None  # (code, call_id) awaiting its tool result
    call_results: dict[str, int] = {}
    for message in messages:
        if message.get("role") == "tool":
            try:
                payload = json.loads(str(message.get("content")))
                call_results[message.get("tool_call_id")] = payload.get("returncode")
            except (TypeError, ValueError):
                continue
    for message in messages:
        for call in (message.get("tool_calls") or []):
            try:
                command = json.loads(call["function"]["arguments"]).get("command", "")
            except (KeyError, TypeError, ValueError):
                continue
            if "savefig" not in command and "figure.png" not in command:
                continue
            if call_results.get(call.get("id")) == 0:
                last = command
    return last


def literal_array_violation(instructions: str, messages: list[dict]) -> str | None:
    """Evidence text for a literal-series mismatch, or None."""
    series = [
        _numbers(match.group(0))
        for match in _INSTRUCTION_SERIES.finditer(instructions)
    ]
    series = [s for s in series if len(s) >= 4]
    if not series:
        return None
    code = final_plot_code(messages)
    if code is None:
        return None
    code_series = [_numbers(m.group(1)) for m in _CODE_SERIES.finditer(code)]
    if not code_series:
        return None
    reordering_requested = bool(_REORDER_WORDS.search(instructions))

    for wanted in series:
        if any(found == wanted for found in code_series):
            continue                     # exact match somewhere: satisfied
        # same multiset, different order
        permuted = [found for found in code_series
                    if len(found) == len(wanted)
                    and sorted(found) == sorted(wanted)]
        if permuted and not reordering_requested:
            return ("the instructions give the series "
                    f"{list(wanted)} in a fixed order, but the plotting code "
                    f"uses the same numbers re-ordered as {list(permuted[0])}")
        # same length, a few changed values (a permutation is not a value
        # change: it was handled -- or deliberately allowed -- above)
        for found in code_series:
            if len(found) != len(wanted) or sorted(found) == sorted(wanted):
                continue
            diffs = [i for i, (a, b) in enumerate(zip(wanted, found)) if a != b]
            if 0 < len(diffs) <= max(1, len(wanted) // 3):
                positions = ", ".join(str(i + 1) for i in diffs)
                return ("the plotting code alters the series "
                        f"{list(wanted)} from the instructions at "
                        f"position(s) {positions}: it uses {list(found)}")
    return None


if __name__ == "__main__":
    # unit cases
    msgs = lambda cmd: [  # noqa: E731
        {"role": "assistant", "tool_calls": [{"id": "c1", "function": {
            "name": "bash", "arguments": json.dumps({"command": cmd})}}]},
        {"role": "tool", "tool_call_id": "c1",
         "content": json.dumps({"returncode": 0, "output": ""})},
    ]
    instr = "Plot the values 3, 1, 4, 1, 5, 9 in the given order."
    ok = "import matplotlib.pyplot as plt\nplt.plot([3, 1, 4, 1, 5, 9])\nplt.savefig('figure.png')"
    swapped = ok.replace("[3, 1, 4, 1, 5, 9]", "[3, 4, 1, 1, 5, 9]")
    altered = ok.replace("[3, 1, 4, 1, 5, 9]", "[3, 1, 4, 1, 5, 8]")
    assert literal_array_violation(instr, msgs(ok)) is None
    assert "re-ordered" in literal_array_violation(instr, msgs(swapped))
    assert "alters the series" in literal_array_violation(instr, msgs(altered))
    # reordering requested -> permutation is fine
    sorted_instr = "Plot the values 3, 1, 4, 1, 5, 9 sorted in descending order."
    assert literal_array_violation(sorted_instr, msgs(swapped)) is None
    # failed command proves nothing
    failed = msgs(swapped)
    failed[1]["content"] = json.dumps({"returncode": 1, "output": "boom"})
    assert literal_array_violation(instr, failed) is None
    # superseded: last successful command wins
    both = msgs(swapped) + msgs(ok)
    assert literal_array_violation(instr, both) is None
    # wholesale different series (agent computed something): stay silent
    computed = ok.replace("[3, 1, 4, 1, 5, 9]", "[10, 20, 30, 40, 50, 60]")
    assert literal_array_violation(instr, msgs(computed)) is None
    print("all data_check unit cases pass")
