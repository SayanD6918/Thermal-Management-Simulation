"""
Automated validation of thermal_model.py.

Each test maps to one of the Phase 3 checks (or to input validation / edge
cases). Expected values come from the governing equations or hand
calculation, never from the program's own output.
"""
import math

import numpy as np
import pytest

import thermal_model as tm
from thermal_model import InvalidParameterError, ThermalParameters

# Illustrative baseline: Tss = 75 C, tau = 450 s (verified by hand: 25+5/0.1, 45/0.1)
BASE = ThermalParameters(
    heat_generation_W=5.0, mass_kg=0.05, specific_heat_J_per_kgK=900.0,
    area_m2=0.01, h_W_per_m2K=10.0, ambient_C=25.0, initial_C=25.0,
    duration_s=4500.0, dt_s=1.0,   # 10 tau
)


# ---------------------------------------------------------------- formulas
def test_analytical_formulas_by_hand():
    assert tm.steady_state_temperature(BASE) == pytest.approx(75.0)
    assert tm.time_constant(BASE) == pytest.approx(450.0)
    # At t = tau the response has covered 1 - 1/e of the rise.
    T_tau = tm.analytical_temperature(BASE, np.array([450.0]))[0]
    assert T_tau == pytest.approx(25.0 + 50.0 * (1 - math.exp(-1)))


# ------------------------------------------------------ initial condition
@pytest.mark.parametrize("method", ["rk4", "euler"])
@pytest.mark.parametrize("T0", [25.0, 10.0, 120.0])
def test_initial_condition(method, T0):
    r = tm.simulate(BASE.with_changes(initial_C=T0), method)
    assert r["time_s"][0] == 0.0
    assert r["temperature_C"][0] == T0


# --------------------------------------------------------------- steady state
@pytest.mark.parametrize("method", ["rk4", "euler"])
def test_approaches_analytical_steady_state(method):
    r = tm.simulate(BASE, method)
    # 10 tau -> remaining gap is 50*exp(-10) = 2.3e-3 K
    assert r["temperature_C"][-1] == pytest.approx(tm.steady_state_temperature(BASE), abs=5e-3)


def test_long_run_converges_to_steady_state_tightly():
    p = BASE.with_changes(duration_s=450.0 * 40, dt_s=5.0)
    assert tm.simulate(p)["temperature_C"][-1] == pytest.approx(75.0, abs=1e-9)


# ------------------------------------------------------------------ heating
def test_heating_is_monotonic_and_never_overshoots():
    T = tm.simulate(BASE)["temperature_C"]
    assert np.all(np.diff(T) > 0)
    assert T.max() < tm.steady_state_temperature(BASE)


def test_starting_above_steady_state_cools_down_to_it():
    p = BASE.with_changes(initial_C=120.0)  # above Tss = 75
    T = tm.simulate(p)["temperature_C"]
    assert np.all(np.diff(T) < 0)
    assert T[-1] > 75.0 and T[-1] == pytest.approx(75.0, abs=0.01)


# ------------------------------------------------------------------ cooling
def test_cooling_with_zero_heat_generation_goes_to_ambient():
    p = BASE.with_changes(heat_generation_W=0.0, initial_C=80.0)
    T = tm.simulate(p)["temperature_C"]
    assert np.all(np.diff(T) < 0)
    assert T[-1] > p.ambient_C                      # never crosses ambient
    assert T[-1] == pytest.approx(25.0, abs=0.01)   # 55*exp(-10) = 2.5e-3 K
    assert tm.steady_state_temperature(p) == pytest.approx(25.0)


def test_zero_heat_at_ambient_stays_constant():
    p = BASE.with_changes(heat_generation_W=0.0)
    assert np.allclose(tm.simulate(p)["temperature_C"], 25.0, atol=1e-12)


# --------------------------------------------------------------- sensitivity
def test_higher_heat_generation_raises_steady_state():
    tss = [tm.steady_state_temperature(BASE.with_changes(heat_generation_W=q)) for q in (1, 2, 5, 10)]
    assert all(b > a for a, b in zip(tss, tss[1:]))
    # Rise above ambient is proportional to Q_gen.
    assert tss[3] - 25.0 == pytest.approx(10 * (tss[0] - 25.0))


