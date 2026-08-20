"""Offline tests for the scorers (no API calls). Run: .venv/bin/python -m pytest eval/tests -q
or .venv/bin/python -m unittest eval.tests.test_score"""
import unittest

from eval.score import score_dimcheck, score_takeoff
from eval.tasks import DIMCHECK, TAKEOFF


def dim_answer(findings, scale="1:100"):
    return {"scale": scale, "dimensions_checked": 7, "findings": findings, "summary": "x"}


def F(kind, labeled, unit, comp, element="e"):
    return {"kind": kind, "labeled_value": labeled, "unit": unit, "comparison_value": comp,
            "element": element, "explanation": ""}


class DimcheckTests(unittest.TestCase):
    def test_perfect_run(self):
        a = dim_answer([
            F("dimension_mismatch", 4.00, "m", 3.49, "bedroom"),
            F("chain_sum_mismatch", 10.00, "m", 10.575, "top chain"),
            F("dimension_mismatch", 5.86, "m", 5.80, "living"),
        ])
        s = score_dimcheck(a, DIMCHECK)
        self.assertTrue(s["found_primary"]); self.assertTrue(s["found_chain_sum"]); self.assertTrue(s["found_living_5.86"])
        self.assertEqual(s["false_positives"], 0); self.assertTrue(s["pass"]); self.assertGreater(s["score"], 0.95)
        self.assertTrue(s["scale_ok"])

    def test_original_session_result(self):
        # what the prototype found on 27 Jul 2026: 4.00 vs 3.49 and the chain sum
        a = dim_answer([F("dimension_mismatch", 4.00, "m", 3.49), F("chain_sum_mismatch", 10.00, "m", 10.575)])
        s = score_dimcheck(a, DIMCHECK)
        self.assertTrue(s["pass"]); self.assertAlmostEqual(s["score"], 0.9, delta=0.02)
        self.assertEqual(s["matched_ids"], ["bedroom_4.00", "chain_sum"])

    def test_units_cm_and_unknown(self):
        a = dim_answer([F("dimension_mismatch", 400, "cm", 3.485), F("dimension_mismatch", 4.0, "unknown", 3.485)])
        s = score_dimcheck(a, DIMCHECK)
        self.assertTrue(s["found_primary"])
        # second entry duplicates the primary; it must not count as a false positive
        self.assertEqual(s["false_positives"], 0)

    def test_label_only_partial(self):
        a = dim_answer([F("dimension_mismatch", 4.00, "m", None)])
        s = score_dimcheck(a, DIMCHECK)
        self.assertFalse(s["found_primary"]); self.assertTrue(s["found_primary_label_only"])
        self.assertFalse(s["pass"]); self.assertAlmostEqual(s["score"], 0.35, delta=0.01)

    def test_false_positive_on_correct_dimension(self):
        a = dim_answer([F("dimension_mismatch", 4.00, "m", 3.485), F("dimension_mismatch", 7.00, "m", 6.5, "depth")])
        s = score_dimcheck(a, DIMCHECK)
        self.assertTrue(s["found_primary"]); self.assertEqual(s["false_positives"], 1)
        self.assertEqual(s["flagged_correct_dimensions"], ["overall depth"]); self.assertFalse(s["pass"])

    def test_area_findings_not_penalized(self):
        a = dim_answer([F("dimension_mismatch", 4.00, "m", 3.485), F("area_mismatch", 31.2, "m2", 37.1, "WOHNEN")])
        s = score_dimcheck(a, DIMCHECK)
        self.assertEqual(s["area_findings"], 1); self.assertEqual(s["false_positives"], 0); self.assertTrue(s["pass"])

    def test_kind_is_ignored(self):
        # the schema no longer hints at categories; matching is by numbers only
        a = dim_answer([F("looks wrong", 4.00, "m", 3.49), F("arithmetic", 10.00, "m", 10.575),
                        F("label", 5.86, "m", 5.80), F("room size", 13.4, "unknown", 14.2)])
        s = score_dimcheck(a, DIMCHECK)
        self.assertTrue(s["found_primary"]); self.assertTrue(s["found_chain_sum"]); self.assertTrue(s["found_living_5.86"])
        self.assertEqual(s["area_findings"], 1); self.assertEqual(s["false_positives"], 0); self.assertTrue(s["pass"])

    def test_qualitative_remark_is_tracked_not_penalized(self):
        a = dim_answer([F("dimension_mismatch", 4.00, "m", 3.485), F("other", None, "unknown", None, "no windows drawn")])
        s = score_dimcheck(a, DIMCHECK)
        self.assertTrue(s["found_primary"]); self.assertEqual(s["false_positives"], 0)
        self.assertEqual(s["other_observations"], 1); self.assertTrue(s["pass"])

    def test_door_swing_is_valid_finding(self):
        a = dim_answer([F("dimension_mismatch", 4.00, "m", 3.485),
                        F("door symbol not aligned with wall opening", None, "unknown", 1.0,
                          "Door between WOHNEN and SCHLAFEN, in the vertical partition")])
        s = score_dimcheck(a, DIMCHECK)
        self.assertTrue(s["found_door_swing"]); self.assertEqual(s["false_positives"], 0); self.assertTrue(s["pass"])
        self.assertAlmostEqual(s["score"], 0.85, delta=0.01)

    def test_area_sum_and_imprecise_secondary_are_not_false_positives(self):
        a = dim_answer([F("dimension_mismatch", 4.00, "m", 3.485),
                        F("areas do not close", 51.5, "m2", 59.0, "sum of room areas vs net floor area"),
                        F("segment off", 5.86, "m", 5.68, "WOHNEN width")])
        s = score_dimcheck(a, DIMCHECK)
        self.assertEqual(s["false_positives"], 0); self.assertEqual(s["area_findings"], 1)
        self.assertFalse(s["found_living_5.86"]); self.assertTrue(s["pass"])

    def test_missed_everything(self):
        s = score_dimcheck(dim_answer([]), DIMCHECK)
        self.assertEqual(s["score"], 0.0); self.assertFalse(s["pass"])
        self.assertEqual(score_dimcheck(None, DIMCHECK)["score"], 0.0)

    def test_measured_way_off_is_partial(self):
        a = dim_answer([F("dimension_mismatch", 4.00, "m", 2.9)])
        s = score_dimcheck(a, DIMCHECK)
        self.assertFalse(s["found_primary"]); self.assertTrue(s["found_primary_label_only"])


