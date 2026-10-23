import math
from dataclasses import replace

import numpy as np
import pytest

import two_node_model as tm

BASE = tm.TwoNodeParameters(
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
    dt_s=1.0,
)


def test_initial_temperatures_are_preserved():
    p = BASE.with_changes(initial_component_C=40.0, initial_wall_C=30.0)
    r = tm.simulate(p)
    assert r["component_C"][0] == 40.0
    assert r["wall_C"][0] == 30.0


def test_steady_state_matches_analytical_equations():
    tc, tw = tm.steady_state_temperatures(BASE)
    assert tc == pytest.approx(BASE.ambient_C + BASE.heat_generation_W * (BASE.R_cond_K_per_W + BASE.R_conv_K_per_W))
    assert tw == pytest.approx(BASE.ambient_C + BASE.heat_generation_W * BASE.R_conv_K_per_W)
    r = tm.simulate(BASE.with_changes(duration_s=40_000.0, dt_s=1.0))
    assert r["component_C"][-1] == pytest.approx(tc, abs=1e-7)
    assert r["wall_C"][-1] == pytest.approx(tw, abs=1e-7)


def test_transient_matches_independent_eigen_solution():
    p = BASE.with_changes(duration_s=2000.0, dt_s=0.25, initial_component_C=50.0, initial_wall_C=20.0)
    r = tm.simulate(p)
    a = tm.analytical_transient(p, r["time_s"])
    assert np.max(np.abs(r["component_C"] - a["component_C"])) < 2e-3
    assert np.max(np.abs(r["wall_C"] - a["wall_C"])) < 2e-3
    vals = tm.eigenvalues(p)
    assert len(vals) == 2 and np.all(vals < 0)


def test_energy_conservation_and_equal_opposite_conduction_flux():
    p = BASE.with_changes(duration_s=1000.0, dt_s=0.5)
    r = tm.simulate(p)
    q = (r["component_C"] - r["wall_C"]) / p.R_cond_K_per_W
    q_component_loss = -q
    q_wall_gain = q
    assert np.max(np.abs(q_component_loss + q_wall_gain)) == 0.0
    eb = tm.total_energy_balance(p, r)
    assert eb["relative_residual"] < 1e-7


def test_positive_heat_generation_heats_both_nodes_from_ambient():
    r = tm.simulate(BASE.with_changes(duration_s=1000.0))
    assert r["component_C"][-1] > BASE.ambient_C
    assert r["wall_C"][-1] > BASE.ambient_C
    assert np.all(np.diff(r["component_C"]) >= -1e-12)
    assert np.all(np.diff(r["wall_C"]) >= -1e-12)


def test_zero_heat_generation_cools_from_above_ambient():
    p = BASE.with_changes(heat_generation_W=0.0, initial_component_C=90.0, initial_wall_C=70.0, duration_s=5000.0)
    r = tm.simulate(p)
    assert r["component_C"][-1] < 90.0
    assert r["wall_C"][-1] < 70.0
    assert r["component_C"][-1] > p.ambient_C
    assert r["wall_C"][-1] > p.ambient_C


def test_increasing_conduction_resistance_raises_component_temperature():
    low = tm.steady_state_temperatures(BASE.with_changes(conduction_thickness_m=0.0005))[0]
    high = tm.steady_state_temperatures(BASE.with_changes(conduction_thickness_m=0.008))[0]
    assert high > low


def test_increasing_convection_resistance_raises_both_steady_state_temperatures():
    low = tm.steady_state_temperatures(BASE.with_changes(convection_h_W_per_m2K=20.0))
    high = tm.steady_state_temperatures(BASE.with_changes(convection_h_W_per_m2K=5.0))
    assert high[0] > low[0]
    assert high[1] > low[1]


def test_threshold_matches_numerical_and_analytical_results():
    p = BASE.with_changes(duration_s=3000.0, dt_s=0.5)
    # The baseline steady-state component temperature is below 60 °C, so use a reached threshold.
    r = tm.simulate(p)
    numerical = tm.time_to_threshold(r["time_s"], r["component_C"], 35.0)
    analytical = tm.analytical_threshold_time(p, 35.0)
    assert numerical is not None and analytical is not None
    assert numerical == pytest.approx(analytical, abs=0.01)


def test_invalid_parameters_are_rejected():
    cases = [
        ("component_mass_kg", 0.0),
        ("wall_mass_kg", -1.0),
        ("component_specific_heat_J_per_kgK", 0.0),
        ("conduction_thickness_m", 0.0),
        ("conduction_conductivity_W_per_mK", -1.0),
        ("conduction_area_m2", 0.0),
        ("convection_h_W_per_m2K", 0.0),
        ("convection_area_m2", -1.0),
        ("duration_s", 0.0),
        ("dt_s", 0.0),
        ("heat_generation_W", -1.0),
        ("ambient_C", -273.15),
    ]
    for field, value in cases:
        with pytest.raises(tm.InvalidParameterError, match=field):
            BASE.with_changes(**{field: value})


def test_reduced_time_step_converges():
    p1 = BASE.with_changes(dt_s=1.0, duration_s=1000.0)
    p2 = BASE.with_changes(dt_s=0.5, duration_s=1000.0)
    e1 = np.max(np.abs(tm.simulate(p1)["component_C"] - tm.analytical_transient(p1, tm.simulate(p1)["time_s"])["component_C"]))
    e2 = np.max(np.abs(tm.simulate(p2)["component_C"] - tm.analytical_transient(p2, tm.simulate(p2)["time_s"])["component_C"]))
    assert e2 < e1


def test_final_shortened_step_lands_exactly_on_duration():
    p = BASE.with_changes(duration_s=1.5, dt_s=1.0)
    r = tm.simulate(p)
    assert r["time_s"][-1] == pytest.approx(1.5)


def test_single_node_limit_uses_combined_capacitance():
    # A small R_cond makes the two temperatures nearly equal after the fast
    # internal equilibration. The comparison is made with the equivalent
    # single-node model using Cc + Cw and the same R_conv.
    p = BASE.with_changes(conduction_thickness_m=0.0001, duration_s=3000.0, dt_s=0.01)
    t = np.array([10.0, 100.0, 1000.0, 3000.0])
    a = tm.analytical_transient(p, t)
    C = p.component_capacitance_J_per_K + p.wall_capacitance_J_per_K
    R = p.R_conv_K_per_W
    Tss = p.ambient_C + p.heat_generation_W * R
    tau = C * R
    lumped = Tss + (p.initial_component_C - Tss) * np.exp(-t / tau)
    assert np.max(np.abs(a["component_C"] - lumped)) < 0.02
    assert np.max(np.abs(a["wall_C"] - lumped)) < 0.02


def test_steady_state_heat_flow_is_consistent():
    tc, tw = tm.steady_state_temperatures(BASE)
    q_cond = (tc - tw) / BASE.R_cond_K_per_W
    q_conv = (tw - BASE.ambient_C) / BASE.R_conv_K_per_W
    assert q_cond == pytest.approx(BASE.heat_generation_W)
    assert q_conv == pytest.approx(BASE.heat_generation_W)
