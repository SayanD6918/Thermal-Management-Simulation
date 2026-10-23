# Stage 3 — Thermal Parameter Studies and Engineering Validation

Stage 3 extends the validated Stage 2 two-node model with reproducible parameter
studies and an engineering applicability check. The Stage 1 and Stage 2 model
interfaces are preserved.

## 1. Scope

The following quantities are studied independently around the Stage 2 baseline:

| Parameter | Study values | Rationale |
|---|---|---|
| Heat generation | 1, 2.5, 5, 7.5, 10 W | Illustrative low-to-high electronics heat-load sweep; not a product rating. |
| Ambient temperature | 15, 25, 35, 45, 55 °C | Separates environmental temperature from heat-load effects. |
| Conduction thickness / R_cond | 0.5, 1, 2, 4, 8 mm with fixed k and area | Demonstrates the direct `R_cond = L/(kA)` effect. |
| Convection coefficient | 5, 10, 20, 40, 80 W/(m² K) | Illustrative weak-to-strong convection range; actual `h` depends on flow regime, geometry and properties. |
| Convection area | 0.015, 0.0225, 0.03, 0.06, 0.09 m² | Isolates the `R_conv = 1/(hA)` effect. |
| Component capacitance | 22.5, 45, 90, 180 J/K | Implemented by changing component mass while holding `cp` fixed. Demonstrates transient inertia. |
| Wall capacitance | 90, 180, 360, 720 J/K | Implemented by changing wall mass while holding `cp` fixed. |
| Conduction conductivity | 5, 10, 25, 50, 155 W/(m K) | 5–50 are illustrative sensitivity values; 155 W/(m K) is approximately an Al 6061-T6 reference near room temperature from NIST. |

The baseline remains:

- `Q_gen = 5 W`
- `Cc = 45 J/K`
- `Cw = 180 J/K`
- `R_cond = 0.02 K/W`
- `R_conv = 3.3333 K/W`
- `T_inf = Tc,0 = Tw,0 = 25 °C`

All study values are assumptions unless explicitly identified as reference
property data. They are not experimental operating limits.

## 2. Analytical trend checks

The two-node steady-state equations are

`Tc,ss = T_inf + Q_gen (R_cond + R_conv)`

`Tw,ss = T_inf + Q_gen R_conv`.

Therefore:

- increasing `Q_gen` increases both temperatures linearly;
- increasing `T_inf` shifts both temperatures by the same amount;
- increasing `R_cond` raises `Tc,ss` but leaves `Tw,ss` unchanged;
- increasing `R_conv` raises both steady-state temperatures;
- increasing convection area reduces `R_conv` and therefore lowers both steady-state temperatures;
- changing either thermal capacitance changes the transient response but not steady state;
- increasing conduction conductivity lowers `R_cond` and therefore lowers `Tc,ss`, while leaving `Tw,ss` unchanged.

The generated sensitivity plots show these trends without fitting arbitrary
correction factors to the results.

## 3. Numerical verification

For representative low/high endpoints of every study, the RK4 result was
compared with the independent Stage 2 eigenvalue/eigenvector analytical
solution. The largest observed errors were:

- component: `1.888e-6 K`
- wall: `4.727e-7 K`

A conservative RK4 time step is automatically selected for study cases with a
fast conduction mode. This avoids using an unnecessarily large fixed step when
material conductivity or component capacitance makes the internal mode much
faster.

## 4. Biot-number applicability check

For lumped-capacitance analysis, a commonly used criterion is

`Bi = h L_c / k < 0.1`,

where a convenient characteristic length is `L_c = V/A_s`. This criterion is a
check on internal conduction relative to surface convection; it does **not**
validate the complete enclosure model, the selected `h`, contact resistance,
geometry, or boundary conditions.

For an illustrative Al 6061-T6 wall reference:

- wall mass = `0.20 kg`
- density = `2700 kg/m³`
- convection area = `0.03 m²`
- `V = m/rho = 7.407e-5 m³`
- `L_c = V/A = 0.002469 m`
- `h = 10 W/(m² K)`
- `k ≈ 154.37 W/(m K)` near 293 K
- calculated `Bi = 1.599e-4`

This is well below 0.1, so the **wall-node lumped-temperature assumption is
supported for this illustrative geometry/property combination**. It does not
establish that the actual enclosure wall has this material, geometry or heat
transfer coefficient.