@pytest.mark.parametrize("field", ["h_W_per_m2K", "area_m2"])
def test_larger_h_or_area_reduces_steady_state_rise(field):
    base_val = getattr(BASE, field)
    rises = [tm.steady_state_temperature(BASE.with_changes(**{field: base_val * f})) - 25.0
             for f in (0.5, 1, 2, 4)]
    assert all(b < a for a, b in zip(rises, rises[1:]))
    assert rises[2] == pytest.approx(rises[1] / 2)  # rise ~ 1/(hA)


def test_thermal_mass_changes_speed_not_steady_state():
    light = BASE.with_changes(mass_kg=0.025)
    heavy = BASE.with_changes(mass_kg=0.10)
    # same steady state
    assert tm.steady_state_temperature(light) == tm.steady_state_temperature(heavy) == pytest.approx(75.0)
    # tau scales with m*cp
    assert tm.time_constant(heavy) == pytest.approx(4 * tm.time_constant(light))
    # heavy part is cooler at every t > 0 when heating from ambient
    Tl = tm.simulate(light)["temperature_C"]
    Th = tm.simulate(heavy)["temperature_C"]
    assert np.all(Th[1:] < Tl[1:])
    # and takes longer to reach 60 C
    tl = tm.time_to_threshold(*(lambda r: (r["time_s"], r["temperature_C"]))(tm.simulate(light)), 60.0)
    th = tm.time_to_threshold(*(lambda r: (r["time_s"], r["temperature_C"]))(tm.simulate(heavy)), 60.0)
    assert th > tl


# ------------------------------------------------------------- time-step check
def _max_err(p, method):
    r = tm.simulate(p, method)
    return float(np.max(np.abs(r["temperature_C"] - tm.analytical_temperature(p, r["time_s"]))))


def test_rk4_accuracy_at_default_dt():
    assert _max_err(BASE, "rk4") < 1e-9          # K


def test_euler_accuracy_at_default_dt_is_acceptable():
    assert _max_err(BASE, "euler") < 0.05        # K  (dt = tau/450)


@pytest.mark.parametrize("method,expected_order,tol", [("euler", 1.0, 0.1), ("rk4", 4.0, 0.3)])
def test_observed_order_of_convergence(method, expected_order, tol):
    """Halving dt should cut the global error by 2**order."""
    errs = [_max_err(BASE.with_changes(dt_s=dt), method) for dt in (100.0, 50.0, 25.0, 12.5)]
    orders = [math.log2(a / b) for a, b in zip(errs, errs[1:])]
    assert all(e > 0 for e in errs)
    assert all(abs(o - expected_order) < tol for o in orders[-2:]), (errs, orders)


def test_euler_unstable_step_is_rejected():
    with pytest.raises(InvalidParameterError, match="unstable"):
        tm.simulate(BASE.with_changes(dt_s=900.0), "euler")  # dt = 2*tau


def test_final_step_shortened_when_dt_does_not_divide_duration():
    r = tm.simulate(BASE.with_changes(duration_s=100.0, dt_s=30.0))
    assert r["time_s"][-1] == pytest.approx(100.0)
    assert len(r["time_s"]) == 5  # 0, 30, 60, 90, 100
    # The shortened last step must not be worse than ordinary RK4 truncation
    # error (dt/tau = 0.067 here, giving ~1e-6 K). Compare with a run whose
    # duration IS a multiple of dt rather than using a magic tolerance.
    err_short = _max_err(BASE.with_changes(duration_s=100.0, dt_s=30.0), "rk4")
    err_divisible = _max_err(BASE.with_changes(duration_s=120.0, dt_s=30.0), "rk4")
    assert err_short <= err_divisible
    assert err_short < 1e-5


# ---------------------------------------------------------------- energy balance
def test_integral_energy_balance_closes():
    r = tm.simulate(BASE)
    e = tm.energy_balance_residual(BASE, r["time_s"], r["temperature_C"])
    assert e["energy_in_J"] == pytest.approx(5.0 * 4500.0)
    assert e["relative_residual"] < 1e-6
    assert e["energy_stored_J"] == pytest.approx(45.0 * (r["temperature_C"][-1] - 25.0))


