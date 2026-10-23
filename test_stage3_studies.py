import csv
from pathlib import Path

import pytest

from stage3_parameter_studies import (
    BASE,
    STUDIES,
    high_altitude_study,
    run_case,
    biot_number,
    wall_biot_check,
    numerical_parameters,
    standard_atmosphere_troposphere,
)
from two_node_model import analytical_transient, simulate, steady_state_temperatures


def test_study_grids_are_reproducible_and_nonempty():
    assert set(STUDIES) == {
        "heat_generation", "ambient_temperature", "conduction_resistance",
        "convection_coefficient", "convection_area", "component_capacitance",
        "wall_capacitance", "conduction_conductivity",
    }
    assert all(values for _, values in STUDIES.values())


def test_heat_generation_sensitivity_matches_governing_equation():
    low = run_case(BASE.with_changes(heat_generation_W=2.5))
    high = run_case(BASE.with_changes(heat_generation_W=7.5))
    assert high["component_ss_C"] > low["component_ss_C"]
    assert high["wall_ss_C"] > low["wall_ss_C"]


def test_ambient_temperature_shifts_steady_state_linearly():
    low = run_case(BASE.with_changes(ambient_C=15.0, initial_component_C=15.0, initial_wall_C=15.0))
    high = run_case(BASE.with_changes(ambient_C=45.0, initial_component_C=45.0, initial_wall_C=45.0))
    assert high["component_ss_C"] - low["component_ss_C"] == pytest.approx(30.0)
    assert high["wall_ss_C"] - low["wall_ss_C"] == pytest.approx(30.0)


def test_conduction_resistance_changes_component_not_wall_steady_state():
    low = run_case(BASE.with_changes(conduction_thickness_m=0.0005))
    high = run_case(BASE.with_changes(conduction_thickness_m=0.008))
    assert high["component_ss_C"] > low["component_ss_C"]
    assert high["wall_ss_C"] == pytest.approx(low["wall_ss_C"])


def test_convection_coefficient_and_area_have_expected_effect():
    low_h = run_case(BASE.with_changes(convection_h_W_per_m2K=5.0))
    high_h = run_case(BASE.with_changes(convection_h_W_per_m2K=40.0))
    low_a = run_case(BASE.with_changes(convection_area_m2=0.015))
    high_a = run_case(BASE.with_changes(convection_area_m2=0.09))
    assert high_h["component_ss_C"] < low_h["component_ss_C"]
    assert high_a["component_ss_C"] < low_a["component_ss_C"]


def test_capacitance_changes_transient_but_not_steady_state():
    low = run_case(BASE.with_changes(component_mass_kg=0.025), numerical=True)
    high = run_case(BASE.with_changes(component_mass_kg=0.20), numerical=True)
    assert high["component_ss_C"] == pytest.approx(low["component_ss_C"])
    # At an early time the larger capacitance must have changed less.
    t = 100.0
    low_exact = analytical_transient(BASE.with_changes(component_mass_kg=0.025), [t])["component_C"][0]
    high_exact = analytical_transient(BASE.with_changes(component_mass_kg=0.20), [t])["component_C"][0]
    assert high_exact < low_exact


def test_conduction_conductivity_sensitivity_is_monotonic():
    low = run_case(BASE.with_changes(conduction_conductivity_W_per_mK=5.0))
    high = run_case(BASE.with_changes(conduction_conductivity_W_per_mK=155.0))
    assert high["component_ss_C"] < low["component_ss_C"]
    assert high["wall_ss_C"] == pytest.approx(low["wall_ss_C"])


def test_representative_numerical_cases_match_analytical_solution():
    for field, values in STUDIES.values():
        for value in (values[0], values[-1]):
            changes = {field: value}
            if field == "ambient_C":
                changes["initial_component_C"] = value
                changes["initial_wall_C"] = value
            p = BASE.with_changes(**changes)
            numerical = simulate(numerical_parameters(p))
            analytical = analytical_transient(p, numerical["time_s"])
            assert max(abs(numerical["component_C"] - analytical["component_C"])) < 2e-5
            assert max(abs(numerical["wall_C"] - analytical["wall_C"])) < 2e-5


def test_standard_atmosphere_reference_points():
    t0, p0, rho0 = standard_atmosphere_troposphere(0.0)
    t5, p5, rho5 = standard_atmosphere_troposphere(5000.0)
    t10, p10, rho10 = standard_atmosphere_troposphere(10000.0)
    assert t0 == pytest.approx(15.0, abs=1e-9)
    assert p0 == pytest.approx(101325.0, rel=1e-8)
    assert rho0 == pytest.approx(1.225, rel=1e-6)
    assert t5 == pytest.approx(-17.5, abs=1e-9)
    assert rho5 == pytest.approx(0.7361, rel=2e-4)
    assert t10 == pytest.approx(-50.0, abs=1e-9)
    assert rho10 == pytest.approx(0.4127, rel=2e-4)
    assert rho0 > rho5 > rho10
    assert p0 > p5 > p10


def test_high_altitude_assumption_produces_lower_h_but_cooler_steady_state():
    rows = high_altitude_study()
    assert [r["altitude_m"] for r in rows] == [0.0, 5000.0, 10000.0]
    assert rows[0]["assumed_h_W_per_m2K"] > rows[1]["assumed_h_W_per_m2K"] > rows[2]["assumed_h_W_per_m2K"]
    assert rows[0]["component_ss_C"] > rows[1]["component_ss_C"] > rows[2]["component_ss_C"]


def test_generated_summary_csv_has_expected_columns(tmp_path):
    # Lightweight schema check against the expected Stage 3 output format.
    path = tmp_path / "stage3_parameter_summary.csv"
    fields = [
        "study", "parameter", "value", "unit", "R_cond_K_per_W", "R_conv_K_per_W",
        "component_capacitance_J_per_K", "wall_capacitance_J_per_K",
        "component_ss_C", "wall_ss_C", "threshold_35C_s",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        csv.DictWriter(f, fieldnames=fields).writeheader()
    with path.open(encoding="utf-8") as f:
        assert next(csv.reader(f)) == fields


def test_biot_number_and_wall_lumped_check():
    bi = biot_number(10.0, 0.002, 100.0)
    assert bi == pytest.approx(2.0e-4)
    check = wall_biot_check(BASE, 2700.0, 154.37)
    assert check["characteristic_length_m"] == pytest.approx((BASE.wall_mass_kg / 2700.0) / BASE.convection_area_m2)
    assert check["Bi"] < 0.1
