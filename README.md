# Thermal Management of Electronic Components Under Varying Environmental Conditions

This project is a staged engineering thermal-simulation study. Stages 1–3 provide the validated single-node model, two-node component/wall model, parameter studies, numerical/analytical verification, plots, CSV outputs, and engineering documentation.

## Stage 4 — Streamlit dashboard

`dashboard.py` provides a local Streamlit interface around the existing physics implementations. It does **not** duplicate the governing equations.

### Models

- **Single-node:** uses `thermal_model.py` / `thermal_simulation.py`.
- **Two-node:** uses `two_node_model.py` and reuses the Stage 3 conservative timestep selection from `stage3_parameter_studies.py`.

The dashboard supports:

- validated model selection and inputs;
- run/reset and documented example scenarios;
- component/wall temperature plots and analytical references;
- steady-state and threshold metrics;
- user-selected scenario comparison;
- predefined Stage 3 sensitivity-study viewing;
- CSV exports for time series, scenario comparison, and parameter configuration;
- a plain-text simulation summary;
- assumptions and limitation documentation.

## Installation

Use a Python virtual environment if desired, then install the project dependencies:

```bash
python -m pip install -r requirements.txt
```

## Run the dashboard

From the project directory:

```bash
streamlit run dashboard.py
```

The command prints a local URL, normally `http://localhost:8501`.

## Run the engineering validation suite

```bash
python -m pytest -q
python thermal_simulation.py
python two_node_simulation.py
python stage3_parameter_studies.py
```

## Scope and limitations

The application is a lumped thermal model, not a 3-D CFD or finite-element solver. Component and wall nodes are spatially uniform. Radiation, internal enclosure air, contact resistance, additional heat paths, hardware integration, cloud services, databases, accounts, and external APIs are outside the current scope. No experimental validation is claimed.

Stage 3 documents the Biot-number applicability check, physical-property references, and idealized high-altitude scenario assumptions. Low Biot number supports only the stated illustrative wall case; it does not validate the complete enclosure model.

Default dashboard values are illustrative unless explicitly identified as documented reference data.
