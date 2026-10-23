"""Stage 3 systematic parameter studies and engineering validation.

All study values are illustrative unless explicitly identified as sourced.
The two-node physical model itself remains in ``two_node_model.py``.
"""
from __future__ import annotations

import csv
import math
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from two_node_model import (
    TwoNodeParameters,
    analytical_threshold_time,
    analytical_transient,
    eigenvalues,
    simulate,
    steady_state_temperatures,
)

OUT = Path(__file__).parent / "outputs"
OUT.mkdir(exist_ok=True)

THRESHOLD_C = 35.0

# Sourced reference point used only for the engineering applicability check.
# NIST's Al 6061-T6 fitted data at 293.15 K give k ≈ 154.37 W/(m K) and
# cp ≈ 943.13 J/(kg K); density is taken as 2700 kg/m³ from a NASA/UMD
# engineering material-property table. The study does not claim that the
# project wall is actually made from this material.
AL6061_T6_K_293K_W_PER_MK = 154.37
AL6061_T6_DENSITY_KG_PER_M3 = 2700.0


def biot_number(h_W_per_m2K: float, characteristic_length_m: float,
                conductivity_W_per_mK: float) -> float:
    """Return Bi = h Lc / k for a solid lumped-capacitance check."""
    if h_W_per_m2K <= 0 or characteristic_length_m <= 0 or conductivity_W_per_mK <= 0:
        raise ValueError("h, characteristic_length_m and conductivity must all be > 0.")
    return h_W_per_m2K * characteristic_length_m / conductivity_W_per_mK


def wall_biot_check(p: TwoNodeParameters, density_kg_per_m3: float,
                    conductivity_W_per_mK: float) -> dict[str, float]:
    """Estimate wall Bi using Lc = V/A = m/(rho*A_conv)."""
    if density_kg_per_m3 <= 0:
        raise ValueError("density_kg_per_m3 must be > 0.")
    volume_m3 = p.wall_mass_kg / density_kg_per_m3
    characteristic_length_m = volume_m3 / p.convection_area_m2
    bi = biot_number(p.convection_h_W_per_m2K, characteristic_length_m, conductivity_W_per_mK)
    return {
        "volume_m3": volume_m3,
        "characteristic_length_m": characteristic_length_m,
        "Bi": bi,
    }

BASE = TwoNodeParameters(
    heat_generation_W=5.0,
    component_mass_kg=0.05,
    component_specific_heat_J_per_kgK=900.0,
    wall_mass_kg=0.20,
    wall_specific_heat_J_per_kgK=900.0,
    conduction_thickness_m=0.002,
    conduction_conductivity_W_per_mK=10.0,
    conduction_area_m2=0.01,
    convection_h_W_per_m2K=10.0,
    convection_area_m2=0.03,
    ambient_C=25.0,
    initial_component_C=25.0,
    initial_wall_C=25.0,
    duration_s=3000.0,
    dt_s=0.5,
)

# Reproducible study grids. Values are deliberately simple engineering ranges,
# not claimed operating limits for a real product.
STUDIES = {
    "heat_generation": ("heat_generation_W", [1.0, 2.5, 5.0, 7.5, 10.0]),
    "ambient_temperature": ("ambient_C", [15.0, 25.0, 35.0, 45.0, 55.0]),
    "conduction_resistance": ("conduction_thickness_m", [0.0005, 0.001, 0.002, 0.004, 0.008]),
    "convection_coefficient": ("convection_h_W_per_m2K", [5.0, 10.0, 20.0, 40.0, 80.0]),
    "convection_area": ("convection_area_m2", [0.015, 0.0225, 0.03, 0.06, 0.09]),
    "component_capacitance": ("component_mass_kg", [0.025, 0.05, 0.10, 0.20]),
    "wall_capacitance": ("wall_mass_kg", [0.10, 0.20, 0.40, 0.80]),
    "conduction_conductivity": ("conduction_conductivity_W_per_mK", [5.0, 10.0, 25.0, 50.0, 155.0]),
}


def numerical_parameters(p: TwoNodeParameters) -> TwoNodeParameters:
    """Choose a conservative RK4 step for study cases with fast modes."""
    lam_max = float(np.max(np.abs(eigenvalues(p))))
    safe_dt = 0.25 / lam_max if lam_max > 0.0 else p.dt_s
    return p.with_changes(dt_s=min(p.dt_s, safe_dt))