def test_energy_residual_shrinks_second_order_with_dt():
    res = []
    for dt in (20.0, 10.0, 5.0):
        p = BASE.with_changes(dt_s=dt)
        r = tm.simulate(p)
        res.append(abs(tm.energy_balance_residual(p, r["time_s"], r["temperature_C"])["residual_J"]))
    assert 3.5 < res[0] / res[1] < 4.5 and 3.5 < res[1] / res[2] < 4.5, res  # trapezoid is O(dt^2)


def test_pointwise_energy_balance_dTdt():
    """C*dT/dt (central difference) must equal Q_gen - h*A*(T - T_inf) at interior points."""
    p = BASE.with_changes(dt_s=0.5, duration_s=2000.0)
    r = tm.simulate(p)
    t, T = r["time_s"], r["temperature_C"]
    dTdt = (T[2:] - T[:-2]) / (t[2:] - t[:-2])
    lhs = p.heat_capacity_J_per_K * dTdt
    rhs = p.heat_generation_W - p.conductance_W_per_K * (T[1:-1] - p.ambient_C)
    assert np.max(np.abs(lhs - rhs)) < 1e-4  # W, vs. Q_gen = 5 W


# --------------------------------------------------------------- time to threshold
def test_time_to_threshold_matches_analytical_and_hand_value():
    r = tm.simulate(BASE)
    t_num = tm.time_to_threshold(r["time_s"], r["temperature_C"], 60.0)
    t_exact = tm.analytical_time_to_temperature(BASE, 60.0)
    assert t_exact == pytest.approx(-450.0 * math.log(0.3))     # hand calc: 541.79 s
    assert t_num == pytest.approx(t_exact, abs=0.01)


def test_threshold_not_reached_returns_none():
    r = tm.simulate(BASE)
    assert tm.time_to_threshold(r["time_s"], r["temperature_C"], 80.0) is None   # above Tss
    assert tm.analytical_time_to_temperature(BASE, 80.0) is None
    assert tm.analytical_time_to_temperature(BASE, 75.0) is None                  # asymptote only
    assert tm.analytical_time_to_temperature(BASE, 20.0) is None                  # below start


def test_threshold_at_initial_temperature_is_time_zero():
    r = tm.simulate(BASE)
    assert tm.time_to_threshold(r["time_s"], r["temperature_C"], 25.0) == 0.0


def test_threshold_found_when_cooling():
    p = BASE.with_changes(heat_generation_W=0.0, initial_C=80.0)
    r = tm.simulate(p)
    t = tm.time_to_threshold(r["time_s"], r["temperature_C"], 40.0)
    assert t == pytest.approx(tm.analytical_time_to_temperature(p, 40.0), abs=0.01)


# ---------------------------------------------------------------- input validation
@pytest.mark.parametrize("field,bad", [
    ("mass_kg", 0.0), ("mass_kg", -1.0),
    ("specific_heat_J_per_kgK", 0.0), ("specific_heat_J_per_kgK", -900.0),
    ("area_m2", 0.0), ("area_m2", -0.01),
    ("h_W_per_m2K", 0.0), ("h_W_per_m2K", -5.0),
    ("dt_s", 0.0), ("dt_s", -1.0),
    ("duration_s", 0.0), ("duration_s", -10.0),
    ("heat_generation_W", -1.0),
    ("ambient_C", -300.0), ("initial_C", -273.15),
    ("mass_kg", float("nan")), ("area_m2", float("inf")), ("ambient_C", float("nan")),
    ("mass_kg", "heavy"), ("mass_kg", True),
])
def test_invalid_inputs_are_rejected_with_named_message(field, bad):
    with pytest.raises(InvalidParameterError, match=field):
        BASE.with_changes(**{field: bad})
    with pytest.raises(InvalidParameterError):
        from dataclasses import replace
        tm.simulate(replace(BASE, **{field: bad}))


def test_dt_larger_than_duration_rejected():
    with pytest.raises(InvalidParameterError, match="dt_s"):
        BASE.with_changes(dt_s=10.0, duration_s=5.0)


def test_excessive_step_count_rejected():
    with pytest.raises(InvalidParameterError, match="steps"):
        BASE.with_changes(dt_s=1e-6, duration_s=1000.0)


def test_unknown_method_rejected():
    with pytest.raises(InvalidParameterError, match="method"):
        tm.simulate(BASE, "magic")
