"""Pure-logic tests for the Stage 4 dashboard adapters."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import dashboard_logic as dl


def test_single_node_uses_existing_model_and_returns_analytical_comparison():
    r = dl.run_model("Single-node", {
        "heat_generation_W": 5.0,
        "mass_kg": 0.05,
        "specific_heat_J_per_kgK": 900.0,
        "area_m2": 0.01,
        "h_W_per_m2K": 10.0,
        "ambient_C": 25.0,
        "initial_C": 25.0,
        "duration_s": 300.0,
        "dt_s": 1.0,
    }, 60.0)
    assert r["component_ss_C"] == pytest.approx(75.0)
    assert r["max_error_component_K"] < 1e-9
    assert r["wall_C"] is None


def test_two_node_uses_stage3_conservative_step_and_returns_wall():
    r = dl.run_model("Two-node", {
        "heat_generation_W": 5.0,
        "component_mass_kg": 0.05,
        "component_specific_heat_J_per_kgK": 900.0,
        "wall_mass_kg": 0.20,
        "wall_specific_heat_J_per_kgK": 900.0,
        "conduction_thickness_m": 0.002,
        "conduction_conductivity_W_per_mK": 10.0,
        "conduction_area_m2": 0.01,
        "convection_h_W_per_m2K": 10.0,
        "convection_area_m2": 0.03,
        "ambient_C": 25.0,
        "initial_component_C": 25.0,
        "initial_wall_C": 25.0,
        "duration_s": 300.0,
        "dt_s": 0.5,
    }, 35.0)
    assert r["component_ss_C"] == pytest.approx(41.7666666667)
    assert r["wall_ss_C"] == pytest.approx(41.6666666667)
    assert r["wall_C"] is not None
    assert r["max_error_component_K"] < 1e-5


def test_invalid_inputs_are_rejected_with_model_message():
    values = {
        "heat_generation_W": 5.0,
        "mass_kg": 0.05,
        "specific_heat_J_per_kgK": 900.0,
        "area_m2": 0.01,
        "h_W_per_m2K": 10.0,
        "ambient_C": 25.0,
        "initial_C": 25.0,
        "duration_s": 10.0,
        "dt_s": 20.0,
    }
    with pytest.raises(ValueError, match="must not exceed duration"):
        dl.validate_single_inputs(values, 60.0)


def test_timeseries_export_contains_actual_calculated_columns():
    r = dl.run_model("Single-node", {
        "heat_generation_W": 5.0,
        "mass_kg": 0.05,
        "specific_heat_J_per_kgK": 900.0,
        "area_m2": 0.01,
        "h_W_per_m2K": 10.0,
        "ambient_C": 25.0,
        "initial_C": 25.0,
        "duration_s": 10.0,
        "dt_s": 1.0,
    }, 60.0)
    df = dl.current_timeseries_dataframe(r)
    assert isinstance(df, pd.DataFrame)
    assert list(df.columns)[:3] == ["time_s", "component_temperature_C", "component_analytical_C"]
    assert df.iloc[-1]["time_s"] == pytest.approx(10.0)
    assert df.iloc[-1]["component_temperature_C"] > 25.0


def test_scenario_comparison_changes_results_as_expected():
    base = dl.run_model("Two-node", {
        "heat_generation_W": 5.0,
        "component_mass_kg": 0.05,
        "component_specific_heat_J_per_kgK": 900.0,
        "wall_mass_kg": 0.20,
        "wall_specific_heat_J_per_kgK": 900.0,
        "conduction_thickness_m": 0.002,
        "conduction_conductivity_W_per_mK": 10.0,
        "conduction_area_m2": 0.01,
        "convection_h_W_per_m2K": 10.0,
        "convection_area_m2": 0.03,
        "ambient_C": 25.0,
        "initial_component_C": 25.0,
        "initial_wall_C": 25.0,
        "duration_s": 300.0,
        "dt_s": 0.5,
    }, 35.0)
    high_q_values = dict(base["params"].__dict__)
    high_q_values["heat_generation_W"] = 7.5
    high_q = dl.run_model("Two-node", high_q_values, 35.0)
    base["scenario"] = "Baseline"
    high_q["scenario"] = "High Q"
    df = dl.scenario_comparison_dataframe([base, high_q])
    assert df.iloc[1]["component_steady_state_C"] > df.iloc[0]["component_steady_state_C"]
    assert df.iloc[1]["wall_steady_state_C"] > df.iloc[0]["wall_steady_state_C"]


def test_parameter_summary_includes_derived_resistances():
    r = dl.run_model("Two-node", {
        "heat_generation_W": 5.0,
        "component_mass_kg": 0.05,
        "component_specific_heat_J_per_kgK": 900.0,
        "wall_mass_kg": 0.20,
        "wall_specific_heat_J_per_kgK": 900.0,
        "conduction_thickness_m": 0.002,
        "conduction_conductivity_W_per_mK": 10.0,
        "conduction_area_m2": 0.01,
        "convection_h_W_per_m2K": 10.0,
        "convection_area_m2": 0.03,
        "ambient_C": 25.0,
        "initial_component_C": 25.0,
        "initial_wall_C": 25.0,
        "duration_s": 10.0,
        "dt_s": 0.5,
    }, 35.0)
    df = dl.parameter_summary_dataframe(r)
    assert "R_cond_K_per_W" in set(df["parameter"])
    assert "R_conv_K_per_W" in set(df["parameter"])
    assert np.isclose(df.loc[df["parameter"] == "R_cond_K_per_W", "value"].iloc[0], 0.02)
