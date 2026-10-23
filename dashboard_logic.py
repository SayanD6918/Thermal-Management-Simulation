"""Pure dashboard helpers for the Stage 4 Streamlit UI.

This module deliberately contains no Streamlit calls and no duplicate thermal
physics. It adapts the existing Stage 1/2 model APIs for validation, result
preparation, scenario comparison, and export formatting.
"""
from __future__ import annotations

import io
import math
from dataclasses import asdict
from typing import Any

import numpy as np
import pandas as pd

import thermal_model as tm
from stage3_parameter_studies import BASE as TWO_NODE_BASE
from stage3_parameter_studies import numerical_parameters
from two_node_model import (
    InvalidParameterError as TwoNodeInvalidParameterError,
    TwoNodeParameters,
    analytical_transient,
    analytical_threshold_time,
    eigenvalues,
    simulate as simulate_two_node,
    steady_state_temperatures,
    time_to_threshold as two_node_time_to_threshold,
    total_energy_balance,
)

SINGLE_NODE_DEFAULT = tm.ThermalParameters(
    heat_generation_W=5.0,
    mass_kg=0.05,
    specific_heat_J_per_kgK=900.0,
    area_m2=0.01,
    h_W_per_m2K=10.0,
    ambient_C=25.0,
    initial_C=25.0,
    duration_s=3000.0,
    dt_s=1.0,
)
SINGLE_THRESHOLD_DEFAULT = 60.0
TWO_NODE_THRESHOLD_DEFAULT = 35.0
STEADY_STATE_TOLERANCE_K = 0.1

EXAMPLE_SCENARIOS: dict[str, dict[str, Any]] = {
    "Validated baseline": {},
    "High heat generation": {"heat_generation_W": 7.5},
    "Strong convection": {"convection_h_W_per_m2K": 40.0},
    "High conduction resistance": {"conduction_thickness_m": 0.008},
    "Cool ambient": {"ambient_C": 15.0, "initial_component_C": 15.0, "initial_wall_C": 15.0},
}


def _validate_threshold(threshold_C: float) -> None:
    if not isinstance(threshold_C, (int, float, np.integer, np.floating)) or not math.isfinite(float(threshold_C)):
        raise ValueError("Temperature threshold must be a finite number.")
    if threshold_C <= tm.ABSOLUTE_ZERO_C:
        raise ValueError("Temperature threshold must be above absolute zero (-273.15 °C).")


def validate_single_inputs(values: dict[str, float], threshold_C: float) -> tm.ThermalParameters:
    _validate_threshold(threshold_C)
    try:
        p = tm.ThermalParameters(**values)
        tm.validate_parameters(p)
        return p
    except (TypeError, tm.InvalidParameterError, ValueError) as exc:
        raise ValueError(str(exc)) from exc


def validate_two_node_inputs(values: dict[str, float], threshold_C: float) -> TwoNodeParameters:
    _validate_threshold(threshold_C)
    try:
        p = TwoNodeParameters(**values)
        # Use the model's own validation and derived resistances.
        p.with_changes()
        return p
    except (TypeError, TwoNodeInvalidParameterError, ValueError) as exc:
        raise ValueError(str(exc)) from exc


def run_single_node(p: tm.ThermalParameters, threshold_C: float) -> dict[str, Any]:
    sim = tm.simulate(p, method="rk4")
    t = sim["time_s"]
    temp = sim["temperature_C"]
    analytical = tm.analytical_temperature(p, t)
    return {
        "mode": "Single-node",
        "params": p,
        "time_s": t,
        "component_C": temp,
        "analytical_component_C": analytical,
        "wall_C": None,
        "analytical_wall_C": None,
        "ambient_C": p.ambient_C,
        "threshold_C": threshold_C,
        "component_ss_C": tm.steady_state_temperature(p),
        "wall_ss_C": None,
        "time_constant_s": tm.time_constant(p),
        "fast_time_constant_s": None,
        "threshold_num_s": tm.time_to_threshold(t, temp, threshold_C),
        "threshold_analytical_s": tm.analytical_time_to_temperature(p, threshold_C),
        "max_error_component_K": float(np.max(np.abs(temp - analytical))),
        "energy": tm.energy_balance_residual(p, t, temp),
        "reached_steady_state": bool(abs(temp[-1] - tm.steady_state_temperature(p)) <= STEADY_STATE_TOLERANCE_K),
    }