The current component-to-wall model uses an effective conduction resistance,
not an external convection coefficient at the component surface. Consequently,
a classical external-convection Biot check for the component is not established
by the current inputs and is not claimed here.

## 5. Physical-property references

### Aluminum 6061-T6 thermal properties

NIST provides temperature-dependent fitted thermal-conductivity and specific-
heat data for Al 6061-T6 over its stated data range. Evaluating those fits near
293.15 K gives approximately:

- `k = 154.37 W/(m K)`
- `cp = 943.13 J/(kg K)`

These values are used only as a reference for the engineering applicability
check and material-conductivity comparison. The Stage 2 baseline wall remains
an illustrative `k = 10 W/(m K)`, `cp = 900 J/(kg K)` model and is not silently
replaced with aluminum.

Reference: NIST, Aluminum 6061-T6 thermal-property data.

### Standard atmosphere

The altitude study uses the 1976 U.S. Standard Atmosphere tropospheric equations
for a reproducible environmental scenario. The model is not a weather forecast.
At 0, 5 and 10 km the calculated reference conditions are approximately:

| Altitude | T_inf | Pressure | Density |
|---:|---:|---:|---:|
| 0 km | 15.0 °C | 101.325 kPa | 1.2250 kg/m³ |
| 5 km | -17.5 °C | 54.020 kPa | 0.7361 kg/m³ |
| 10 km | -50.0 °C | 26.436 kPa | 0.4127 kg/m³ |

Source: NASA/NOAA/USAF 1976 Standard Atmosphere.

## 6. High-altitude convection assumption

Altitude is **not** converted directly into a universal `h` value.

For this controlled study only, the representative forced-convection coefficient
is scaled as

`h/h_0 = sqrt(rho/rho_0)`.

This follows an explicitly simplified fixed-velocity/fixed-geometry scaling
assumption in which the Reynolds-number dependence is represented by a square-
root density dependence while other correlation factors are held fixed.

Under that assumption:

- `h(0 km) = 10.000 W/(m² K)`
- `h(5 km) = 7.752 W/(m² K)`
- `h(10 km) = 5.804 W/(m² K)`.

The resulting lower steady-state temperatures in the study are dominated by
the much lower standard-atmosphere ambient temperature, not by an assertion that
high altitude inherently improves cooling. Different velocity, geometry,
orientation, flow regime, natural/forced convection, humidity and air-property
assumptions can produce different `h` values.

## 7. Generated outputs

- `outputs/stage3_parameter_summary.csv` — 38 study cases.
- `outputs/stage3_steady_state_sensitivity.png` — steady-state sensitivity plots.
- `outputs/stage3_threshold_sensitivity.png` — 35 °C threshold-time plots.
- `outputs/stage3_transient_comparisons.png` — selected component transient curves.
- `outputs/stage3_material_conductivity.png` — conduction-conductivity comparison.
- `outputs/stage3_high_altitude.csv` — standard-atmosphere scenario table.
- `outputs/stage3_high_altitude.png` — altitude scenario plot.
- `outputs/stage3_biot_check.csv` — wall Biot calculation.
- `outputs/stage3_numerical_verification.csv` — analytical-vs-numerical endpoint errors.

A blank threshold field means that the component did not cross 35 °C during the
analytical response; in cases starting at or above 35 °C, the study does not
interpret the result as a future upward crossing.

## 8. Limitations

- The model remains a two-node lumped model.
- No 3-D temperature gradients, CFD, FEM, radiation, internal-air node,
  contact-resistance submodel, or additional heat paths were introduced.
- `h` is an input/scenario assumption rather than a solved convection
  correlation in the two-node model.
- Material conductivity is varied independently of mass and specific heat in
  the conductivity sensitivity study; this isolates the resistance effect and
  is not a complete material substitution study.
- Standard-atmosphere conditions are idealized reference conditions and not
  measured local environmental conditions.
- No experimental validation was performed or claimed.
- No manufacturer performance limits were inferred.

## 9. Commands executed

Baseline regression before editing:

```text
python -m pytest -q
68 passed
```

After Stage 3 changes:

```text
python -m pytest -q
80 passed
```

Parameter-study execution:

```text
python stage3_parameter_studies.py
```

Result: exit code 0; 38 parameter-study rows generated, plots and CSV files
written successfully, and representative numerical/analytical endpoint errors
reported as above.