def to_answer(supply, total=None, sheets=("M101", "M601"), excl=(), cfm=None):
    return {
        "supply_diffusers": [dict(tag=t, count=c, size=sz, model=m, mount="ceiling", cfm_values=[])
                             for t, c, sz, m in supply],
        "supply_diffuser_total": total if total is not None else sum(c for _, c, _, _ in supply),
        "return_exhaust_grilles": [], "exhaust_fans": [], "total_supply_cfm": cfm,
        "excluded_false_positives": list(excl), "sheets_used": list(sheets), "summary": "",
    }


GOLD = [("A", 5, '6" round', "SCD"), ("B", 4, '8"Ø', "SCD"), ("C", 15, "10 inch round", "Price SCD"),
        ("D", 1, "12\"", "SCD"), ("H", 3, "18x8", "520D"), ("I", 4, "14 x 8 sidewall", "520D"),
        ("J", 3, "12x12 face, 8\" neck", "SMD")]


class TakeoffTests(unittest.TestCase):
    def test_gold(self):
        s = score_takeoff(to_answer(GOLD, excl=["F/121 room number", "M/123 room number"], cfm=10000), TAKEOFF)
        self.assertTrue(s["pass"]); self.assertEqual(s["score"], 1.0)
        self.assertEqual(s["count_exact_frac"], 1.0); self.assertEqual(s["size_ok_frac"], 1.0)
        self.assertTrue(s["false_positives_excluded_explicitly"]); self.assertTrue(s["cfm_ok"])
        self.assertEqual(s["counts_vector"], [5, 4, 15, 1, 3, 4, 3])

    def test_first_pass_with_false_positives(self):
        # the prototype's first tally before the M601 cross-check
        supply = GOLD + [("F", 1, "", ""), ("M", 1, "", "")]
        s = score_takeoff(to_answer(supply, sheets=["M101"]), TAKEOFF)
        self.assertFalse(s["pass"]); self.assertEqual(s["false_positive_tags"], ["F", "M"])
        self.assertFalse(s["cross_verified"]); self.assertFalse(s["total_exact"])
        self.assertLess(s["score"], 0.85)

    def test_off_by_one_and_missing_type(self):
        supply = [(t, c - (1 if t == "C" else 0), sz, m) for t, c, sz, m in GOLD if t != "D"]
        s = score_takeoff(to_answer(supply), TAKEOFF)
        self.assertEqual(s["interpretation"], "all_supply")
        self.assertEqual(s["types_missing"], ["D"]); self.assertEqual(s["per_type"]["C"]["reported"], 14)
        self.assertTrue(s["per_type"]["C"]["close"]); self.assertFalse(s["per_type"]["C"]["exact"])
        self.assertFalse(s["pass"]); self.assertGreater(s["score"], 0.6)

    def test_ceiling_only_reading_with_sidewall_noted(self):
        # the strict reading of "ceiling air vents": H and I are sidewall grilles (M601 note 10)
        ceiling = [g for g in GOLD if g[0] not in ("H", "I")]
        excl = ["H (3 ea, 18x8) sidewall supply grille, not ceiling", "I (4 ea, 14x8) sidewall, not ceiling"]
        s = score_takeoff(to_answer(ceiling, excl=excl, cfm=6550), TAKEOFF)
        self.assertEqual(s["interpretation"], "ceiling_only"); self.assertEqual(s["expected_total"], 28)
        self.assertTrue(s["total_exact"]); self.assertTrue(s["sidewall_noted"]); self.assertTrue(s["cfm_ok"])
        self.assertTrue(s["pass"]); self.assertEqual(s["score"], 1.0)
        self.assertEqual(s["counts_vector"], [5, 4, 15, 1, None, None, 3])

    def test_ceiling_only_reading_silent_about_sidewall(self):
        ceiling = [g for g in GOLD if g[0] not in ("H", "I")]
        s = score_takeoff(to_answer(ceiling), TAKEOFF)
        self.assertEqual(s["interpretation"], "ceiling_only")
        self.assertFalse(s["sidewall_noted"]); self.assertFalse(s["pass"]); self.assertAlmostEqual(s["score"], 0.85, delta=0.01)

    def test_mixed_reading_counts_as_all_supply(self):
        # reports H but forgets I: scored against all 7 types
        s = score_takeoff(to_answer([g for g in GOLD if g[0] != "I"]), TAKEOFF)
        self.assertEqual(s["interpretation"], "all_supply"); self.assertEqual(s["types_missing"], ["I"])
        self.assertFalse(s["pass"])

    def test_tag_normalisation_and_merge(self):
        supply = [("Type C", 10, "10\"", "SCD"), ("c", 5, "10\"", "SCD")]
        s = score_takeoff(to_answer(supply), TAKEOFF)
        self.assertEqual(s["per_type"]["C"]["reported"], 15); self.assertTrue(s["per_type"]["C"]["exact"])

    def test_size_matching(self):
        # H needs both 18 and 8; a size of just "18" is wrong, "8x18" is fine
        s = score_takeoff(to_answer([("H", 3, "18 inch", "520D"), ("I", 4, "8x14", "520D")]), TAKEOFF)
        self.assertFalse(s["per_type"]["H"]["size_ok"]); self.assertTrue(s["per_type"]["I"]["size_ok"])

    def test_none_answer(self):
        s = score_takeoff(None, TAKEOFF)
        self.assertEqual(s["score"], 0.0); self.assertFalse(s["parsed"])


if __name__ == "__main__":
    unittest.main()
