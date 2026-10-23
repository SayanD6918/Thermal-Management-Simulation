# Validation log — Stage 1 + Stage 2

This file records commands actually executed in the Stage 2 implementation
environment. Physical parameter values are illustrative assumptions unless
explicitly identified otherwise.

## Stage 1 baseline before editing

Command:

    python -m pytest -q test_thermal_model.py

Result:

    54 passed

Command:

    python thermal_simulation.py

Result: exit code 0. The original Stage 1 CSV and PNG were generated. The
baseline analytical values were `T_ss = 75.0 °C`, `tau = 450 s`, and the
60 °C crossing was `541.79 s`. The maximum RK4 difference from the Stage 1
analytical solution was approximately `3.70e-12 K` in this execution.

The Stage 1 files were preserved; the Stage 1 model and tests were not rewritten.

## Stage 2 implementation

Added:

- `two_node_model.py` — validated parameter dataclass, physical equations,
  steady-state equations, eigenvalue/eigenvector analytical transient,
  RK4/Euler integration, threshold crossing, energy balance diagnostics.
- `two_node_simulation.py` — baseline run, plots, CSV output, and six-case
  illustrative scenario study.
- `test_two_node_model.py` — 14 focused Stage 2 tests.
- `TWO_NODE_MODEL.md` — assumptions, equations, analytical validation,
  single-node limit, tolerances and outputs.

The Stage 1 `thermal_model.py`, `thermal_simulation.py`, and existing tests
remain available as the baseline.

## Commands and results

### Original Stage 1 tests

    python -m pytest -q test_thermal_model.py

Result: **54 passed**.

### Stage 2 tests

    python -m pytest -q test_two_node_model.py

Result: **14 passed**.

### Combined regression

    python -m pytest -q

Result: **68 passed**.

### Stage 2 simulation

    python two_node_simulation.py

Result: exit code 0. Generated both baseline and scenario CSV/PNG outputs.

### Baseline analytical comparison

Illustrative inputs:

- `Q_gen = 5 W`
- component: `m = 0.05 kg`, `cp = 900 J/(kg K)`
- wall: `m = 0.20 kg`, `cp = 900 J/(kg K)`
- `R_cond = 0.02 K/W`
- `R_conv = 3.333333 K/W`
- `T_inf = Tc,0 = Tw,0 = 25 °C`
- duration `3000 s`, RK4 `dt = 0.1 s`

Analytical steady state:

- `Tc,ss = 41.766667 °C`
- `Tw,ss = 41.666667 °C`

Numerical final temperatures at 3000 s:

- component: `41.460452 °C`
- wall: `41.360819 °C`

The difference between the numerical and analytical **transient curves** was:

- component maximum absolute error: `8.20e-8 K`
- wall maximum absolute error: `2.05e-8 K`

The final temperatures are below steady state because 3000 s is finite; the
system continues asymptotically toward the analytical values.

The illustrative 35 °C component threshold was reached at:

- numerical: `677.835 s`
- analytical: `677.835 s`

## Energy conservation

The model checks total system energy as

`generated energy = stored energy + energy convected to ambient`.

It also explicitly computes the component-to-wall conduction flux. The tests
verify that the component conduction loss and wall conduction gain are equal in
magnitude and opposite in sign at every sampled time.

The automated energy-balance test passed with relative residual below `1e-7`
for its test case.

## Sensitivity/scenario checks

The generated scenario table covers:

- low/high conduction resistance,
- low/high convection resistance,
- low/high heat generation.

The expected trends were observed: increasing `R_cond` raises component
steady-state temperature without changing the wall steady-state temperature;
increasing `R_conv` raises both steady-state temperatures; and increasing
`Q_gen` raises both steady-state temperatures.

The illustrative scenario file uses a **35 °C** threshold column named
`threshold_35C_s`; a blank entry means that threshold was not reached during
the simulated duration.

## Single-node limit

The limiting comparison was tested analytically with a small conduction
resistance. The equivalent one-node model uses **combined capacitance**
`Cc + Cw` and `R_conv`, not the Stage 1 component-only capacitance. This is the
physically consistent comparison requested for `R_cond -> 0`.

## Input validation

Stage 2 tests cover zero/negative masses, heat capacities, geometry,
conductivity, convection coefficient/area, duration/time step, negative heat
generation and invalid ambient temperature. Numerical integration also rejects
explicit steps that exceed the stability region of the fastest thermal
Eigenmode.

## Scope / limitations

- This is a two-node lumped thermal model, not a 3-D enclosure, CFD or finite
  element simulation.
- Component and wall temperatures are spatially uniform within each node.
- Properties, heat generation, ambient temperature, `h`, areas and resistances
  are constant during each run.
