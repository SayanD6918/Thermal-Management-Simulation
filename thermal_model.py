"""
thermal_model.py -- Lumped-capacitance model of a heat-generating component.

Physics only: no plotting, no file I/O, no user interface.

Governing energy balance (single uniform temperature, constant parameters):

    m * cp * dT/dt = Q_gen - h * A * (T - T_inf)

Analytical results (constant parameters):

    T_ss = T_inf + Q_gen / (h * A)
    tau  = m * cp / (h * A)
    T(t) = T_ss + (T0 - T_ss) * exp(-t / tau)

ASSUMPTIONS AND SCOPE (read before using the results)
-----------------------------------------------------
* The component is ONE node at ONE uniform temperature (Biot number small).
  No spatial temperature gradients are modelled.
* ALL heat leaves by convection from area A to a fixed ambient temperature
  T_inf. Enclosure walls, internal air temperature, conduction paths, contact
  resistance and radiation are NOT modelled in this version. The result is
  therefore NOT a complete enclosure simulation; "ambient" means the
  temperature of the fluid that the effective exposed area A "sees".
* Q_gen, h, A, m, cp and T_inf are constant in time.
* Units are SI internally (W, kg, J/(kg K), m^2, W/(m^2 K), s). Temperatures
  are in degC; because only temperature DIFFERENCES enter the equation, this
  is equivalent to using kelvin.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Callable, Optional

import numpy as np

ABSOLUTE_ZERO_C = -273.15
MAX_STEPS = 5_000_000  # guard against accidental huge allocations


class InvalidParameterError(ValueError):
    """Raised when a model input is physically or numerically unacceptable."""


# --------------------------------------------------------------------------
# Parameters
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class ThermalParameters:
    """Inputs of the lumped-capacitance model (SI units, temperatures in degC)."""

    heat_generation_W: float          # Q_gen, W (>= 0)
    mass_kg: float                    # m, kg (> 0)
    specific_heat_J_per_kgK: float    # cp, J/(kg K) (> 0)
    area_m2: float                    # A, effective exposed area, m^2 (> 0)
    h_W_per_m2K: float                # h, W/(m^2 K) (> 0)
    ambient_C: float                  # T_inf, degC
    initial_C: float                  # T0, degC
    duration_s: float                 # simulated time span, s (> 0)
    dt_s: float                       # time step, s (> 0, <= duration)

    # -- derived quantities ------------------------------------------------
    @property
    def heat_capacity_J_per_K(self) -> float:
        """Lumped thermal capacitance C = m * cp  [J/K]."""
        return self.mass_kg * self.specific_heat_J_per_kgK

    @property
    def conductance_W_per_K(self) -> float:
        """Convective conductance G = h * A  [W/K] (= 1 / R_conv)."""
        return self.h_W_per_m2K * self.area_m2

    def with_changes(self, **kwargs) -> "ThermalParameters":
        """Return a validated copy with some fields replaced."""
        new = replace(self, **kwargs)
        validate_parameters(new)
        return new


def validate_parameters(p: ThermalParameters) -> None:
    """Raise InvalidParameterError with a descriptive message for bad inputs."""

    def finite(name: str, value: float) -> None:
        if not isinstance(value, (int, float, np.floating, np.integer)) or isinstance(value, bool):
            raise InvalidParameterError(f"{name} must be a number, got {value!r}.")
        if not math.isfinite(value):
            raise InvalidParameterError(f"{name} must be finite, got {value}.")

    def positive(name: str, value: float, unit: str) -> None:
        finite(name, value)
        if value <= 0:
            raise InvalidParameterError(f"{name} must be > 0 ({unit}), got {value}.")

    positive("mass_kg", p.mass_kg, "kg")
    positive("specific_heat_J_per_kgK", p.specific_heat_J_per_kgK, "J/(kg K)")
    positive("area_m2", p.area_m2, "m^2")
    # h = 0 would mean no heat path at all: no steady state exists.
    positive("h_W_per_m2K", p.h_W_per_m2K, "W/(m^2 K)")
    positive("duration_s", p.duration_s, "s")
    positive("dt_s", p.dt_s, "s")

    finite("heat_generation_W", p.heat_generation_W)
    if p.heat_generation_W < 0:
        raise InvalidParameterError(
            f"heat_generation_W must be >= 0 (W); a component cannot generate negative heat. "
            f"Got {p.heat_generation_W}."
        )
    for name, value in (("ambient_C", p.ambient_C), ("initial_C", p.initial_C)):
        finite(name, value)
        if value <= ABSOLUTE_ZERO_C:
            raise InvalidParameterError(f"{name} must be above absolute zero ({ABSOLUTE_ZERO_C} degC), got {value}.")

    if p.dt_s > p.duration_s:
        raise InvalidParameterError(
            f"dt_s ({p.dt_s}) must not exceed duration_s ({p.duration_s})."
        )
    n_steps = p.duration_s / p.dt_s
    if n_steps > MAX_STEPS:
        raise InvalidParameterError(
            f"duration_s/dt_s = {n_steps:.3g} steps exceeds the limit of {MAX_STEPS}. Increase dt_s."
        )


# --------------------------------------------------------------------------
# Analytical results
# --------------------------------------------------------------------------
def steady_state_temperature(p: ThermalParameters) -> float:
    """T_ss = T_inf + Q_gen / (h A)   [degC]."""
    validate_parameters(p)
    return p.ambient_C + p.heat_generation_W / p.conductance_W_per_K


def time_constant(p: ThermalParameters) -> float:
    """tau = m cp / (h A)   [s]."""
    validate_parameters(p)
    return p.heat_capacity_J_per_K / p.conductance_W_per_K


def analytical_temperature(p: ThermalParameters, t_s: np.ndarray) -> np.ndarray:
    """Exact solution T(t) for constant parameters   [degC]."""
    t = np.asarray(t_s, dtype=float)
    t_ss = steady_state_temperature(p)
    tau = time_constant(p)
    return t_ss + (p.initial_C - t_ss) * np.exp(-t / tau)


def analytical_time_to_temperature(p: ThermalParameters, threshold_C: float) -> Optional[float]:
    """Exact time at which T(t) first equals `threshold_C`, or None if never reached.

    Inverts T(t): t = -tau * ln((T_thr - T_ss) / (T0 - T_ss)).
    The threshold is reached only if it lies between T0 and T_ss (T_ss itself
    is approached asymptotically and never reached in finite time).
    """
    t_ss = steady_state_temperature(p)
    tau = time_constant(p)
    t0 = p.initial_C
    if threshold_C == t0:
        return 0.0
    if t0 == t_ss:
        return None
    ratio = (threshold_C - t_ss) / (t0 - t_ss)
    if not (0.0 < ratio < 1.0):
        return None
    return float(-tau * math.log(ratio))


# --------------------------------------------------------------------------
# Numerical integration
# --------------------------------------------------------------------------
def _dTdt_factory(p: ThermalParameters) -> Callable[[float, float], float]:
    """Right-hand side dT/dt = (Q_gen - h A (T - T_inf)) / (m cp)   [K/s].

    Kept as a function of (t, T) so later extensions (time-varying loads,
    radiation, multi-node networks) can reuse the same integrators.
    """
    c = p.heat_capacity_J_per_K
    g = p.conductance_W_per_K
    q = p.heat_generation_W
    t_inf = p.ambient_C

    def rhs(_t: float, temp: float) -> float:
        return (q - g * (temp - t_inf)) / c

    return rhs


def simulate(p: ThermalParameters, method: str = "rk4") -> dict:
    """Integrate the energy balance numerically.

    method: "rk4"   -- classical 4th-order Runge-Kutta (default, global error O(dt^4))
            "euler" -- explicit Euler (global error O(dt); stable only if dt < 2*tau)

    Returns a dict with arrays 'time_s' and 'temperature_C'. The final step is
    shortened if duration_s is not an exact multiple of dt_s so that the last
    sample is exactly at duration_s.
    """
    validate_parameters(p)
    if method not in ("rk4", "euler"):
        raise InvalidParameterError(f"Unknown method {method!r}; use 'rk4' or 'euler'.")

    tau = time_constant(p)
    if method == "euler" and p.dt_s >= 2.0 * tau:
        raise InvalidParameterError(
            f"Explicit Euler is unstable for dt_s >= 2*tau (dt_s={p.dt_s}, tau={tau:.4g}). "
            f"Use a smaller dt_s or method='rk4'."
        )
    if method == "rk4" and p.dt_s > 2.7 * tau:
        # RK4 stability limit on dy/dt = -y/tau is dt < ~2.785*tau.
        raise InvalidParameterError(
            f"RK4 is unstable for dt_s > ~2.78*tau (dt_s={p.dt_s}, tau={tau:.4g}). Use a smaller dt_s."
        )

    rhs = _dTdt_factory(p)

    n_full = int(math.floor(p.duration_s / p.dt_s + 1e-12))
    steps = [p.dt_s] * n_full
    remainder = p.duration_s - n_full * p.dt_s
    if remainder > 1e-12 * max(1.0, p.duration_s):
        steps.append(remainder)

    time = np.empty(len(steps) + 1)
    temp = np.empty(len(steps) + 1)
    time[0], temp[0] = 0.0, p.initial_C

    t, y = 0.0, p.initial_C
    for i, dt in enumerate(steps, start=1):
        if method == "euler":
            y = y + dt * rhs(t, y)
        else:
            k1 = rhs(t, y)
            k2 = rhs(t + 0.5 * dt, y + 0.5 * dt * k1)
            k3 = rhs(t + 0.5 * dt, y + 0.5 * dt * k2)
            k4 = rhs(t + dt, y + dt * k3)
            y = y + (dt / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)
        t += dt
        time[i], temp[i] = t, y

    return {"time_s": time, "temperature_C": temp}


# --------------------------------------------------------------------------
# Diagnostics
# --------------------------------------------------------------------------
def time_to_threshold(time_s: np.ndarray, temp_C: np.ndarray, threshold_C: float) -> Optional[float]:
    """First time the simulated temperature reaches `threshold_C` (either direction).

    Uses linear interpolation between samples. Returns None if never reached.
    """
    time_s = np.asarray(time_s, dtype=float)
    d = np.asarray(temp_C, dtype=float) - threshold_C
    if d[0] == 0.0:
        return float(time_s[0])
    sign_change = np.nonzero(np.sign(d[:-1]) * np.sign(d[1:]) <= 0)[0]
    if sign_change.size == 0:
        return None
    i = int(sign_change[0])
    if d[i + 1] == d[i]:  # cannot happen when sign changed unless both are zero
        return float(time_s[i])
    frac = -d[i] / (d[i + 1] - d[i])
    return float(time_s[i] + frac * (time_s[i + 1] - time_s[i]))


def energy_balance_residual(p: ThermalParameters, time_s: np.ndarray, temp_C: np.ndarray) -> dict:
    """Integral check of the energy balance over the whole run.

        stored  = m cp (T_end - T_0)
        in      = Q_gen * t_end
        out     = integral of h A (T - T_inf) dt   (trapezoidal rule on the numerical T)

    Residual = in - out - stored. It would be zero for the exact solution; for
    the numerical solution it is limited by the trapezoidal quadrature, O(dt^2).
    Returned in joules, plus a relative value normalised by the larger of |in|,
    |out|, |stored| (None if all are zero).
    """
    time_s = np.asarray(time_s, dtype=float)
    temp_C = np.asarray(temp_C, dtype=float)
    stored = p.heat_capacity_J_per_K * (temp_C[-1] - temp_C[0])
    e_in = p.heat_generation_W * (time_s[-1] - time_s[0])
    flux = p.conductance_W_per_K * (temp_C - p.ambient_C)
    e_out = float(np.sum(0.5 * (flux[1:] + flux[:-1]) * np.diff(time_s)))
    residual = e_in - e_out - stored
    scale = max(abs(e_in), abs(e_out), abs(stored))
    return {
        "energy_in_J": e_in,
        "energy_out_J": e_out,
        "energy_stored_J": stored,
        "residual_J": residual,
        "relative_residual": (abs(residual) / scale) if scale > 0 else None,
    }
