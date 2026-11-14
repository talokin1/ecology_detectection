"""Global-grid first, old bbox-extract fallback, for the GES DISC / LP DAAC / GPCC / CHIRPS sources."""
from __future__ import annotations

import numpy as np

from . import global_grids as GG
from . import gridded as G
from . import tables as T


def _airs_flags(dates, var):
    return np.where(dates.dt.year == 2025, "airs_2025_bias_unverified", "")


def _try(src, region, prods, fallback, flags_fn=None, optional=()):
    out, notes = GG.load_from_global(prods, src, region, flags_fn, optional)
    if out is not None:
        return out, notes
    fo, fn = fallback(region)
    fn["fallback_reason"] = notes
    fn["path"] = "old_bbox_extract"
    return fo, fn


def load_merra2(region):
    return _try("merra2", region, ["merra2_slv", "merra2_flx"], T.load_merra2, optional=("merra2_wind", "merra2_ext"))


def load_gldas20(region):
    return _try("gldas20", region, ["gldas20"], T.load_gldas20, optional=("gldas20_rainf",))


def load_gldas21(region):
    return _try("gldas21", region, ["gldas21"], T.load_gldas21, optional=("gldas21_rainf",))


def load_imerg(region):
    return _try("gpm_imerg", region, ["gpm_imerg"], T.load_imerg)


def load_airs(region):
    return _try("airs", region, ["airs"], T.load_airs, _airs_flags)


def _modis_flags(tag):
    return lambda dates, var: np.full(len(dates), tag)


def load_modis(region):
    """Per-pixel QC'd MODIS (QC files) first; if QC files are missing, unQC'd global files flagged no_qc; then the
    old bbox extract (also no_qc)."""
    out, notes = GG.load_from_global(["mod13c2_qc", "mod11c3_qc"], "modis", region, _modis_flags("qc_pixel_masked"))
    if out is not None:
        for t in out:  # QC can leave few pixels (snow/cloud winters): flag, don't drop
            low = t["coverage_frac"].to_numpy(float) < 0.5
            t.loc[low, "flags"] = [";".join(x for x in (f, "qc_low_coverage_lt50pct") if x) for f in t.loc[low, "flags"]]
        notes["qc"] = "per-pixel QC applied before area averaging (see qc_report: MODIS QC rules)"
        return out, notes
    out, n2 = GG.load_from_global(["mod13c2", "mod11c3"], "modis", region, _modis_flags("no_qc"))
    if out is not None:
        n2["qc"] = "QC files missing -> no_qc"; n2["qc_fallback_reason"] = notes
        return out, n2
    fo, fn = T.load_modis(region)
    for t in fo:
        t["flags"] = [";".join(x for x in (f, "no_qc") if x) for f in t["flags"]]
    fn["fallback_reason"] = notes; fn["path"] = "old_bbox_extract"
    return fo, fn


def load_gpcc(region):
    out, notes = GG.load_gpcc_global(region)
    if out is not None:
        return out, notes
    fo, fn = T.load_gpcc(region); fn["fallback_reason"] = notes; fn["path"] = "old_bbox_extract"
    return fo, fn


def load_chirps(region):
    out, notes = GG.load_chirps_global(region)
    if out is not None:
        return out, notes
    fo, fn = G.load_chirps(region); fn["fallback_reason"] = notes; fn["path"] = "old_bbox_extract"
    return fo, fn
