"""
thermal_simulation.py -- Run the lumped-capacitance simulation, print key
results, save a plot and a CSV.

Usage:
    python thermal_simulation.py              # runs with the defaults below
    python thermal_simulation.py --show       # also opens the plot window
"""

from __future__ import annotations

import argparse
import csv
import os
import sys

import matplotlib

import numpy as np

import thermal_model as tm

# ==========================================================================
# CONFIGURATION  --  ALL VALUES BELOW ARE ILLUSTRATIVE ASSUMPTIONS
# They are NOT measured data, NOT manufacturer specifications and NOT from a
# validated source. Replace them with documented values for a real study.
# ==========================================================================
PARAMS = tm.ThermalParameters(
    heat_generation_W=5.0,           # Q_gen: assumed electrical power dissipated as heat [W]
    mass_kg=0.05,                    # m: assumed effective thermal mass [kg]
    specific_heat_J_per_kgK=900.0,   # cp: assumed (order of magnitude of aluminium) [J/(kg K)]
    area_m2=0.01,                    # A: assumed effective exposed area [m^2]
    h_W_per_m2K=10.0,                # h: assumed natural-convection-like value [W/(m^2 K)]
    ambient_C=25.0,                  # T_inf: assumed ambient [degC]
    initial_C=25.0,                  # T0: assumed initial component temperature [degC]
    duration_s=3000.0,               # simulated duration [s]
    dt_s=1.0,                        # time step [s]
)
THRESHOLD_C = 60.0                   # user-defined temperature threshold [degC]
METHOD = "rk4"                       # "rk4" or "euler"
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "outputs")
# ==========================================================================


def run(params: tm.ThermalParameters, threshold_C: float, method: str) -> dict:
    """Simulate and collect every quantity reported to the user."""
    sim = tm.simulate(params, method=method)
    t, T = sim["time_s"], sim["temperature_C"]
    T_exact = tm.analytical_temperature(params, t)
    return {
        "params": params,
        "method": method,
        "threshold_C": threshold_C,
        "time_s": t,
        "temperature_C": T,
        "analytical_C": T_exact,
        "T_ss_C": tm.steady_state_temperature(params),
        "tau_s": tm.time_constant(params),
        "t_threshold_num_s": tm.time_to_threshold(t, T, threshold_C),
        "t_threshold_exact_s": tm.analytical_time_to_temperature(params, threshold_C),
        "max_abs_error_K": float(np.max(np.abs(T - T_exact))),
        "energy": tm.energy_balance_residual(params, t, T),
    }


def print_summary(r: dict) -> None:
    p = r["params"]

    def fmt(x, unit):
        return "not reached during simulation" if x is None else f"{x:.2f} {unit}"

    print("=" * 66)
    print("Lumped-capacitance thermal simulation (illustrative inputs)")
    print("=" * 66)
    print(f"Method                      : {r['method']}, dt = {p.dt_s} s, duration = {p.duration_s} s")
    print(f"Initial temperature         : {r['temperature_C'][0]:.3f} degC")
    print(f"Maximum simulated           : {r['temperature_C'].max():.3f} degC")
    print(f"Final simulated             : {r['temperature_C'][-1]:.3f} degC")
    print(f"Analytical steady state     : {r['T_ss_C']:.3f} degC")
    print(f"Thermal time constant tau   : {r['tau_s']:.2f} s")
    print(f"Duration / tau              : {p.duration_s / r['tau_s']:.2f}")
    print(f"Threshold {r['threshold_C']:.1f} degC (numerical): {fmt(r['t_threshold_num_s'], 's')}")
    print(f"Threshold {r['threshold_C']:.1f} degC (analytic) : {fmt(r['t_threshold_exact_s'], 's')}")
    print(f"Max |numerical - analytical|: {r['max_abs_error_K']:.3e} K")
    e = r["energy"]
    print(f"Energy: in {e['energy_in_J']:.1f} J, out {e['energy_out_J']:.1f} J, "
          f"stored {e['energy_stored_J']:.1f} J, residual {e['residual_J']:.3e} J")
    print("=" * 66)


def save_csv(r: dict, path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["time_s", "temperature_numerical_C", "temperature_analytical_C", "abs_error_K"])
        for t, tn, ta in zip(r["time_s"], r["temperature_C"], r["analytical_C"]):
            w.writerow([f"{t:.6f}", f"{tn:.6f}", f"{ta:.6f}", f"{abs(tn - ta):.3e}"])


def save_plot(r: dict, path: str, show: bool = False) -> None:
    import matplotlib.pyplot as plt

    p = r["params"]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(r["time_s"], r["temperature_C"], lw=2, label=f"Numerical ({r['method']}, dt={p.dt_s:g} s)")
    ax.plot(r["time_s"], r["analytical_C"], "k--", lw=1, label="Analytical")
    ax.axhline(p.ambient_C, color="tab:blue", ls=":", label=f"Ambient ({p.ambient_C:g} °C)")
    ax.axhline(r["T_ss_C"], color="tab:red", ls=":", label=f"Steady state ({r['T_ss_C']:.1f} °C)")
    ax.axhline(r["threshold_C"], color="tab:orange", ls="-.", lw=1, label=f"Threshold ({r['threshold_C']:g} °C)")
    if r["t_threshold_num_s"] is not None:
        ax.plot([r["t_threshold_num_s"]], [r["threshold_C"]], "o", color="tab:orange")
    ax.axvline(r["tau_s"], color="gray", ls=":", lw=0.8)
    ax.text(r["tau_s"], ax.get_ylim()[0], " τ", va="bottom", color="gray")
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Component temperature (°C)")
    ax.set_title("Lumped-capacitance model — illustrative inputs")
    ax.grid(alpha=0.3)
    ax.legend(loc="center right")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    if show:
        plt.show()
    plt.close(fig)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--show", action="store_true", help="display the plot interactively")
    args = ap.parse_args(argv)
    if not args.show:
        matplotlib.use("Agg")  # headless-safe backend

    try:
        result = run(PARAMS, THRESHOLD_C, METHOD)
    except tm.InvalidParameterError as exc:
        print(f"Input error: {exc}", file=sys.stderr)
        return 2

    print_summary(result)
    csv_path = os.path.join(OUTPUT_DIR, "single_run.csv")
    png_path = os.path.join(OUTPUT_DIR, "single_run.png")
    save_csv(result, csv_path)
    save_plot(result, png_path, show=args.show)
    print(f"Saved: {csv_path}\nSaved: {png_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