def run_two_node(p: TwoNodeParameters, threshold_C: float) -> dict[str, Any]:
    # Stage 3 already contains the conservative step selection needed for
    # high-conductivity / low-capacitance cases. The dashboard reuses it.
    p_num = numerical_parameters(p)
    sim = simulate_two_node(p_num, method="rk4")
    t = sim["time_s"]
    tc = sim["component_C"]
    tw = sim["wall_C"]
    analytical = analytical_transient(p_num, t)
    ss_c, ss_w = steady_state_temperatures(p_num)
    eig = eigenvalues(p_num)
    tau_fast = -1.0 / float(np.min(eig))
    tau_slow = -1.0 / float(np.max(eig))
    return {
        "mode": "Two-node",
        "params": p_num,
        "time_s": t,
        "component_C": tc,
        "analytical_component_C": analytical["component_C"],
        "wall_C": tw,
        "analytical_wall_C": analytical["wall_C"],
        "ambient_C": p_num.ambient_C,
        "threshold_C": threshold_C,
        "component_ss_C": ss_c,
        "wall_ss_C": ss_w,
        "time_constant_s": tau_slow,
        "fast_time_constant_s": tau_fast,
        "threshold_num_s": two_node_time_to_threshold(t, tc, threshold_C),
        "threshold_analytical_s": analytical_threshold_time(p_num, threshold_C),
        "max_error_component_K": float(np.max(np.abs(tc - analytical["component_C"]))),
        "max_error_wall_K": float(np.max(np.abs(tw - analytical["wall_C"]))),
        "energy": total_energy_balance(p_num, sim),
        "reached_steady_state": bool(
            max(abs(tc[-1] - ss_c), abs(tw[-1] - ss_w)) <= STEADY_STATE_TOLERANCE_K
        ),
    }


def run_model(mode: str, values: dict[str, float], threshold_C: float) -> dict[str, Any]:
    if mode == "Single-node":
        return run_single_node(validate_single_inputs(values, threshold_C), threshold_C)
    if mode == "Two-node":
        return run_two_node(validate_two_node_inputs(values, threshold_C), threshold_C)
    raise ValueError(f"Unknown model mode: {mode!r}")


def current_timeseries_dataframe(result: dict[str, Any]) -> pd.DataFrame:
    data: dict[str, Any] = {
        "time_s": result["time_s"],
        "component_temperature_C": result["component_C"],
        "component_analytical_C": result["analytical_component_C"],
        "ambient_C": np.full_like(result["time_s"], result["ambient_C"], dtype=float),
        "threshold_C": np.full_like(result["time_s"], result["threshold_C"], dtype=float),
    }
    if result["wall_C"] is not None:
        data["wall_temperature_C"] = result["wall_C"]
        data["wall_analytical_C"] = result["analytical_wall_C"]
    return pd.DataFrame(data)


def parameter_summary_dataframe(result: dict[str, Any]) -> pd.DataFrame:
    p = result["params"]
    rows: list[tuple[str, Any, str]] = []
    for name, value in asdict(p).items():
        unit = _PARAMETER_UNITS.get(name, "")
        rows.append((name, value, unit))
    derived = [
        ("component_capacitance_J_per_K", getattr(p, "heat_capacity_J_per_K", getattr(p, "component_capacitance_J_per_K", None)), "J/K"),
        ("R_cond_K_per_W", getattr(p, "R_cond_K_per_W", None), "K/W"),
        ("R_conv_K_per_W", getattr(p, "R_conv_K_per_W", None), "K/W"),
    ]
    for name, value, unit in derived:
        if value is not None:
            rows.append((name, value, unit))
    if result["wall_C"] is not None:
        rows.append(("wall_capacitance_J_per_K", p.wall_capacitance_J_per_K, "J/K"))
    return pd.DataFrame(rows, columns=["parameter", "value", "unit"])


_PARAMETER_UNITS = {
    "heat_generation_W": "W",
    "mass_kg": "kg",
    "component_mass_kg": "kg",
    "specific_heat_J_per_kgK": "J/(kg K)",
    "component_specific_heat_J_per_kgK": "J/(kg K)",
    "wall_mass_kg": "kg",
    "wall_specific_heat_J_per_kgK": "J/(kg K)",
    "area_m2": "m²",
    "conduction_thickness_m": "m",
    "conduction_conductivity_W_per_mK": "W/(m K)",
    "conduction_area_m2": "m²",
    "convection_h_W_per_m2K": "W/(m² K)",
    "convection_area_m2": "m²",
    "ambient_C": "°C",
    "initial_C": "°C",
    "initial_component_C": "°C",
    "initial_wall_C": "°C",
    "duration_s": "s",
    "dt_s": "s",
}