def run_case(p: TwoNodeParameters, *, numerical: bool = False) -> dict:
    ss_c, ss_w = steady_state_temperatures(p)
    threshold = analytical_threshold_time(p, THRESHOLD_C)
    result = None
    max_err_c = max_err_w = math.nan
    if numerical:
        p_num = numerical_parameters(p)
        result = simulate(p_num, "rk4")
        exact = analytical_transient(p, result["time_s"])
        max_err_c = float(np.max(np.abs(result["component_C"] - exact["component_C"])))
        max_err_w = float(np.max(np.abs(result["wall_C"] - exact["wall_C"])))
    return {
        "params": p,
        "component_ss_C": ss_c,
        "wall_ss_C": ss_w,
        "threshold_s": threshold,
        "result": result,
        "max_error_component_K": max_err_c,
        "max_error_wall_K": max_err_w,
    }


def build_study_rows(study_name: str, field: str, values: list[float]) -> list[dict]:
    rows = []
    for value in values:
        # Each ambient-temperature case starts at its own ambient value so the
        # transient represents heating from equilibrium rather than an imposed
        # initial-temperature mismatch.
        changes = {field: value}
        if field == "ambient_C":
            changes["initial_component_C"] = value
            changes["initial_wall_C"] = value
        p = BASE.with_changes(**changes)
        r = run_case(p)
        rows.append({
            "study": study_name,
            "parameter": field,
            "value": value,
            "unit": _unit(field),
            "R_cond_K_per_W": p.R_cond_K_per_W,
            "R_conv_K_per_W": p.R_conv_K_per_W,
            "component_capacitance_J_per_K": p.component_capacitance_J_per_K,
            "wall_capacitance_J_per_K": p.wall_capacitance_J_per_K,
            "component_ss_C": r["component_ss_C"],
            "wall_ss_C": r["wall_ss_C"],
            "threshold_35C_s": "" if r["threshold_s"] is None else r["threshold_s"],
        })
    return rows


def _unit(field: str) -> str:
    return {
        "heat_generation_W": "W",
        "ambient_C": "degC",
        "conduction_thickness_m": "m",
        "convection_h_W_per_m2K": "W/(m^2 K)",
        "convection_area_m2": "m^2",
        "component_mass_kg": "kg",
        "wall_mass_kg": "kg",
        "conduction_conductivity_W_per_mK": "W/(m K)",
    }[field]


