"""Local regression tests for filtering and arbitration handling.

    uv run python experiments/regression_tests.py <module>

Checks, against the named solution module (default validator.solution):

1. The five improvement-plan findings that filtering must preserve.
2. Arbitration partial replies: missing families must keep their original
   findings, for both "stop" and "length" finish reasons; a truncated reply
   triggers one bounded repair request; a malformed reply preserves
   everything; an arbiter YES for a family nobody proposed must not invent
   an error with fabricated evidence.

All model calls are mocked; nothing here touches the endpoint or labels.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from validator.prediction import Error, ErrorFamily  # noqa: E402
from validator.runner import runs  # noqa: E402

WD, WC, HR = (ErrorFamily.WRONG_DATA, ErrorFamily.WRONG_CHART,
              ErrorFamily.HARD_TO_READ)
E = lambda f, ev: Error(family=f, evidence=ev)  # noqa: E731

PRESERVE = [
    E(WC, "The required tab:blue series is red and the required tab:red series is blue."),
    E(WC, "The title is missing and the line color is incorrect."),
    E(WC, "The line uses color steelblue instead of royalblue."),
    E(WC, "The code uses color='blue' instead of the required color='tab:blue'."),
    E(HR, "The tab:blue series overlaps its label and both blue elements blur together."),
]


def main() -> None:
    module_name = sys.argv[1] if len(sys.argv) > 1 else "validator.solution"
    solution = importlib.import_module(module_name)
    failures: list[str] = []

    # ---- 1. filtering preserves the plan's findings -------------------
    filter_fn = getattr(solution, "_drop_tab_alias_claims", None)
    filter_active = filter_fn is not None and "_drop_tab_alias_claims(raw" in \
        Path(solution.__file__).read_text()
    for case in PRESERVE:
        if filter_active:
            out = filter_fn([case])
            ok = len(out) == 1 and out[0].evidence == case.evidence
        else:
            ok = True  # no active filter: trivially preserved
        if not ok:
            failures.append(f"filter destroyed: {case.evidence[:60]}")

    # ---- 2. arbitration handling --------------------------------------
    run = next(r for r in runs(Path(__file__).resolve().parents[1] / "runs")
               if r.figure is not None)
    findings = [E(WD, "values differ from the request"),
                E(WC, "the requested log scale is missing"),
                E(HR, "tick labels overlap")]
    real_complete = solution.complete

    def check(name, replies, expect_families, expect_calls=None):
        calls = []

        def fake(messages, **kw):
            calls.append(1)
            reply = replies[min(len(calls), len(replies)) - 1]
            return {"choices": [{"message": {"content": reply[0]},
                                 "finish_reason": reply[1]}]}
        solution.complete = fake
        try:
            out = solution._arbitrate(run, findings)
        finally:
            solution.complete = real_complete
        got = sorted(e.family.value for e in out)
        if got != sorted(expect_families):
            failures.append(f"{name}: families {got}, expected {expect_families}")
        if expect_calls is not None and len(calls) != expect_calls:
            failures.append(f"{name}: {len(calls)} calls, expected {expect_calls}")
        return out

    # partial reply, finish=stop: unanswered families preserved
    check("partial-stop", [("WRONG_DATA: NO", "stop")],
          ["wrong_chart", "hard_to_read"], expect_calls=1)
    # partial reply, finish=length: one repair request, then full parse
    check("partial-length-repaired",
          [("WRONG_DATA: NO", "length"),
           ("WRONG_DATA: NO\nWRONG_DATA_EVIDENCE: none\n"
            "WRONG_CHART: YES\nWRONG_CHART_EVIDENCE: log scale missing.\n"
            "HARD_TO_READ: NO\nHARD_TO_READ_EVIDENCE: none", "stop")],
          ["wrong_chart"], expect_calls=2)
    # repair also truncated: answered family honoured, others preserved
    check("partial-length-unrepaired",
          [("WRONG_DATA: NO", "length"), ("WRONG_DATA: NO", "length")],
          ["wrong_chart", "hard_to_read"], expect_calls=2)
    # malformed reply: everything preserved
    check("malformed", [("no verdict lines here", "stop")],
          ["wrong_data", "wrong_chart", "hard_to_read"])
    # arbiter must not invent: YES with no evidence for a family nobody
    # proposed (proposed findings here are wd/wc/hr; simulate an unproposed
    # family by sending only wd findings and a YES elsewhere).
    solo = [E(WD, "values differ from the request")]

    def fake_invent(messages, **kw):
        return {"choices": [{"message": {"content":
            "WRONG_DATA: NO\nWRONG_DATA_EVIDENCE: none\n"
            "WRONG_CHART: YES\nWRONG_CHART_EVIDENCE: none\n"
            "HARD_TO_READ: NO\nHARD_TO_READ_EVIDENCE: none"},
            "finish_reason": "stop"}]}
    solution.complete = fake_invent
    try:
        out = solution._arbitrate(run, solo)
    finally:
        solution.complete = real_complete
    invented = [e for e in out if e.family is WC]
    generic = [e for e in out if "confirmed by arbitration" in e.evidence]
    if invented or generic:
        failures.append(
            "arbiter invented a finding for an unproposed family "
            f"(invented={len(invented)}, generic={len(generic)})")

    # ---- 3. end-to-end validate() smoke with a mocked judge ------------
    # Catches wiring errors (undefined names, broken diag hooks) that
    # per-function tests miss.
    solution.complete = lambda *a, **k: {"choices": [{"message": {
        "content": "VERDICT: NO\nEVIDENCE: none"}, "finish_reason": "stop"}]}
    try:
        out = solution.validate(run)
        if out != []:
            failures.append(f"mocked validate() returned {out}")
        nofig = next(r for r in runs(Path(__file__).resolve().parents[1] / "runs")
                     if r.figure is None)
        out = solution.validate(nofig)
        if [e.family.value for e in out] != ["execution_failure"]:
            failures.append(f"mocked validate() on no-figure run: {out}")
    except Exception as error:  # noqa: BLE001
        failures.append(f"mocked validate() raised {type(error).__name__}: {error}")
    finally:
        solution.complete = real_complete

    if failures:
        print(f"FAIL ({module_name}):")
        for f in failures:
            print("  -", f)
        raise SystemExit(1)
    print(f"all regression tests pass ({module_name})")


if __name__ == "__main__":
    main()
