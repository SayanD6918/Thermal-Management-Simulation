"""Run the Stage 2 two-node thermal simulation and scenario study."""
from pathlib import Path
import csv
import matplotlib.pyplot as plt
import numpy as np

from two_node_model import TwoNodeParameters, simulate, steady_state_temperatures, analytical_transient, analytical_threshold_time, time_to_threshold

OUT = Path(__file__).parent / "outputs"
OUT.mkdir(exist_ok=True)

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
    dt_s=0.1,
)
THRESHOLD_C = 35.0


def save_csv(path: Path, result: dict[str, np.ndarray]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["time_s", "component_C", "wall_C", "conduction_W"])
        writer.writerows(zip(result["time_s"], result["component_C"], result["wall_C"], result["conduction_W"]))


def run_case(name: str, p: TwoNodeParameters) -> dict:
    r = simulate(p, "rk4")
    ss_c, ss_w = steady_state_temperatures(p)
    exact = analytical_transient(p, r["time_s"])
    err_c = float(np.max(np.abs(r["component_C"] - exact["component_C"])))
    err_w = float(np.max(np.abs(r["wall_C"] - exact["wall_C"])))
    threshold = time_to_threshold(r["time_s"], r["component_C"], THRESHOLD_C)
    return {"name": name, "params": p, "result": r, "ss_c": ss_c, "ss_w": ss_w, "err_c": err_c, "err_w": err_w, "threshold_s": threshold}


def main() -> None:
    case = run_case("baseline", BASE)
    save_csv(OUT / "two_node_baseline.csv", case["result"])
    plt.figure()
    plt.plot(case["result"]["time_s"], case["result"]["component_C"], label="Component")
    plt.plot(case["result"]["time_s"], case["result"]["wall_C"], label="Wall")
    plt.axhline(BASE.ambient_C, linestyle="--", label="Ambient")
    plt.axhline(case["ss_c"], linestyle=":", label="Component steady state")
    plt.xlabel("Time [s]")
    plt.ylabel("Temperature [°C]")
    plt.title("Stage 2 Two-Node Thermal Response")
    plt.legend()
    plt.grid(True, alpha=0.25)
    plt.tight_layout()
    plt.savefig(OUT / "two_node_baseline.png", dpi=160)
    plt.close()

    scenarios = {
        "low_Rcond": BASE.with_changes(conduction_thickness_m=0.0005, dt_s=0.1),
        "high_Rcond": BASE.with_changes(conduction_thickness_m=0.008),
        "low_Rconv": BASE.with_changes(convection_h_W_per_m2K=20.0),
        "high_Rconv": BASE.with_changes(convection_h_W_per_m2K=5.0),
        "low_Q": BASE.with_changes(heat_generation_W=2.5),
        "high_Q": BASE.with_changes(heat_generation_W=7.5),
    }
    cases = [run_case(name, p) for name, p in scenarios.items()]
    plt.figure()
    for c in cases:
        plt.plot(c["result"]["time_s"], c["result"]["component_C"], label=f'{c["name"]} component')
        plt.plot(c["result"]["time_s"], c["result"]["wall_C"], linestyle="--", label=f'{c["name"]} wall')
    plt.xlabel("Time [s]")
    plt.ylabel("Temperature [°C]")
    plt.title("Stage 2 Scenario Comparison (illustrative)")
    plt.legend(fontsize=7, ncol=2)
    plt.grid(True, alpha=0.25)
    plt.tight_layout()
    plt.savefig(OUT / "two_node_scenarios.png", dpi=160)
    plt.close()

    with (OUT / "two_node_scenarios.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["scenario", "R_cond_K_per_W", "R_conv_K_per_W", "Q_W", "component_ss_C", "wall_ss_C", "threshold_35C_s"])
        for c in [case] + cases:
            p = c["params"]
            w.writerow([c["name"], p.R_cond_K_per_W, p.R_conv_K_per_W, p.heat_generation_W, c["ss_c"], c["ss_w"], c["threshold_s"]])

    print("=" * 72)
    print("Two-node component + enclosure-wall thermal simulation")
    print(f"R_cond = {BASE.R_cond_K_per_W:.6g} K/W, R_conv = {BASE.R_conv_K_per_W:.6g} K/W")
    print(f"Steady state: component = {case['ss_c']:.6f} °C, wall = {case['ss_w']:.6f} °C")
    print(f"Numerical final: component = {case['result']['component_C'][-1]:.6f} °C, wall = {case['result']['wall_C'][-1]:.6f} °C")
    print(f"Max analytical error: component = {case['err_c']:.3e} K, wall = {case['err_w']:.3e} K")
    threshold_a = analytical_threshold_time(BASE, THRESHOLD_C)
    threshold_text = f"{case['threshold_s']:.3f} s" if case['threshold_s'] is not None else "not reached"
    threshold_a_text = f"{threshold_a:.3f} s" if threshold_a is not None else "not reached"
    print(f"{THRESHOLD_C:.0f} °C component threshold: {threshold_text} (numerical)")
    print(f"{THRESHOLD_C:.0f} °C component threshold: {threshold_a_text} (analytical)")
    print(f"Saved: {OUT / 'two_node_baseline.csv'}")
    print(f"Saved: {OUT / 'two_node_baseline.png'}")
    print(f"Saved: {OUT / 'two_node_scenarios.csv'}")
    print(f"Saved: {OUT / 'two_node_scenarios.png'}")


if __name__ == "__main__":
    main()