def save_summary(rows: list[dict], path: Path) -> None:
    fields = [
        "study", "parameter", "value", "unit", "R_cond_K_per_W", "R_conv_K_per_W",
        "component_capacitance_J_per_K", "wall_capacitance_J_per_K",
        "component_ss_C", "wall_ss_C", "threshold_35C_s",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def plot_steady_state(rows: list[dict]) -> None:
    names = list(STUDIES)
    fig, axes = plt.subplots(4, 2, figsize=(11, 15))
    for ax, name in zip(axes.flat, names):
        subset = [r for r in rows if r["study"] == name]
        x = [r["value"] for r in subset]
        ax.plot(x, [r["component_ss_C"] for r in subset], marker="o", label="Component")
        ax.plot(x, [r["wall_ss_C"] for r in subset], marker="s", label="Wall")
        ax.set_title(name.replace("_", " ").title())
        ax.set_xlabel(f"{_unit(subset[0]['parameter'])}: {subset[0]['parameter']}")
        ax.set_ylabel("Steady-state temperature [°C]")
        ax.grid(True, alpha=0.25)
        ax.legend(fontsize=8)
    fig.suptitle("Stage 3 — Steady-State Parameter Sensitivity", y=0.995)
    fig.tight_layout()
    fig.savefig(OUT / "stage3_steady_state_sensitivity.png", dpi=160)
    plt.close(fig)


def plot_threshold(rows: list[dict]) -> None:
    fig, axes = plt.subplots(4, 2, figsize=(11, 15))
    for ax, name in zip(axes.flat, STUDIES):
        subset = [r for r in rows if r["study"] == name and r["threshold_35C_s"] != ""]
        if subset:
            ax.plot([r["value"] for r in subset], [r["threshold_35C_s"] for r in subset], marker="o")
        else:
            ax.text(0.5, 0.5, "35 °C not reached", ha="center", va="center", transform=ax.transAxes)
        ax.set_title(name.replace("_", " ").title())
        ax.set_xlabel(f"{_unit(STUDIES[name][0])}: {STUDIES[name][0]}")
        ax.set_ylabel("Time to component 35 °C [s]")
        ax.grid(True, alpha=0.25)
    fig.suptitle("Stage 3 — Threshold-Time Sensitivity", y=0.995)
    fig.tight_layout()
    fig.savefig(OUT / "stage3_threshold_sensitivity.png", dpi=160)
    plt.close(fig)


def plot_selected_transients() -> None:
    selections = [
        ("heat generation", [BASE.with_changes(heat_generation_W=q) for q in (2.5, 5.0, 7.5)]),
        ("conduction resistance", [BASE.with_changes(conduction_thickness_m=L) for L in (0.0005, 0.002, 0.008)]),
        ("convection coefficient", [BASE.with_changes(convection_h_W_per_m2K=h) for h in (5.0, 10.0, 40.0)]),
        ("component capacitance", [BASE.with_changes(component_mass_kg=m) for m in (0.025, 0.05, 0.20)]),
    ]
    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    for ax, (title, params) in zip(axes.flat, selections):
        for p in params:
            r = simulate(numerical_parameters(p), "rk4")
            label = {
                "heat generation": f"Q={p.heat_generation_W:g} W",
                "conduction resistance": f"Rcond={p.R_cond_K_per_W:g} K/W",
                "convection coefficient": f"h={p.convection_h_W_per_m2K:g} W/m²K",
                "component capacitance": f"Cc={p.component_capacitance_J_per_K:g} J/K",
            }[title]
            ax.plot(r["time_s"], r["component_C"], label=label)
        ax.set_title(title.title())
        ax.set_xlabel("Time [s]")
        ax.set_ylabel("Component temperature [°C]")
        ax.grid(True, alpha=0.25)
        ax.legend(fontsize=8)
    fig.suptitle("Stage 3 — Selected Transient Responses", y=0.995)
    fig.tight_layout()
    fig.savefig(OUT / "stage3_transient_comparisons.png", dpi=160)
    plt.close(fig)


def plot_material_conductivity() -> None:
    values = [5.0, 10.0, 25.0, 50.0, 155.0]
    fig, ax = plt.subplots(figsize=(8, 5))
    for k in values:
        p = BASE.with_changes(conduction_conductivity_W_per_mK=k)
        r = simulate(numerical_parameters(p), "rk4")
        label = "Al 6061-T6 (~155 W/mK at 293 K)" if k == 155.0 else f"k={k:g} W/mK (illustrative)"
        ax.plot(r["time_s"], r["component_C"], label=label)
    ax.set_xlabel("Time [s]")
    ax.set_ylabel("Component temperature [°C]")
    ax.set_title("Effect of Conduction Material Conductivity")
    ax.grid(True, alpha=0.25)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT / "stage3_material_conductivity.png", dpi=160)
    plt.close(fig)


def standard_atmosphere_troposphere(altitude_m: float) -> tuple[float, float, float]:
    """Return standard-atmosphere temperature [C], pressure [Pa], density [kg/m3].

    Valid here for 0 <= altitude <= 11 km, using the 1976 standard-atmosphere
    tropospheric lapse-rate equations. This is an environmental scenario, not
    a prediction of actual local weather.
    """
    if not math.isfinite(altitude_m) or not 0.0 <= altitude_m <= 11_000.0:
        raise ValueError("altitude_m must be finite and between 0 and 11000 m for this function.")
    T0 = 288.15
    P0 = 101325.0
    R = 287.05287
    g = 9.80665
    lapse = 0.0065
    T = T0 - lapse * altitude_m
    P = P0 * (T / T0) ** (g / (R * lapse))
    rho = P / (R * T)
    return T - 273.15, P, rho


