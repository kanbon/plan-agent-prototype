"""Deterministic scorers. Input: the agent's structured answer (dict) + task ground truth.
Output: a flat dict of metrics; `score` in [0, 1] and `pass` (bool) are the headline fields.

Scoring is tolerant about form (units, string formats) and strict about facts (which
dimension is wrong, how many diffusers of which type).
"""
from __future__ import annotations

import re
from typing import Any

from .tasks import Task

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _num(x: Any) -> float | None:
    if x is None:
        return None
    if isinstance(x, bool):
        return None
    if isinstance(x, (int, float)):
        return float(x)
    if isinstance(x, str):
        m = re.search(r"-?\d+(?:[.,]\d+)?", x)
        return float(m.group().replace(",", ".")) if m else None
    return None


def _to_m(value: float | None, unit: str | None) -> list[float]:
    """Return the plausible metre interpretations of a printed value.

    Plans print walls as '30' (cm) and rooms as '4.00' (m). Agents may report either the
    printed number or a converted one, so accept every plausible reading."""
    if value is None:
        return []
    u = (unit or "unknown").lower()
    if u == "m":
        cands = [value]
    elif u == "cm":
        cands = [value / 100]
    elif u == "mm":
        cands = [value / 1000]
    else:
        cands = [value, value / 100, value / 1000]
    return cands


def _close(a: float | None, b: float | None, tol: float) -> bool:
    return a is not None and b is not None and abs(a - b) <= tol


def _matches_label(finding: dict, labeled: float, unit: str, tol: float = 0.011) -> bool:
    cands = _to_m(_num(finding.get("labeled_value")), finding.get("unit"))
    target = _to_m(labeled, unit)[0]
    return any(_close(c, target, tol) for c in cands)


# ---------------------------------------------------------------------------
# Task 1: dimension check
# ---------------------------------------------------------------------------

