"""Shared NormalizedRecord builders: every adapter normalizes the synthetic state the same way,
so the impact engine sees identical normalized records whichever platform served them."""
from __future__ import annotations

from .base import NormalizedRecord


def submittal(s: dict, platform: str, pid: str, number: str, link: str, raw: dict) -> NormalizedRecord:
    return NormalizedRecord(
        kind="submittal", id=str(pid), ref=s["ref"], platform=platform, number=number, title=s["title"],
        status=s["status"], element_ids=list(s["element_ids"]), dates=dict(s["dates"]), links={"self": link},
        fields={"stage": s["stage"], "stage_notes": s["stage_notes"], "spec_section": s["spec_section"],
                "spec_title": s["spec_title"], "package_kind": s["package_kind"], "level": s["level"],
                "sequence": s["sequence"], "revision": s["revision"], "response": s["response"],
                "ball_in_court": s["ball_in_court"], "activity_refs": s["activity_refs"]},
        raw=raw)


def rfi(r: dict, platform: str, pid: str, number: str, link: str, raw: dict) -> NormalizedRecord:
    return NormalizedRecord(
        kind="rfi", id=str(pid), ref=r["ref"], platform=platform, number=number, title=r["subject"],
        status=r["status"], element_ids=list(r["element_ids"]), dates=dict(r["dates"]), links={"self": link},
        fields={"question": r["question"], "answer": r["answer"], "ball_in_court": r["ball_in_court"],
                "cost_impact": r["cost_impact"], "schedule_impact": r["schedule_impact"],
                "drawing_number": r["drawing_number"], "spec_section": r["spec_section"]},
        raw=raw)


def change_event(c: dict, platform: str, pid: str, number: str, link: str, raw: dict) -> NormalizedRecord:
    return NormalizedRecord(
        kind="change_event", id=str(pid), ref=c["ref"], platform=platform, number=number, title=c["title"],
        status=c["status"], element_ids=list(c["element_ids"]), dates={"created": c["created"]}, links={"self": link},
        fields={"amount_usd": c["amount"], "reason": c["reason"], "line_items": c["line_items"],
                "change_order_refs": c["co_refs"], "estimate": True}, raw=raw)


def change_order(c: dict, platform: str, pid: str, number: str, link: str, raw: dict) -> NormalizedRecord:
    return NormalizedRecord(
        kind="change_order", id=str(pid), ref=c["ref"], platform=platform, number=number, title=c["title"],
        status=c["status"], element_ids=list(c["element_ids"]),
        dates={"created": c["created"], "approved": c["approved"]}, links={"self": link},
        fields={"amount_usd": c["amount"], "schedule_days": c["schedule_days"], "change_event_ref": c["change_event_ref"],
                "co_type": c["co_type"], "estimate": True}, raw=raw)


def budget_line(b: dict, platform: str, pid: str, link: str, raw: dict) -> NormalizedRecord:
    return NormalizedRecord(
        kind="budget_line", id=str(pid), ref=b["ref"], platform=platform, number=b["cost_code"], title=b["description"],
        status="active", element_ids=list(b["element_ids"]), links={"self": link},
        fields={"cost_code": b["cost_code"], "quantity": b["quantity"], "unit": b["unit"], "unit_cost_usd": b["unit_cost"],
                "amount_usd": b["amount"], "basis": b["basis"], "estimate": True}, raw=raw)


def cost_code(c: dict, platform: str, pid: str, link: str, raw: dict) -> NormalizedRecord:
    return NormalizedRecord(kind="cost_code", id=str(pid), ref=f"CC-{c['code']}", platform=platform, number=c["code"],
                            title=c["name"], status="active", links={"self": link},
                            fields={"code": c["code"], "division": c["division"]}, raw=raw)


def activity(a: dict, platform: str, pid: str, number: str, link: str, raw: dict) -> NormalizedRecord:
    return NormalizedRecord(
        kind="schedule_activity", id=str(pid), ref=a["ref"], platform=platform, number=number, title=a["name"],
        status=a["status"], element_ids=list(a["element_ids"]),
        dates={"early_start": a["early_start"], "early_finish": a["early_finish"], "late_start": a["late_start"],
               "late_finish": a["late_finish"], "actual_start": a["actual_start"], "actual_finish": a["actual_finish"]},
        links={"self": link},
        fields={"wbs": a["wbs"], "duration_days": a["duration"], "percent_complete": a["percent_complete"],
                "total_float_days": a["total_float"], "critical": a["critical"], "milestone": a["milestone"],
                "predecessors": a["predecessors"], "package_ref": a["package_ref"]}, raw=raw)


def sheet(s: dict, platform: str, pid: str, link: str, raw: dict) -> NormalizedRecord:
    return NormalizedRecord(kind="sheet", id=str(pid), ref=s["ref"], platform=platform, number=s["number"],
                            title=s["title"], status="active", element_ids=list(s["element_ids"]),
                            dates={"issued": s["issued"]}, links={"self": link},
                            fields={"discipline": s["discipline"], "revision": s["revision"],
                                    "version_set": s["version_set"]}, raw=raw)