def high_altitude_study() -> list[dict]:
    """Illustrative altitude study with fixed speed/geometry scaling of h.

    For a forced-convection scenario, h is scaled as sqrt(rho/rho0), holding
    the representative velocity, geometry and other correlation factors fixed.
    This is an explicit modelling assumption, not a universal altitude law.
    """
    rho0 = standard_atmosphere_troposphere(0.0)[2]
    rows = []
    for altitude in (0.0, 5000.0, 10000.0):
        ambient, pressure, rho = standard_atmosphere_troposphere(altitude)
        h = BASE.convection_h_W_per_m2K * math.sqrt(rho / rho0)
        p = BASE.with_changes(
            ambient_C=ambient,
            initial_component_C=ambient,
            initial_wall_C=ambient,
            convection_h_W_per_m2K=h,
        )
        r = run_case(p)
        rows.append({
            "altitude_m": altitude,
            "ambient_C": ambient,
            "pressure_Pa": pressure,
            "density_kg_per_m3": rho,
            "assumed_h_W_per_m2K": h,
            "R_conv_K_per_W": p.R_conv_K_per_W,
            "component_ss_C": r["component_ss_C"],
            "wall_ss_C": r["wall_ss_C"],
            "threshold_35C_s": "" if r["threshold_s"] is None else r["threshold_s"],
        })
    return rows


def save_altitude(rows: list[dict]) -> None:
    path = OUT / "stage3_high_altitude.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        fields = list(rows[0])
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def plot_altitude(rows: list[dict]) -> None:
    fig, ax = plt.subplots(figsize=(8, 5))
    x = [r["altitude_m"] / 1000 for r in rows]
    ax.plot(x, [r["component_ss_C"] for r in rows], marker="o", label="Component")
    ax.plot(x, [r["wall_ss_C"] for r in rows], marker="s", label="Wall")
    ax.set_xlabel("Altitude [km]")
    ax.set_ylabel("Steady-state temperature [°C]")
    ax.set_title("Illustrative High-Altitude Environmental Scenario")
    ax.grid(True, alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(OUT / "stage3_high_altitude.png", dpi=160)
    plt.close(fig)


def main() -> None:
    all_rows: list[dict] = []
    for study_name, (field, values) in STUDIES.items():
        all_rows.extend(build_study_rows(study_name, field, values))
    save_summary(all_rows, OUT / "stage3_parameter_summary.csv")
    plot_steady_state(all_rows)
    plot_threshold(all_rows)
    plot_selected_transients()
    plot_material_conductivity()

    altitude_rows = high_altitude_study()
    save_altitude(altitude_rows)
    plot_altitude(altitude_rows)

    bi = wall_biot_check(BASE, AL6061_T6_DENSITY_KG_PER_M3, AL6061_T6_K_293K_W_PER_MK)
    with (OUT / "stage3_biot_check.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["material", "density_kg_per_m3", "k_W_per_mK", "h_W_per_m2K",
                     "convection_area_m2", "wall_mass_kg", "characteristic_length_m", "Bi"])
        w.writerow(["Al 6061-T6 reference", AL6061_T6_DENSITY_KG_PER_M3,
                    AL6061_T6_K_293K_W_PER_MK, BASE.convection_h_W_per_m2K,
                    BASE.convection_area_m2, BASE.wall_mass_kg,
                    bi["characteristic_length_m"], bi["Bi"]])

    # Numerical verification of representative study endpoints against the
    # independent analytical benchmark.
    verification = []
    for study_name, (field, values) in STUDIES.items():
        for value in (values[0], values[-1]):
            changes = {field: value}
            if field == "ambient_C":
                changes["initial_component_C"] = value
                changes["initial_wall_C"] = value
            p = BASE.with_changes(**changes)
            r = run_case(p, numerical=True)
            verification.append((study_name, value, r["max_error_component_K"], r["max_error_wall_K"]))
    with (OUT / "stage3_numerical_verification.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["study", "endpoint_value", "max_component_error_K", "max_wall_error_K"])
        w.writerows(verification)

    print("Stage 3 parameter studies complete")
    print(f"Summary rows: {len(all_rows)}")
    print(f"Outputs: {OUT}")
    print("Representative numerical-vs-analytical endpoint errors:")
    print(f"  max component = {max(v[2] for v in verification):.3e} K")
    print(f"  max wall      = {max(v[3] for v in verification):.3e} K")
    print(f"Wall Biot check (Al 6061-T6 reference): Bi = {bi['Bi']:.3e}, Lc = {bi['characteristic_length_m']:.6g} m")
    print("High-altitude scenarios:")
    for row in altitude_rows:
        print(
            f"  {row['altitude_m']/1000:.1f} km: Tinf={row['ambient_C']:.2f} °C, "
            f"rho={row['density_kg_per_m3']:.4f} kg/m³, h={row['assumed_h_W_per_m2K']:.3f} W/(m²K), "
            f"Tc,ss={row['component_ss_C']:.3f} °C"
        )


if __name__ == "__main__":
    main()
