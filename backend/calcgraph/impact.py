"""Impact propagation over the element graph and the calc graph (port of the 2D
prototype's propagate()).

change  - the element itself changes: everything downstream on the load path is hit
remove  - the element is removed: what it supported is re-framed (direct upstream
          neighbours, through a connection node to the member on the other side), the
          connection nodes that only served it go too, anything downstream that loses
          all its supports is orphaned (removed), then the re-framed members propagate
          downstream like a change.
Then: every calc linked to a hit or removed element is stale, and every calc
downstream of a stale calc in the calc graph is stale too.

`edges` are the element graph's `supports` edges (src is supported by dst). Waves count steps the
way packages/element-graph's loadPathDown counts depth: the step into a connection node counts,
the step out of it to a member does not, so the engine and the UI report the same depth.
"""
from __future__ import annotations

from collections import deque


def propagate(gid: str, mode: str, edges: list[dict], links: list[dict], calc_edges: list[dict],
              elements: dict[str, dict]) -> dict:
    down: dict[str, list[str]] = {}
    up: dict[str, list[str]] = {}
    for e in edges:
        down.setdefault(e["src"], []).append(e["dst"])
        up.setdefault(e["dst"], []).append(e["src"])

    removed: set[str] = set()
    seeds: list[str] = []
    why: dict[str, str] = {}
    mark = lambda g: elements.get(g, {}).get("mark") or elements.get(g, {}).get("name") or g  # noqa: E731

    if mode == "remove":
        removed.add(gid)
        for u in up.get(gid, []):
            if elements.get(u, {}).get("cat") == "Connection" and set(down.get(u, [])) <= removed:
                removed.add(u)
                for uu in up.get(u, []):
                    seeds.append(uu)
                    why[uu] = f"lost its support at {mark(gid)} (via connection) - re-frame / re-span"
            else:
                seeds.append(u)
                why[u] = f"lost its support at {mark(gid)} - re-frame / re-span"
        # orphans: downstream nodes whose every support is removed
        stack = list(down.get(gid, []))
        while stack:
            d = stack.pop()
            if d in removed:
                continue
            if all(s in removed for s in up.get(d, [])):
                removed.add(d)
                why[d] = f"only carried load from {mark(gid)} - now orphaned"
                stack.extend(down.get(d, []))
    else:
        seeds = [gid]
        why[gid] = "changed"

    hit: dict[str, int] = {}
    q: deque[str] = deque()
    for s in dict.fromkeys(seeds):
        if s not in removed:
            hit[s] = 0
            q.append(s)
    while q:  # 0-1 BFS: leaving a connection node costs 0, every other step 1
        x = q.popleft()
        step = 0 if elements.get(x, {}).get("cat") == "Connection" else 1
        for d in down.get(x, []):
            if d in removed or (d in hit and hit[d] <= hit[x] + step):
                continue
            hit[d] = hit[x] + step
            (q.appendleft if step == 0 else q.append)(d)

    stale: dict[str, str] = {}
    by_calc: dict[str, list[str]] = {}
    for l in links:
        if l.get("status") == "rejected":
            continue
        if l["global_id"] in hit or l["global_id"] in removed:
            by_calc.setdefault(l["calc_key"], []).append(l["global_id"])
    for k, gs in by_calc.items():
        names = sorted({mark(g) for g in gs})
        stale[k] = f"covers {', '.join(names[:6])}{' +' + str(len(names) - 6) + ' more' if len(names) > 6 else ''}"
    kdown: dict[str, list[str]] = {}
    for e in calc_edges:
        kdown.setdefault(e["src"], []).append(e["dst"])
    cq = list(stale)
    while cq:
        k = cq.pop(0)
        for d in kdown.get(k, []):
            if d not in stale:
                stale[d] = f"input from {k}"
                cq.append(d)
    return {"global_id": gid, "mode": mode, "removed": sorted(removed), "hit": hit, "why": why,
            "stale": stale, "waves": max(hit.values(), default=0)}