- Radiation, internal enclosure air, contact resistance and additional heat
  paths are excluded.
- No experimental validation or real-world performance claim is made.
- Scenario parameters are illustrative assumptions.
- Streamlit, radiation and unrelated extensions were not started in Stage 2.

## Stage 3 — parameter studies and engineering validation

### Preserve/retest before editing

Command:

    python -m pytest -q

Result before Stage 3 edits: **68 passed**.

The Stage 1 and Stage 2 model interfaces were retained. No existing model was
rewritten merely to support the studies.

### Stage 3 implementation

Added:

- `stage3_parameter_studies.py` — systematic parameter studies, selected
  transient plots, material-conductivity study, standard-atmosphere scenario,
  Biot-number check and CSV generation.
- `test_stage3_studies.py` — automated Stage 3 trend, atmosphere, Biot and
  numerical-verification tests.
- `STAGE3_ENGINEERING_VALIDATION.md` — parameter ranges, engineering rationale,
  references, assumptions, limitations and outputs.
- Updated `TWO_NODE_MODEL.md` with Stage 3 applicability notes.

### Stage 3 tests

Command:

    python -m pytest -q

Result: **80 passed**.

The increase from 68 to 80 is due to 12 new Stage 3 tests.

### Parameter studies

Command:

    python stage3_parameter_studies.py

Result: exit code 0. Generated 38 systematic study rows and the requested CSV
and PNG outputs.

Largest representative numerical-vs-independent-analytical transient errors:

- component: **1.888e-6 K**
- wall: **4.727e-7 K**

### Engineering trend validation

Automated checks confirm:

- `Q_gen` increases both steady-state temperatures.
- `T_inf` shifts both steady-state temperatures one-for-one.
- `R_cond` changes component steady state but not wall steady state.
- stronger convection (larger `h`) lowers both steady-state temperatures.
- larger convection area lowers both steady-state temperatures.
- thermal capacitance changes transient speed but not steady state.
- increasing conduction conductivity lowers component steady state but not wall steady state.

### Biot-number check

For the illustrative Al 6061-T6 wall reference:

- `rho = 2700 kg/m^3`
- `k = 154.37 W/(m K)` near 293 K
- `m_wall = 0.20 kg`
- `A_conv = 0.03 m^2`
- `h = 10 W/(m^2 K)`
- `L_c = 0.00246914 m`
- `Bi = 1.599e-4`

This is below the commonly used `Bi < 0.1` lumped-capacitance criterion. The
check applies only to the stated illustrative wall geometry/material and does
not validate the complete model.

### High-altitude scenario

The 1976 U.S. Standard Atmosphere was used for reproducible reference
conditions. For the illustrative fixed-velocity/fixed-geometry forced-
convection scaling `h/h0 = sqrt(rho/rho0)`:

- 0 km: `T_inf = 15.0 °C`, `rho = 1.2250 kg/m^3`, `h = 10.000 W/(m^2 K)`
- 5 km: `T_inf = -17.5 °C`, `rho = 0.7361 kg/m^3`, `h = 7.752 W/(m^2 K)`
- 10 km: `T_inf = -50.0 °C`, `rho = 0.4127 kg/m^3`, `h = 5.804 W/(m^2 K)`

This is an explicit scenario assumption, not a universal altitude-to-`h`
relationship.

### Physical-property references

- NIST Aluminum 6061-T6 thermal conductivity and specific heat data were used
  as a reference for the material-property applicability check. The values
  evaluated near 293.15 K are approximately `k = 154.37 W/(m K)` and
  `cp = 943.13 J/(kg K)`.
- NASA/NOAA/USAF 1976 Standard Atmosphere data/equations were used for the
  altitude environmental scenario.

No experimental measurements, manufacturer performance data, or experimental
validation were introduced.

### Plot/CSV verification

The following files were successfully written by the Stage 3 script:

- `outputs/stage3_parameter_summary.csv`
- `outputs/stage3_steady_state_sensitivity.png`
- `outputs/stage3_threshold_sensitivity.png`
- `outputs/stage3_transient_comparisons.png`
- `outputs/stage3_material_conductivity.png`
- `outputs/stage3_high_altitude.csv`
- `outputs/stage3_high_altitude.png`
- `outputs/stage3_biot_check.csv`
- `outputs/stage3_numerical_verification.csv`

The generated plots were visually inspected and the CSV schemas/content were
checked from the execution output.

## Stage 3 unresolved limitations

- No experimental validation exists.
- The two-node lumped model remains a reduced-order model rather than a 3-D
  enclosure model.
