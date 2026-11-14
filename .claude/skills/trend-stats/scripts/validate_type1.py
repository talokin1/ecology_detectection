"""Monte-Carlo validation of trend tests: false-positive rate (no trend) and power (with trend)
under AR(1) noise. Produces the table quoted in docs/10-methods.md.

Usage: python validate_type1.py [--runs 300]

SI-assisted (Claude, Anthropic).
"""
import argparse

import numpy as np

import trend_stats as ts


def ar1(n, phi, rng):
    e = rng.normal(0, 1, n)
    x = np.empty(n)
    x[0] = e[0] / np.sqrt(1 - phi**2)
    for i in range(1, n):
        x[i] = phi * x[i - 1] + e[i]
    return x


def main(runs: int, seed: int = 0) -> None:
    rng = np.random.default_rng(seed)
    tests = {
        "MK original": lambda t, y: ts.mann_kendall(t, y, method="original")["p"],
        "MK Hamed-Rao": lambda t, y: ts.mann_kendall(t, y, method="hamed_rao")["p"],
        "MK Yue-Wang (default)": lambda t, y: ts.mann_kendall(t, y, method="yue_wang")["p"],
        "OLS n_eff": lambda t, y: ts.ols_trend(t, y)["p"],
    }
    trend = 0.06  # noise-sd per year
    print(f"runs={runs}, alpha=0.05, AR(1) unit-variance innovations, power trend={trend}/yr")
    print("| n (months) | phi | test | false-positive rate | power |")
    print("|---|---|---|---|---|")
    for n in (120, 240, 480):
        t = np.arange(n) / 12
        for phi in (0.0, 0.3, 0.6):
            fp = dict.fromkeys(tests, 0)
            pw = dict.fromkeys(tests, 0)
            for _ in range(runs):
                y = ar1(n, phi, rng)
                y2 = y + trend * t
                for name, f in tests.items():
                    fp[name] += f(t, y) < 0.05
                    pw[name] += f(t, y2) < 0.05
            for name in tests:
                print(f"| {n} | {phi} | {name} | {fp[name] / runs:.3f} | {pw[name] / runs:.3f} |")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=300)
    main(ap.parse_args().runs)