def score_dimcheck(answer: dict[str, Any] | None, task: Task) -> dict[str, Any]:
    gt = task.ground_truth
    tol = gt["tolerance_m"]
    out: dict[str, Any] = {
        "task": task.id,
        "parsed": answer is not None,
        "found_primary": False,
        "found_primary_label_only": False,
        "primary_measured_m": None,
        "primary_abs_error_m": None,
        "found_living_5.86": False,
        "found_chain_sum": False,
        "found_door_swing": False,
        "area_findings": 0,
        "other_observations": 0,        # non-numeric remarks (no printed value); tracked, not scored
        "false_positives": 0,
        "flagged_correct_dimensions": [],
        "n_findings": 0,
        "dimensions_checked": None,
        "scale_ok": False,
        "matched_ids": [],
        "unmatched": [],
    }
    if answer is None:
        out["score"] = 0.0
        out["pass"] = False
        return out

    findings = answer.get("findings") or []
    out["n_findings"] = len(findings)
    out["dimensions_checked"] = answer.get("items_checked", answer.get("dimensions_checked"))
    scale = str(answer.get("scale") or "")
    out["scale_ok"] = bool(re.search(r"1\s*[:/]\s*100\b", scale))

    # Findings are classified by their numbers only. The declared `kind` is free text
    # and is recorded but not used for matching, so the prompt and schema can stay
    # free of hints about what kind of error to look for.
    prim = gt["primary"]
    chain = next(x for x in gt["secondary"] if x["id"] == "chain_sum")
    living = next(x for x in gt["secondary"] if x["id"] == "living_5.86")
    matched: list[str] = []
    for f in findings:
        kind = f.get("kind")
        lab = _num(f.get("labeled_value"))
        comp = _num(f.get("comparison_value"))
        hit = None

        # chain-sum inconsistency: 10.00 printed vs 10.575 summed (either direction)
        if (_matches_label(f, chain["labeled"], chain["unit"]) and _close(comp, chain["actual_m"], 0.02)) or (
                _matches_label(f, chain["actual_m"], "m") and _close(comp, chain["labeled"], 0.02)):
            hit = chain["id"]
            out["found_chain_sum"] = True

        # primary: bedroom 4.00 vs 3.485
        elif _matches_label(f, prim["labeled"], prim["unit"]):
            if _close(comp, prim["actual_m"], tol):
                hit = prim["id"]
                out["found_primary"] = True
                out["primary_measured_m"] = comp
                out["primary_abs_error_m"] = abs(comp - prim["actual_m"])
            elif not out["found_primary"]:
                # right label flagged, but measurement missing or off: partial credit
                out["found_primary_label_only"] = True
                hit = prim["id"] + "?"
                out["primary_measured_m"] = comp
                out["primary_abs_error_m"] = None if comp is None else abs(comp - prim["actual_m"])

        # living room 5.86 vs 5.80 (label flagged with an off measurement: no bonus, no penalty)
        elif _matches_label(f, living["labeled"], living["unit"]):
            if _close(comp, living["actual_m"], tol):
                hit = living["id"]
                out["found_living_5.86"] = True
            else:
                hit = living["id"] + "?"

        # area labels (tracked, not scored): printed area value, or the computed one
        if hit is None:
            unit = str(f.get("unit") or "").lower()
            for a in gt["areas"]:
                if (_close(lab, a["labeled"], 0.05) and (unit == "m2" or _close(comp, a["actual_m2"], 0.6))) or (
                        a["id"] == "area_sum" and unit == "m2" and _close(comp, a["actual_m2"], 1.2)):
                    hit = a["id"]
                    out["area_findings"] += 1
                    break

        # the misplaced bedroom door swing (real defect, matched by text)
        if hit is None and lab is None:
            d = gt["door_swing"]
            txt = " ".join(str(f.get(k) or "") for k in ("kind", "element", "explanation")).lower()
            if (all(k in txt for k in d["keywords_all"]) and any(k in txt for k in d["keywords_any"])
                    and any(k in txt for k in d["location_any"])):
                hit = d["id"]
                out["found_door_swing"] = True

        if hit is None and lab is None and comp is None:
            # qualitative remark without numbers: the ground truth cannot judge it either way
            hit = "observation"
            out["other_observations"] += 1

        if hit is None:
            # did the agent flag a dimension that is actually correct?
            for c in gt["correct_labels"]:
                if _matches_label(f, c["labeled"], c["unit"]):
                    out["flagged_correct_dimensions"].append(c["element"])
                    break
            out["false_positives"] += 1
            out["unmatched"].append({"kind": kind, "labeled": f.get("labeled_value"),
                                     "unit": f.get("unit"), "comparison": comp,
                                     "element": f.get("element")})
        elif hit != "observation":
            matched.append(hit)

    out["matched_ids"] = sorted(set(matched))

    # score: primary dominates; secondaries are bonus; false positives cost.
    score = 0.0
    if out["found_primary"]:
        score += 0.70
        err = out["primary_abs_error_m"] or 0.0
        score += 0.10 * max(0.0, 1.0 - err / tol)          # measurement precision
    elif out["found_primary_label_only"]:
        score += 0.35
    score += 0.10 if out["found_chain_sum"] else 0.0
    score += 0.10 if out["found_living_5.86"] else 0.0
    score += 0.05 if out["found_door_swing"] else 0.0
    score -= 0.15 * out["false_positives"]
    out["score"] = round(max(0.0, min(1.0, score)), 3)
    out["pass"] = out["found_primary"] and out["false_positives"] == 0
    return out


# ---------------------------------------------------------------------------
# Task 2: diffuser takeoff
# ---------------------------------------------------------------------------

def _norm_tag(t: Any) -> str:
    s = str(t or "").strip().upper()
    s = re.sub(r"^(TYPE|TAG)\s*", "", s)
    return s.strip(" -:")


def _size_ok(size: str, token_groups: list[list[str]]) -> bool:
    """token_groups is a list of alternatives; each alternative is a list of numbers that
    must all appear in the size string (as whole numbers)."""
    nums = re.findall(r"\d+", size or "")
    for alt in token_groups:
        if all(t in nums for t in alt):
            return True
    return False