- The current model accepts `h` as an input; it does not calculate `h` from a
  detailed convection correlation.
- The high-altitude `h` scaling is deliberately simplified and should not be
  presented as a general law.
- The material-conductivity sensitivity changes `k` while holding mass and
  specific heat fixed, so it is an isolated resistance sensitivity rather than
  a full material-selection model.
- Component Biot applicability is not established because the current model
  represents component-to-wall transfer with an effective conduction
  resistance rather than a component surface-convection boundary condition.

Stage 3 stops here. Streamlit, radiation, CFD/FEM and hardware integration were
not started.

## Stage 4 — Streamlit dashboard

### Preserve/retest before editing

Commands executed before Stage 4 edits:

```text
python -m pytest -q
```

Result: **80 passed**.

```text
python stage3_parameter_studies.py
```

Result: **exit code 0**, 38 study rows regenerated. Reported maximum representative endpoint errors remained `1.888e-6 K` component and `4.727e-7 K` wall; wall Biot check remained `1.599e-4`.

```text
python thermal_simulation.py
```

Result: **exit code 0**. Stage 1 baseline completed with maximum numerical-vs-analytical error `3.695e-12 K`.

```text
python two_node_simulation.py
```

Result: **exit code 0**. Stage 2 baseline completed with maximum numerical-vs-analytical errors `8.197e-08 K` component and `2.052e-08 K` wall.

### Stage 4 implementation

Added:

- `dashboard.py` — Streamlit application entry point and UI.
- `dashboard_logic.py` — pure, testable adapters for model execution, validation, result preparation, scenario comparison, and export formatting. No physics equations are reimplemented here.
- `test_dashboard_logic.py` — Stage 4 dashboard-logic tests.
- `requirements.txt` — runtime/test dependencies including Streamlit.
- `README.md` — installation, execution, validation and scope instructions.

### Stage 4 verification

The dashboard logic was tested independently of the Streamlit UI because Streamlit was not installed in the execution environment. The environment also had no network access, so installing Streamlit with `python -m pip install streamlit -q` failed during package-index resolution.

Commands that were executed after implementation:

```text
python -m pytest -q
python thermal_simulation.py
python two_node_simulation.py
python stage3_parameter_studies.py
python -m compileall dashboard.py dashboard_logic.py
```

The test suite and model scripts completed successfully. `compileall` completed successfully.

**Not completed in this environment:** `streamlit run dashboard.py` and browser-based visual interaction testing. No claim is made that the dashboard was launched or visually inspected here. To complete the final local-launch criterion, install dependencies from `requirements.txt` in an environment with package access and run `streamlit run dashboard.py`.

### Stage 4 scope checks

- Existing Stage 1/2/3 model files were not rewritten to embed dashboard logic.
- Dashboard calculations call existing model APIs.
- CSV exports are generated from actual run arrays/results.
- Invalid model inputs are passed through the existing model validators and surfaced as readable errors.
- The dashboard explicitly distinguishes the final simulated temperature from analytical steady state and uses a documented `±0.1 K` endpoint convergence criterion.
- No CFD/FEM, radiation, hardware integration, database, cloud service, user account, or external API functionality was added.

### Final Stage 4 verification record

After the final dashboard refinements, the following checks were executed:

```text
python -m compileall -q dashboard.py dashboard_logic.py
```

Result: **exit code 0**.

```text
python -m pytest -q
```

Result: **86 passed**. This includes the original 80 Stage 1–3 tests plus 6 pure dashboard-logic tests.

```text
python thermal_simulation.py
```

Result: **exit code 0**; Stage 1 maximum numerical-vs-analytical error `3.695e-12 K`.

```text
python two_node_simulation.py
```

Result: **exit code 0**; Stage 2 maximum numerical-vs-analytical errors `8.197e-08 K` component and `2.052e-08 K` wall.

```text
python stage3_parameter_studies.py
```

Result: **exit code 0**; 38 rows generated; maximum representative endpoint errors `1.888e-06 K` component and `4.727e-07 K` wall; wall Biot `1.599e-04`.

Additional direct dashboard-logic verification confirmed that both model modes return actual time-series data, exports contain calculated values, and increasing heat generation increases both two-node steady-state temperatures.

### Streamlit launch limitation

The execution environment did not contain Streamlit. An installation attempt using:

```text
python -m pip install streamlit -q
```

failed because the environment could not resolve/access the package index. Therefore the following could **not** be honestly verified in this environment:

```text
streamlit run dashboard.py
```

and browser-based visual interaction testing. The dashboard source was syntax-compiled successfully and its non-UI logic was exercised by automated tests, but no claim is made that the Streamlit application was launched or visually inspected here.