def scenario_comparison_dataframe(results: list[dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for r in results:
        p = r["params"]
        rows.append({
            "scenario": r.get("scenario", "Scenario"),
            "mode": r["mode"],
            "heat_generation_W": p.heat_generation_W,
            "ambient_C": p.ambient_C,
            "R_cond_K_per_W": getattr(p, "R_cond_K_per_W", np.nan),
            "R_conv_K_per_W": p.R_conv_K_per_W if hasattr(p, "R_conv_K_per_W") else 1.0 / p.conductance_W_per_K,
            "component_capacitance_J_per_K": p.component_capacitance_J_per_K if hasattr(p, "component_capacitance_J_per_K") else p.heat_capacity_J_per_K,
            "wall_capacitance_J_per_K": getattr(p, "wall_capacitance_J_per_K", np.nan),
            "component_final_C": r["component_C"][-1],
            "wall_final_C": np.nan if r["wall_C"] is None else r["wall_C"][-1],
            "component_steady_state_C": r["component_ss_C"],
            "wall_steady_state_C": np.nan if r["wall_ss_C"] is None else r["wall_ss_C"],
            "component_max_C": float(np.max(r["component_C"])),
            "threshold_time_s": r["threshold_num_s"],
            "steady_state_within_0.1K": r["reached_steady_state"],
        })
    return pd.DataFrame(rows)


def apply_example(mode: str, example_name: str, base_values: dict[str, float]) -> dict[str, float]:
    if example_name == "Validated baseline":
        return dict(base_values)
    changes = EXAMPLE_SCENARIOS.get(example_name, {})
    if mode == "Single-node":
        # Example scenarios are defined for the two-node baseline. Map the
        # compatible heat/ambient examples to the single-node inputs.
        out = dict(base_values)
        if "heat_generation_W" in changes:
            out["heat_generation_W"] = changes["heat_generation_W"]
        if "ambient_C" in changes:
            out["ambient_C"] = changes["ambient_C"]
            out["initial_C"] = changes.get("initial_C", changes["ambient_C"])
        return out
    out = dict(base_values)
    out.update(changes)
    return out


def make_download_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")


def make_summary_text(result: dict[str, Any]) -> str:
    p = result["params"]
    lines = [
        "Thermal Management — Streamlit Simulation Summary",
        "=" * 56,
        f"Model: {result['mode']}",
        f"Heat generation: {p.heat_generation_W:.6g} W",
        f"Ambient: {p.ambient_C:.6g} °C",
        f"Initial component: {(p.initial_C if result['mode'] == 'Single-node' else p.initial_component_C):.6g} °C",
        f"Duration: {p.duration_s:.6g} s",
        f"Numerical time step: {p.dt_s:.6g} s",
        f"Component final: {result['component_C'][-1]:.6f} °C",
        f"Component maximum: {np.max(result['component_C']):.6f} °C",
        f"Component analytical steady state: {result['component_ss_C']:.6f} °C",
        f"Steady-state criterion (±{STEADY_STATE_TOLERANCE_K:g} K): {'met' if result['reached_steady_state'] else 'not met'}",
        f"Component threshold: {result['threshold_C']:.6f} °C",
        f"Component threshold crossing: {_fmt_seconds(result['threshold_num_s'])}",
        f"Analytical threshold crossing: {_fmt_seconds(result['threshold_analytical_s'])}",
        "",
        "Assumptions: lumped thermal nodes, constant parameters during the run,",
        "no radiation, no CFD/FEM, no experimental validation, and illustrative",
        "parameters unless explicitly identified as sourced reference data.",
    ]
    if result["mode"] == "Two-node":
        lines.extend([
            f"Wall final: {result['wall_C'][-1]:.6f} °C",
            f"Wall analytical steady state: {result['wall_ss_C']:.6f} °C",
            f"Slow thermal time constant: {result['time_constant_s']:.6f} s",
            f"Fast thermal time constant: {result['fast_time_constant_s']:.6f} s",
            f"R_cond: {p.R_cond_K_per_W:.6g} K/W",
            f"R_conv: {p.R_conv_K_per_W:.6g} K/W",
        ])
    else:
        lines.append(f"Thermal time constant: {result['time_constant_s']:.6f} s")
    return "\n".join(lines) + "\n"


def _fmt_seconds(value: float | None) -> str:
    return "not reached during simulation" if value is None else f"{value:.3f} s"
