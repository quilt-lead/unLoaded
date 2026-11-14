"""The single AI step: ``extract(task, inputs, schema=None) -> Result``.

Order of operations (each failure is loud, none is swallowed):
 1. resolve the task spec and the output schema (must subclass the task's schema)
 2. compute ``inputs_key`` and ``cache_key`` (content hashes; see cache.py)
 3. cache hit -> re-validate against the schema and return, no provider call, no spend
 4. provider enabled? (a disabled provider raises ProviderDisabled)
 5. budget pre-check on the provider's estimate (raises BudgetExceeded BEFORE calling)
 6. provider.complete -> raw JSON -> ``schema.model_validate_json`` (structured output)
 7. evidence check: every cited id exists in the inputs; every nested bbox lies
    inside the evidence it cites; the task's semantic validator passes
 8. record actual spend, write the cache entry, return Result with method="ai"
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from .budget import Run
from .cache import ResultCache, sha256_json
from .providers import Provider, ProviderDisabled, ProviderRequest, get_provider
from .tasks import TaskSpec, get_task
from .types import AIInputs, AIOutput, AIProvenance, Evidence, Usage

_BBOX_TOL = 0.5  # points of slack for rounding in model-reported boxes


class AIEvidenceError(ValueError):
    """The output cites evidence it was not given, or a bbox outside its evidence."""


class AIOutputInvalid(ValueError):
    """The provider's output failed the schema or the task's semantic validator."""


@dataclass(frozen=True)
class Result:
    task: str
    output: AIOutput
    provenance: AIProvenance
    cached: bool
    usage: Usage  # zero on a cache hit

    def to_record(self) -> dict[str, Any]:
        """The fact plus its provenance, ready for a schema adapter / the store."""
        return {"task": self.task,
                "value": self.output.model_dump(mode="json", exclude={"evidence_refs", "confidence"}),
                "provenance": self.provenance.model_dump(mode="json")}


_default_run: Run | None = None


def default_run() -> Run:
    global _default_run
    if _default_run is None:
        _default_run = Run()
    return _default_run


def _keys(spec: TaskSpec, schema: type[AIOutput], inputs: AIInputs, provider: Provider) -> tuple[str, str, dict]:
    json_schema = schema.model_json_schema()
    inputs_key = sha256_json({
        "task": spec.name, "task_version": spec.version,
        "instructions_sha256": spec.instructions_sha256,
        "output_schema": json_schema, "inputs": inputs.key_material(),
    })
    cache_key = sha256_json({"inputs_key": inputs_key, "provider": provider.name, "model_id": provider.model_id})
    return inputs_key, cache_key, json_schema


def _inside(inner, outer) -> bool:
    return (inner[0] >= outer[0] - _BBOX_TOL and inner[1] >= outer[1] - _BBOX_TOL
            and inner[2] <= outer[2] + _BBOX_TOL and inner[3] <= outer[3] + _BBOX_TOL)


def _check_evidence(out: AIOutput, inputs: AIInputs) -> list[Evidence]:
    by_id = inputs.evidence_by_id()
    cited: set[str] = set()

    def ref(eid: Any, where: str) -> Evidence:
        if not isinstance(eid, str) or eid not in by_id:
            raise AIEvidenceError(f"{where}: cites evidence {eid!r} not in inputs ({sorted(by_id)})")
        cited.add(eid)
        return by_id[eid]

    def walk(node: Any, where: str) -> None:
        if isinstance(node, dict):
            if "evidence_ref" in node:
                ev = ref(node["evidence_ref"], where)
                bbox = node.get("bbox")
                if bbox is not None:
                    if ev.bbox is None:
                        raise AIEvidenceError(f"{where}: bbox given but evidence {ev.id} has no bbox to bound it")
                    if not _inside(bbox, ev.bbox):
                        raise AIEvidenceError(f"{where}: bbox {bbox} outside evidence {ev.id} bbox {ev.bbox}")
            for eid in node.get("evidence_refs", []) or []:
                ref(eid, where)
            for k, v in node.items():
                walk(v, f"{where}.{k}")
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, f"{where}[{i}]")

    walk(out.model_dump(mode="json"), "output")
    return [e for e in inputs.evidence if e.id in cited]  # input order, deterministic


def _validate(spec: TaskSpec, schema: type[AIOutput], raw_json: str, inputs: AIInputs) -> tuple[AIOutput, list[Evidence]]:
    try:
        out = schema.model_validate_json(raw_json)
    except ValidationError as e:
        raise AIOutputInvalid(f"{spec.name}: output failed schema {schema.__name__}: {e}") from e
    evidence = _check_evidence(out, inputs)
    if spec.validate is not None:
        try:
            spec.validate(inputs, out)
        except (ValueError, AssertionError) as e:
            raise AIOutputInvalid(f"{spec.name}: {e}") from e
    return out, evidence


def extract(task: str | TaskSpec, inputs: AIInputs | dict, schema: type[AIOutput] | None = None, *,
            provider: str | Provider | None = None, run: Run | None = None,
            cache: ResultCache | None = None, use_cache: bool = True) -> Result:
    spec = task if isinstance(task, TaskSpec) else get_task(task)
    schema = schema or spec.output_schema
    if not issubclass(schema, spec.output_schema):
        raise TypeError(f"{spec.name}: schema {schema.__name__} must subclass {spec.output_schema.__name__}")
    inputs = inputs if isinstance(inputs, AIInputs) else AIInputs.model_validate(inputs)
    prov = provider if isinstance(provider, Provider) else get_provider(provider)
    run = run or default_run()
    cache = cache or ResultCache()

    inputs_key, cache_key, json_schema = _keys(spec, schema, inputs, prov)
    label = f"ai:{spec.name}@{prov.name}/{prov.model_id}"

    def provenance(out: AIOutput, evidence: list[Evidence], model_id: str) -> AIProvenance:
        return AIProvenance(rule_id=f"ai:{spec.name}", rule_version=spec.version, provider=prov.name,
                            model_id=model_id, confidence=out.confidence, evidence=evidence,
                            inputs_key=inputs_key, cache_key=cache_key,
                            instructions_sha256=spec.instructions_sha256)

    if use_cache:
        entry = cache.get(spec.name, cache_key)
        if entry is not None:
            try:
                out, evidence = _validate(spec, schema, entry["raw_json"], inputs)
            except (AIOutputInvalid, AIEvidenceError, KeyError):
                entry = None  # stale against the current schema/validator: treat as a miss
            else:
                run.hit()
                return Result(spec.name, out, provenance(out, evidence, entry["model_id"]), True, Usage())

    ok, why = prov.enabled()
    if not ok:
        raise ProviderDisabled(f"{label}: {why}")
    req = ProviderRequest(task=spec, inputs=inputs, output_schema=schema, json_schema=json_schema,
                          inputs_key=inputs_key, max_output_tokens=spec.max_output_tokens)
    run.precheck(prov.estimate(req), label=label)
    resp = prov.complete(req)
    run.record(resp.usage, label=label)
    out, evidence = _validate(spec, schema, resp.raw_json, inputs)
    if use_cache:
        cache.put(spec.name, cache_key, {"raw_json": resp.raw_json, "model_id": resp.model_id,
                                         "usage": resp.usage.model_dump(), "inputs_key": inputs_key})
    return Result(spec.name, out, provenance(out, evidence, resp.model_id), False, resp.usage)
