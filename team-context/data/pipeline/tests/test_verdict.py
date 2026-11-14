"""B-3 conservative-verdict rule. SI-assisted (GOD / Grok Bot), pending team review."""
import importlib.util
from pathlib import Path

import pandas as pd

PIPE = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("ukpipe_verdict", PIPE / "ukpipe" / "verdict.py")
v = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(v)


def _df():
    return pd.DataFrame({
        "yw_p": [0.01, 0.02, 0.30, 0.03],
        "yw_ols_neff_p": [0.001, 0.09, 0.01, 0.06],
        "robust_call": ["significant at 0.05 (repo MK Yue-Wang; verdict strong)",
                        "significant at 0.05 (repo MK Yue-Wang; verdict moderate)",
                        "not significant at 0.05 (repo MK Yue-Wang; verdict none)",
                        "FORCING DIAGNOSTIC. [raw call: significant at 0.05 (repo MK Yue-Wang; verdict moderate)]"],
        "mt_bh_pass": [True, True, False, True], "mt_bonferroni_pass": [True, False, False, False],
        "mk_yw_p": [0.1] * 4,
    })


def test_conservative_rule():
    out = v.apply_conservative_verdict(_df())
    assert out.robust_call[0].startswith("significant")  # agreeing row untouched
    assert out.mt_bh_pass[0] and out.mt_bonferroni_pass[0]
    assert out.robust_call[1].startswith("method-dependent") and not out.mt_bh_pass[1]
    assert "methods disagree" in out.robust_call[2]
    assert "[raw call: method-dependent" in out.robust_call[3] and not out.mt_bh_pass[3]
    assert list(out.conservative_override) == [False, True, True, True]
    assert v.violations(out).empty and len(v.violations(_df().assign(yw_ols_neff_agree=[True, False, False, False]))) == 2


def test_idempotent_and_rename():
    once = v.apply_conservative_verdict(_df())
    assert once.equals(v.apply_conservative_verdict(once))
    assert "sens_pymk_yw_p_do_not_use" in v.rename_sensitivity_columns(once).columns


def test_committed_v14_tables_pass_gate():
    for reg in ("ukraine_bbox", "ukraine_mask"):
        t = pd.read_csv(PIPE / "outputs" / "v1.4" / f"{reg}_trends.csv")
        assert v.violations(t).empty, reg
        assert "mk_yw_p" not in t.columns
