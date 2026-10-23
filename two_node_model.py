"""Two-node component/enclosure-wall thermal model.

Model:
    Cc dTc/dt = Qgen - (Tc - Tw)/Rcond
    Cw dTw/dt = (Tc - Tw)/Rcond - (Tw - Tinf)/Rconv

The component and wall are treated as spatially uniform lumped thermal nodes.
All parameters are constant during one simulation. Temperatures are in degC;
temperature differences are identical in kelvin.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Optional

import numpy as np

ABSOLUTE_ZERO_C = -273.15
MAX_STEPS = 5_000_000


class InvalidParameterError(ValueError):
    """Raised when a two-node model input is physically or numerically invalid."""


@dataclass(frozen=True)
class TwoNodeParameters:
    """Validated physical and numerical parameters for the two-node model."""

    heat_generation_W: float
    component_mass_kg: float
    component_specific_heat_J_per_kgK: float
    wall_mass_kg: float
    wall_specific_heat_J_per_kgK: float
    conduction_thickness_m: float
    conduction_conductivity_W_per_mK: float
    conduction_area_m2: float
    convection_h_W_per_m2K: float
    convection_area_m2: float
    ambient_C: float
    initial_component_C: float
    initial_wall_C: float
    duration_s: float
    dt_s: float

    @property
    def component_capacitance_J_per_K(self) -> float:
        return self.component_mass_kg * self.component_specific_heat_J_per_kgK

    @property
    def wall_capacitance_J_per_K(self) -> float:
        return self.wall_mass_kg * self.wall_specific_heat_J_per_kgK

    @property
    def R_cond_K_per_W(self) -> float:
        return self.conduction_thickness_m / (
            self.conduction_conductivity_W_per_mK * self.conduction_area_m2
        )

    @property
    def R_conv_K_per_W(self) -> float:
        return 1.0 / (self.convection_h_W_per_m2K * self.convection_area_m2)

    def with_changes(self, **kwargs) -> "TwoNodeParameters":
        new = replace(self, **kwargs)
        validate_parameters(new)
        return new


def validate_parameters(p: TwoNodeParameters) -> None:
    def finite(name: str, value: float) -> None:
        if isinstance(value, bool) or not isinstance(value, (int, float, np.integer, np.floating)):
            raise InvalidParameterError(f"{name} must be a finite number, got {value!r}.")
        if not math.isfinite(float(value)):
            raise InvalidParameterError(f"{name} must be finite, got {value}.")

    def positive(name: str, value: float, unit: str) -> None:
        finite(name, value)
        if value <= 0:
            raise InvalidParameterError(f"{name} must be > 0 ({unit}), got {value}.")

    positive("component_mass_kg", p.component_mass_kg, "kg")
    positive("component_specific_heat_J_per_kgK", p.component_specific_heat_J_per_kgK, "J/(kg K)")
    positive("wall_mass_kg", p.wall_mass_kg, "kg")
    positive("wall_specific_heat_J_per_kgK", p.wall_specific_heat_J_per_kgK, "J/(kg K)")
    positive("conduction_thickness_m", p.conduction_thickness_m, "m")
    positive("conduction_conductivity_W_per_mK", p.conduction_conductivity_W_per_mK, "W/(m K)")
    positive("conduction_area_m2", p.conduction_area_m2, "m^2")
    positive("convection_h_W_per_m2K", p.convection_h_W_per_m2K, "W/(m^2 K)")
    positive("convection_area_m2", p.convection_area_m2, "m^2")
    positive("duration_s", p.duration_s, "s")
    positive("dt_s", p.dt_s, "s")
    finite("heat_generation_W", p.heat_generation_W)
    if p.heat_generation_W < 0:
        raise InvalidParameterError("heat_generation_W must be >= 0 (W).")
    for name, value in (("ambient_C", p.ambient_C), ("initial_component_C", p.initial_component_C),
                        ("initial_wall_C", p.initial_wall_C)):
        finite(name, value)
        if value <= ABSOLUTE_ZERO_C:
            raise InvalidParameterError(f"{name} must be above absolute zero ({ABSOLUTE_ZERO_C} degC), got {value}.")
    if p.dt_s > p.duration_s:
        raise InvalidParameterError(f"dt_s ({p.dt_s}) must not exceed duration_s ({p.duration_s}).")
    steps = p.duration_s / p.dt_s
    if steps > MAX_STEPS:
        raise InvalidParameterError(f"duration_s/dt_s = {steps:.3g} exceeds {MAX_STEPS} steps; increase dt_s.")


def steady_state_temperatures(p: TwoNodeParameters) -> tuple[float, float]:
    """Return analytical (component, wall) steady-state temperatures in degC."""
    validate_parameters(p)
    tc = p.ambient_C + p.heat_generation_W * (p.R_cond_K_per_W + p.R_conv_K_per_W)
    tw = p.ambient_C + p.heat_generation_W * p.R_conv_K_per_W
    return float(tc), float(tw)


def system_matrix(p: TwoNodeParameters) -> np.ndarray:
    """Return the linear system matrix A for dT/dt = A*T + b."""
    validate_parameters(p)
    cc, cw = p.component_capacitance_J_per_K, p.wall_capacitance_J_per_K
    rc, rv = p.R_cond_K_per_W, p.R_conv_K_per_W
    return np.array([
        [-1.0 / (cc * rc), 1.0 / (cc * rc)],
        [1.0 / (cw * rc), -(1.0 / rc + 1.0 / rv) / cw],
    ], dtype=float)


def eigenvalues(p: TwoNodeParameters) -> np.ndarray:
    """Return the two real, negative eigenvalues of the thermal system matrix."""
    vals = np.linalg.eigvals(system_matrix(p))
    vals = np.sort(np.real_if_close(vals).astype(float))
    if np.any(vals >= 0.0):
        raise RuntimeError(f"Expected stable thermal eigenvalues, got {vals}.")
    return vals


def analytical_transient(p: TwoNodeParameters, t_s: np.ndarray) -> dict[str, np.ndarray]:
    """Independent analytical transient using eigenvalues/eigenvectors."""
    validate_parameters(p)
    t = np.asarray(t_s, dtype=float)
    if np.any(~np.isfinite(t)) or np.any(t < 0):
        raise InvalidParameterError("t_s must contain finite, non-negative times in seconds.")

    tc_ss, tw_ss = steady_state_temperatures(p)
    x_ss = np.array([tc_ss, tw_ss], dtype=float)
    x0 = np.array([p.initial_component_C, p.initial_wall_C], dtype=float)
    A = system_matrix(p)
    vals, vecs = np.linalg.eig(A)
    vals = np.real_if_close(vals).astype(float)
    vecs = np.real_if_close(vecs).astype(float)
    coeff = np.linalg.solve(vecs, x0 - x_ss)
    modes = vecs @ (coeff[:, None] * np.exp(vals[:, None] * t[None, :]))
    x = x_ss[:, None] + modes
    return {"component_C": x[0], "wall_C": x[1]}


def analytical_threshold_time(p: TwoNodeParameters, threshold_C: float) -> Optional[float]:
    """Find component threshold time numerically from the analytical solution.

    A two-mode response does not generally admit a single logarithmic inverse.
    This routine brackets the first crossing over the requested simulation
    interval and uses bisection on the independent analytical solution.
    """
    validate_parameters(p)
    if not isinstance(threshold_C, (int, float, np.integer, np.floating)) or not math.isfinite(float(threshold_C)):
        raise InvalidParameterError("threshold_C must be a finite number.")
    if threshold_C <= ABSOLUTE_ZERO_C:
        raise InvalidParameterError("threshold_C must be above absolute zero.")

    f = lambda t: float(analytical_transient(p, np.array([t]))["component_C"][0] - threshold_C)
    f0 = f(0.0)
    if f0 == 0.0:
        return 0.0
    # Find a bracket on the model's simulation interval.
    grid = np.linspace(0.0, p.duration_s, 2001)
    vals = analytical_transient(p, grid)["component_C"] - threshold_C
    idx = np.flatnonzero(vals[:-1] * vals[1:] <= 0.0)
    if idx.size == 0:
        return None
    i = int(idx[0])
    lo, hi = float(grid[i]), float(grid[i + 1])
    if abs(vals[i]) < 1e-14:
        return lo
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        if f(lo) * f(mid) <= 0:
            hi = mid
        else:
            lo = mid
    return 0.5 * (lo + hi)


def _rhs(p: TwoNodeParameters, component_C: float, wall_C: float) -> tuple[float, float, float]:
    q_cond = (component_C - wall_C) / p.R_cond_K_per_W
    q_conv = (wall_C - p.ambient_C) / p.R_conv_K_per_W
    dTc = (p.heat_generation_W - q_cond) / p.component_capacitance_J_per_K
    dTw = (q_cond - q_conv) / p.wall_capacitance_J_per_K
    return dTc, dTw, q_cond


def simulate(p: TwoNodeParameters, method: str = "rk4") -> dict[str, np.ndarray]:
    """Numerically integrate the two-node balances using RK4 or explicit Euler."""
    validate_parameters(p)
    if method not in {"rk4", "euler"}:
        raise InvalidParameterError("Unknown method; use 'rk4' or 'euler'.")

    # Explicit RK4/Euler have finite stability regions. Reject a step that is
    # unstable for the fastest thermal eigenmode rather than returning nonsense.
    lam_max = float(np.max(np.abs(eigenvalues(p))))
    if method == "euler" and p.dt_s * lam_max >= 2.0:
        raise InvalidParameterError(
            f"Explicit Euler is unstable for the fastest thermal mode: dt_s*|lambda_max| "
            f"= {p.dt_s * lam_max:.4g} >= 2. Use a smaller dt_s."
        )
    if method == "rk4" and p.dt_s * lam_max > 2.7:
        raise InvalidParameterError(
            f"RK4 may be unstable for the fastest thermal mode: dt_s*|lambda_max| "
            f"= {p.dt_s * lam_max:.4g} > 2.7. Use a smaller dt_s."
        )

    n_full = int(math.floor(p.duration_s / p.dt_s + 1e-12))
    steps = [p.dt_s] * n_full
    remainder = p.duration_s - n_full * p.dt_s
    if remainder > 1e-12 * max(1.0, p.duration_s):
        steps.append(remainder)

    time = np.empty(len(steps) + 1)
    tc = np.empty_like(time)
    tw = np.empty_like(time)
    qcond = np.empty_like(time)
    time[0], tc[0], tw[0] = 0.0, p.initial_component_C, p.initial_wall_C
    qcond[0] = (tc[0] - tw[0]) / p.R_cond_K_per_W
    t = 0.0
    for i, dt in enumerate(steps, start=1):
        if method == "euler":
            k1c, k1w, _ = _rhs(p, tc[i-1], tw[i-1])
            tc[i] = tc[i-1] + dt * k1c
            tw[i] = tw[i-1] + dt * k1w
        else:
            k1c, k1w, _ = _rhs(p, tc[i-1], tw[i-1])
            k2c, k2w, _ = _rhs(p, tc[i-1] + 0.5*dt*k1c, tw[i-1] + 0.5*dt*k1w)
            k3c, k3w, _ = _rhs(p, tc[i-1] + 0.5*dt*k2c, tw[i-1] + 0.5*dt*k2w)
            k4c, k4w, _ = _rhs(p, tc[i-1] + dt*k3c, tw[i-1] + dt*k3w)
            tc[i] = tc[i-1] + dt*(k1c + 2*k2c + 2*k3c + k4c)/6.0
            tw[i] = tw[i-1] + dt*(k1w + 2*k2w + 2*k3w + k4w)/6.0
        t += dt
        time[i], qcond[i] = t, (tc[i] - tw[i]) / p.R_cond_K_per_W
    return {"time_s": time, "component_C": tc, "wall_C": tw, "conduction_W": qcond}


def time_to_threshold(time_s: np.ndarray, temp_C: np.ndarray, threshold_C: float) -> Optional[float]:
    """Return first linearly interpolated crossing time, or None."""
    t = np.asarray(time_s, dtype=float)
    y = np.asarray(temp_C, dtype=float) - threshold_C
    if t.ndim != 1 or y.ndim != 1 or len(t) != len(y) or len(t) == 0:
        raise InvalidParameterError("time_s and temp_C must be non-empty one-dimensional arrays of equal length.")
    if y[0] == 0:
        return float(t[0])
    crossings = np.flatnonzero(y[:-1] * y[1:] <= 0)
    if crossings.size == 0:
        return None
    i = int(crossings[0])
    if y[i + 1] == y[i]:
        return float(t[i])
    return float(t[i] + (threshold_C - (y[i] + threshold_C)) * (t[i+1] - t[i]) / ((y[i+1] + threshold_C) - (y[i] + threshold_C)))


def total_energy_balance(p: TwoNodeParameters, result: dict[str, np.ndarray]) -> dict[str, float]:
    """Check total energy: generated = stored + convected to ambient."""
    t = result["time_s"]
    tc = result["component_C"]
    tw = result["wall_C"]
    qconv = (tw - p.ambient_C) / p.R_conv_K_per_W
    energy_in = p.heat_generation_W * (t[-1] - t[0])
    energy_stored = (
        p.component_capacitance_J_per_K * (tc[-1] - tc[0])
        + p.wall_capacitance_J_per_K * (tw[-1] - tw[0])
    )
    energy_out = float(np.trapezoid(qconv, t))
    residual = energy_in - energy_stored - energy_out
    return {
        "energy_in_J": float(energy_in),
        "energy_stored_J": float(energy_stored),
        "energy_out_J": energy_out,
        "residual_J": float(residual),
        "relative_residual": abs(float(residual)) / max(abs(energy_in), 1.0),
    }
