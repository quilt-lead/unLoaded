"""Verify calcgraph.ai end to end with the replay provider. No network, no spend.

Synthetic inputs only (no drawing-set content). Each check prints PASS/FAIL; exit 1 on
any failure.  uv run python scripts/check_ai_step.py
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

for k in ("CALCGRAPH_AI_ENABLE_REAL", "CALCGRAPH_AI_PROVIDER", "CALCGRAPH_AI_MAX_RUN_USD"):
    os.environ.pop(k, None)

from calcgraph import ai  # noqa: E402
from calcgraph.ai.providers.base import Provider  # noqa: E402

FAILS: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    print(f"{'PASS' if cond else 'FAIL'}  {name}{('  - ' + detail) if detail else ''}")
    if not cond:
        FAILS.append(name)


def raises(name: str, exc: type[BaseException], fn, *, contains: str = "") -> BaseException | None:
    try:
        fn()
    except exc as e:
        check(name, contains in str(e), f"{type(e).__name__}: {str(e)[:140]}")
        return e
    except Exception as e:  # wrong exception type
        check(name, False, f"expected {exc.__name__}, got {type(e).__name__}: {e}")
        return e
    check(name, False, f"expected {exc.__name__}, nothing raised")
    return None


SHA = hashlib.sha256(b"synthetic-doc").hexdigest()
IMG = hashlib.sha256(b"synthetic-page-image").hexdigest()

page_inputs = ai.AIInputs(
    evidence=[ai.Evidence(id="p7", doc_sha256=SHA, page=7, frame="sheet_pt", bbox=(0, 0, 612, 792))],
    images=[ai.ImageInput(evidence_id="p7", sha256=IMG)],
    payload={"calc_package": "synthetic v1", "page": 7},
)
good_page = {"confidence": 0.8, "evidence_refs": ["p7"], "calc_sheet_id": "H1",
             "title": "Hand check - beam B3", "values": [
                 {"label": "Mu", "text": "42.1 k-ft", "value": 42.1, "unit": "k-ft", "member_mark": "B3",
                  "evidence_ref": "p7", "bbox": [100, 200, 180, 214], "confidence": 0.7}]}

match_inputs = ai.AIInputs(
    evidence=[
        ai.Evidence(id="el", doc_sha256=SHA, page=2, frame="sheet_pt", bbox=(10, 10, 60, 20), text="W16X26"),
        ai.Evidence(id="c1", doc_sha256=SHA, page=30, frame="sheet_pt", text="W16X26 Level 2", char_span=(0, 14)),
        ai.Evidence(id="c2", doc_sha256=SHA, page=31, frame="sheet_pt", text="W16X26 Roof", char_span=(0, 11)),
    ],
    payload={"element_id": "E-12", "candidates": [
        {"candidate_id": "c1", "calc_key": "b10", "evidence_ref": "c1", "deterministic_tier": "size_type", "deterministic_score": 0.62},
        {"candidate_id": "c2", "calc_key": "b11", "evidence_ref": "c2", "deterministic_tier": "size_type", "deterministic_score": 0.62},
    ]},
)


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="ai-step-check-"))
    cache = ai.ResultCache(tmp / "cache")
    replay = ai.ReplayProvider(root=tmp / "fixtures")
    run = ai.Run()

    def X(task, inputs, **kw):
        return ai.extract(task, inputs, provider=kw.pop("provider", replay), run=kw.pop("run", run),
                          cache=kw.pop("cache", cache), **kw)

    check("default provider is replay", ai.get_provider().name == "replay")
    check("both tasks registered", [t.name for t in ai.list_tasks()] == ["fuzzy_element_calc_match", "scanned_calc_page"])

    # 1. missing fixture fails loudly and names the file to write
    e = raises("replay miss is loud", ai.ReplayMiss, lambda: X("scanned_calc_page", page_inputs), contains="write ")
    fixture_path = Path(str(e).split("write ")[-1])
    inputs_key = fixture_path.stem

    # 2. fixture -> structured result marked method=ai
    fixture_path.parent.mkdir(parents=True, exist_ok=True)
    fixture_path.write_text(json.dumps({"output": good_page, "model_id": "hand-authored"}))
    calls0 = replay.calls
    r = X("scanned_calc_page", page_inputs)
    p = r.provenance
    check("result validated into the task schema", isinstance(r.output, ai.ScannedCalcPageReading) and r.output.values[0].unit == "k-ft")
    check("provenance method is 'ai'", p.method == "ai" and p.rule_id == "ai:scanned_calc_page" and p.rule_version == "1")
    check("provenance carries model id + confidence", p.model_id == "replay:hand-authored" and p.confidence == 0.8 and p.provider == "replay")
    check("provenance evidence resolved from inputs", [ev.id for ev in p.evidence] == ["p7"] and p.evidence[0].doc_sha256 == SHA)
    check("inputs_key matches the fixture key", p.inputs_key == inputs_key)
    check("first call not cached, provider called once", not r.cached and replay.calls == calls0 + 1)
    try:
        ai.AIProvenance(**{**p.model_dump(), "method": "deterministic"})
        check("provenance cannot be built with method != 'ai'", False)
    except Exception:
        check("provenance cannot be built with method != 'ai'", True)

    # 3. cache hit: no provider call
    r2 = X("scanned_calc_page", page_inputs)
    check("second identical call is a cache hit with no provider call",
          r2.cached and replay.calls == calls0 + 1 and r2.output == r.output and r2.provenance == r.provenance)
    check("image path is not part of the key",
          X("scanned_calc_page", page_inputs.model_copy(update={"images": [ai.ImageInput(evidence_id="p7", sha256=IMG, path="/elsewhere.png")]})).cached)

    # 4. changed content -> new key -> miss
    changed = page_inputs.model_copy(update={"payload": {"calc_package": "synthetic v1", "page": 8}})
    raises("changed input is a different key (miss)", ai.ReplayMiss, lambda: X("scanned_calc_page", changed))

    # 5. evidence and schema enforcement (fresh cache so the fixture is re-read)
    def with_output(out, inputs=page_inputs, task="scanned_calc_page"):
        rp = ai.ReplayProvider(root=tmp / "none", fixtures={})
        key = ai.step._keys(ai.get_task(task), ai.get_task(task).output_schema, inputs, rp)[0]
        rp.fixtures[key] = {"output": out}
        return lambda: ai.extract(task, inputs, provider=rp, run=ai.Run(), cache=ai.ResultCache(tmp / "c2"), use_cache=False)

    raises("citing evidence not in the inputs fails", ai.AIEvidenceError,
           with_output({**good_page, "evidence_refs": ["p99"]}), contains="p99")
    bad_box = json.loads(json.dumps(good_page)); bad_box["values"][0]["bbox"] = [600, 780, 700, 900]
    raises("a bbox outside its evidence fails", ai.AIEvidenceError, with_output(bad_box), contains="outside")
    raises("confidence > 1 fails the schema", ai.AIOutputInvalid, with_output({**good_page, "confidence": 1.5}))
    raises("extra fields fail the schema", ai.AIOutputInvalid, with_output({**good_page, "notes": "x"}))
    no_unit = json.loads(json.dumps(good_page)); no_unit["values"][0]["unit"] = None
    raises("a number without a unit fails the task validator", ai.AIOutputInvalid, with_output(no_unit), contains="no unit")

    # 6. fuzzy match: may only pick an offered candidate, or decline
    ok_choice = {"confidence": 0.66, "evidence_refs": ["el", "c1"], "element_id": "E-12",
                 "chosen_candidate_id": "c1", "reason": "same size, Level 2 on both"}
    m = with_output(ok_choice, match_inputs, "fuzzy_element_calc_match")()
    check("fuzzy match picks an offered candidate", m.output.chosen_candidate_id == "c1" and [e.id for e in m.provenance.evidence] == ["el", "c1"])
    decline = {**ok_choice, "chosen_candidate_id": None, "evidence_refs": ["el"], "reason": "level not stated"}
    check("fuzzy match may decline", with_output(decline, match_inputs, "fuzzy_element_calc_match")().output.chosen_candidate_id is None)
    raises("fuzzy match cannot invent a candidate", ai.AIOutputInvalid,
           with_output({**ok_choice, "chosen_candidate_id": "c9"}, match_inputs, "fuzzy_element_calc_match"), contains="not offered")
    raises("fuzzy match must cite the chosen candidate", ai.AIOutputInvalid,
           with_output({**ok_choice, "evidence_refs": ["el"]}, match_inputs, "fuzzy_element_calc_match"), contains="cited")
    rec = m.to_record()
    check("to_record carries value + provenance(method=ai)", rec["provenance"]["method"] == "ai" and rec["value"]["chosen_candidate_id"] == "c1")

    # 7. budgets: refused BEFORE the provider is called
    class Priced(Provider):
        name, model_id = "priced-test", "priced-test-model"
        calls = 0

        def estimate(self, req):
            return ai.Usage(input_tokens=1000, output_tokens=500, cost_usd=0.02)

        def complete(self, req):
            Priced.calls += 1
            raise AssertionError("must not be reached")

    priced = Priced()
    raises("default run cap $0 refuses any billed call", ai.BudgetExceeded,
           lambda: X("scanned_calc_page", page_inputs, provider=priced, run=ai.Run(), cache=ai.ResultCache(tmp / "c3")), contains="run cap")
    raises("per-call cost cap refuses", ai.BudgetExceeded,
           lambda: X("scanned_calc_page", page_inputs, provider=priced, cache=ai.ResultCache(tmp / "c3"),
                     run=ai.Run(budget=ai.Budget(max_cost_usd_per_call=0.01, max_cost_usd_per_run=10))), contains="per-call")
    raises("max_calls cap refuses", ai.BudgetExceeded,
           lambda: X("scanned_calc_page", page_inputs, provider=priced, cache=ai.ResultCache(tmp / "c3"),
                     run=ai.Run(budget=ai.Budget(max_calls=0, max_cost_usd_per_run=10))), contains="max_calls")
    check("refused calls never reached the provider", Priced.calls == 0)
    check("cache hits are not charged", run.cost_usd == 0 and run.cache_hits >= 2, json.dumps(run.summary()))

    # 8. real provider: disabled, never imports the SDK
    a = ai.get_provider("anthropic")
    en, why = a.enabled()
    check("anthropic provider disabled by default", not en and "CALCGRAPH_AI_ENABLE_REAL" in why, why)
    check("anthropic default model is current", a.model_id == "claude-opus-5-5")
    raises("extract through anthropic refuses while disabled", ai.ProviderDisabled,
           lambda: X("scanned_calc_page", page_inputs, provider="anthropic", cache=ai.ResultCache(tmp / "c4")))
    real_key = os.environ.pop("ANTHROPIC_API_KEY", None)
    os.environ["CALCGRAPH_AI_ENABLE_REAL"] = "1"
    check("flag alone (no key) still disabled", not a.enabled()[0], a.enabled()[1])
    # Even fully enabled, the $0 default run cap refuses before any request is built.
    os.environ["ANTHROPIC_API_KEY"] = "sk-not-a-real-key"
    raises("flag + key but default $0 run budget still refuses before calling", ai.BudgetExceeded,
           lambda: X("scanned_calc_page", page_inputs, provider="anthropic", run=ai.Run(), cache=ai.ResultCache(tmp / "c5")))
    os.environ.pop("CALCGRAPH_AI_ENABLE_REAL")
    os.environ.pop("ANTHROPIC_API_KEY")
    if real_key is not None:
        os.environ["ANTHROPIC_API_KEY"] = real_key
    leaked = [m for m in ("anthropic", "openai") if m in sys.modules]
    check("no LLM SDK module was imported", not leaked, str(leaked))

    print(f"\n{'ALL PASS' if not FAILS else f'{len(FAILS)} FAILED: {FAILS}'}  (scratch: {tmp})")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