def score_takeoff(answer: dict[str, Any] | None, task: Task) -> dict[str, Any]:
    """Interpretation-aware: "ceiling air vents" can mean every supply diffuser (35, the
    original session's answer) or only the ceiling-mounted ones (28; H and I are sidewall
    grilles per M601 note 10). A run that reports H or I as supply is scored as
    `all_supply`; one that reports neither is scored as `ceiling_only`, and then it must
    still acknowledge that the sidewall units exist to pass."""
    gt = task.ground_truth
    gts = gt["supply"]
    all_tags = list(gts)
    out: dict[str, Any] = {
        "task": task.id,
        "parsed": answer is not None,
        "interpretation": None,         # "all_supply" | "ceiling_only"
        "expected_total": None,
        "reported_total": None,
        "computed_total": None,
        "total_exact": False,
        "total_within_2": False,
        "types_reported": [],
        "types_missing": [],
        "types_extra": [],
        "type_jaccard": 0.0,
        "per_type": {},                 # every GT tag -> reported/expected/exact/close/size/model
        "count_exact_frac": 0.0,        # over the tags of the chosen interpretation
        "count_close_frac": 0.0,
        "count_abs_error_sum": None,
        "size_ok_frac": 0.0,
        "model_ok_frac": 0.0,
        "sidewall_noted": False,        # ceiling_only runs: H/I mentioned as sidewall/excluded
        "false_positive_tags": [],      # F/M or any tag outside the GT set reported as supply
        "false_positives_excluded_explicitly": False,
        "used_floor_plan": False,
        "used_schedule": False,
        "cross_verified": False,
        "cfm_reported": None,
        "cfm_ok": False,
        "return_grilles_mentioned": 0,
        "exhaust_fans_mentioned": 0,
        "counts_vector": None,          # counts in GT tag order (A,B,C,D,H,I,J), for agreement stats
    }
    if answer is None:
        out["score"] = 0.0
        out["pass"] = False
        return out

    supply = answer.get("supply_diffusers") or []
    reported: dict[str, dict] = {}
    for item in supply:
        tag = _norm_tag(item.get("tag"))
        if not tag:
            continue
        if tag in reported:                       # merge duplicates
            reported[tag]["count"] = (reported[tag].get("count") or 0) + (item.get("count") or 0)
        else:
            reported[tag] = dict(item)
    rep_tags = set(reported)

    # which reading did the run take?
    sidewall = set(gt["sidewall_tags"])
    interp = "all_supply" if rep_tags & sidewall else "ceiling_only"
    exp = gt["interpretations"][interp]
    exp_tags = list(exp["tags"])
    exp_set = set(exp_tags)
    out["interpretation"] = interp
    out["expected_total"] = exp["total"]

    out["types_reported"] = sorted(rep_tags)
    out["types_missing"] = sorted(exp_set - rep_tags)
    out["types_extra"] = sorted(rep_tags - exp_set)
    out["type_jaccard"] = round(len(exp_set & rep_tags) / len(exp_set | rep_tags), 3) if (exp_set | rep_tags) else 0.0

    exact = close = size_ok = model_ok = 0
    abs_err = 0
    vec = []
    for tag in all_tags:
        g = gts[tag]
        r = reported.get(tag)
        n = None if r is None else r.get("count")
        e = g["count"]
        is_exact = n == e
        is_close = n is not None and abs(n - e) <= 1
        s_ok = r is not None and _size_ok(str(r.get("size", "")), g["size_tokens"])
        m_ok = r is not None and g["model"].lower() in str(r.get("model", "")).lower()
        out["per_type"][tag] = {"reported": n, "expected": e, "exact": is_exact, "close": is_close,
                                "size": None if r is None else r.get("size"), "size_ok": s_ok,
                                "model": None if r is None else r.get("model"), "model_ok": m_ok,
                                "in_interpretation": tag in exp_set}
        vec.append(n)
        if tag in exp_set:
            exact += is_exact
            close += is_close
            abs_err += abs((n or 0) - e)
            size_ok += s_ok
            model_ok += m_ok
    ntypes = len(exp_tags)
    out["count_exact_frac"] = round(exact / ntypes, 3)
    out["count_close_frac"] = round(close / ntypes, 3)
    out["count_abs_error_sum"] = abs_err
    out["size_ok_frac"] = round(size_ok / ntypes, 3)
    out["model_ok_frac"] = round(model_ok / ntypes, 3)
    out["counts_vector"] = vec

    fp_tags = set(gt["false_positive_tags"]) | set(gt["return_grille_tags"])
    out["false_positive_tags"] = sorted(t for t in rep_tags if t in fp_tags or t not in gts)

    free_text = " ".join(str(x) for x in (answer.get("excluded_false_positives") or []))
    free_text_u = (free_text + " " + str(answer.get("summary") or "")).upper()
    out["false_positives_excluded_explicitly"] = any(
        f"{t}/{v}" in free_text.upper() or f"{t} {v}" in free_text.upper()
        or f"{t}-{v}" in free_text.upper() or str(v) in free_text.upper()
        for t, v in gt["false_positive_tags"].items()
    )
    if interp == "ceiling_only":
        # did the run say why H and I are not in the count?
        out["sidewall_noted"] = ("SIDEWALL" in free_text_u or "SIDE WALL" in free_text_u or "WALL" in free_text_u) and all(
            re.search(rf"\b(TYPE\s+)?{t}\b", free_text_u) for t in sidewall)
    else:
        out["sidewall_noted"] = True

    computed_total = sum((reported.get(t, {}).get("count") or 0) for t in rep_tags)
    out["computed_total"] = computed_total
    rt = answer.get("supply_diffuser_total")
    out["reported_total"] = rt
    total = rt if isinstance(rt, int) else computed_total
    out["total_exact"] = total == exp["total"]
    out["total_within_2"] = abs(total - exp["total"]) <= 2

    sheets = " ".join(str(s) for s in (answer.get("sheets_used") or [])).upper()
    out["used_floor_plan"] = gt["floor_plan_sheet"] in sheets
    out["used_schedule"] = gt["schedule_sheet"] in sheets
    out["cross_verified"] = out["used_floor_plan"] and out["used_schedule"]

    cfm = answer.get("total_supply_cfm")
    out["cfm_reported"] = cfm
    if isinstance(cfm, (int, float)):
        out["cfm_ok"] = abs(cfm - exp["cfm"]) <= gt["cfm_tolerance"] * exp["cfm"]

    out["return_grilles_mentioned"] = len(answer.get("return_exhaust_grilles") or [])
    out["exhaust_fans_mentioned"] = len(answer.get("exhaust_fans") or [])

    # composite score
    per_type_score = (exact + 0.5 * (close - exact)) / ntypes
    score = (
        0.40 * per_type_score
        + 0.15 * out["type_jaccard"]
        + 0.15 * (1.0 if out["total_exact"] else 0.5 if out["total_within_2"] else 0.0)
        + 0.15 * out["size_ok_frac"]
        + 0.10 * (1.0 if not out["false_positive_tags"] else 0.0)
        + 0.05 * (1.0 if out["cross_verified"] else 0.0)
    )
    if not out["sidewall_noted"]:
        score -= 0.15          # ceiling_only without saying the sidewall units exist
    out["score"] = round(max(0.0, min(1.0, score)), 3)
    out["pass"] = (
        out["total_exact"]
        and out["count_exact_frac"] == 1.0
        and not out["false_positive_tags"]
        and out["sidewall_noted"]
    )
    return out


SCORERS = {"dimcheck": score_dimcheck, "takeoff": score_takeoff}


def score(task: Task, answer: dict[str, Any] | None) -> dict[str, Any]:
    return SCORERS[task.id](answer, task)
