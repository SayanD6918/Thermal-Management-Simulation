"""
Environmental Hardening & Ruggedized System Design
A software-only requirements, screening-risk, mitigation, and reporting module.

Integration:
    from ruggedization_module import render_ruggedization_module
    render_ruggedization_module()

Run the whole module by itself:
    streamlit run ruggedization_module.py
"""

from __future__ import annotations

from datetime import datetime
from io import StringIO
from typing import Any

import pandas as pd
import streamlit as st


REQUIREMENT_COLUMNS = [
    "ID", "Category", "Requirement", "Acceptance criteria",
    "Verification method", "Evidence status", "Owner", "Notes"
]
RISK_COLUMNS = [
    "ID", "Environmental concern", "Potential effect",
    "Likelihood (1-5)", "Impact (1-5)", "Existing controls",
    "Mitigation ID", "Evidence status", "Owner", "Notes"
]
MITIGATION_COLUMNS = [
    "ID", "Related risk ID", "Proposed action", "Owner",
    "Status", "Due date", "Evidence / reference", "Notes"
]

EVIDENCE_STATUSES = ["Assumed", "Estimated", "Documented", "Verified", "Unknown"]
MITIGATION_STATUSES = ["Not started", "In progress", "Blocked", "Complete", "Not applicable"]


def _seed_data() -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Illustrative starter rows; replace them with project-specific reviewed inputs."""
    requirements = [
        {
            "ID": "REQ-001", "Category": "Temperature",
            "Requirement": "Document the expected operating temperature range.",
            "Acceptance criteria": "A justified minimum and maximum temperature range is recorded.",
            "Verification method": "Review component/environmental specifications",
            "Evidence status": "Assumed", "Owner": "", "Notes": "Replace with project-specific values."
        },
        {
            "ID": "REQ-002", "Category": "Ingress protection",
            "Requirement": "Document the intended dust and moisture exposure.",
            "Acceptance criteria": "Exposure assumptions and the required enclosure protection are documented.",
            "Verification method": "Design review and applicable test evidence",
            "Evidence status": "Unknown", "Owner": "", "Notes": "Do not claim a protection rating without evidence."
        },
        {
            "ID": "REQ-003", "Category": "Mechanical environment",
            "Requirement": "Identify expected handling, vibration, and transport conditions.",
            "Acceptance criteria": "Relevant conditions and an appropriate verification plan are recorded.",
            "Verification method": "Requirements review; qualified test plan if applicable",
            "Evidence status": "Unknown", "Owner": "", "Notes": ""
        },
    ]
    risks = [
        {
            "ID": "RISK-001", "Environmental concern": "Low ambient temperature",
            "Potential effect": "Material properties, battery performance, or electronics may change.",
            "Likelihood (1-5)": 3, "Impact (1-5)": 3,
            "Existing controls": "Not yet assessed", "Mitigation ID": "MIT-001",
            "Evidence status": "Assumed", "Owner": "", "Notes": "Illustrative screening entry only."
        },
        {
            "ID": "RISK-002", "Environmental concern": "Dust or moisture exposure",
            "Potential effect": "Ingress may affect connectors, surfaces, or electrical reliability.",
            "Likelihood (1-5)": 3, "Impact (1-5)": 4,
            "Existing controls": "Not yet assessed", "Mitigation ID": "MIT-002",
            "Evidence status": "Assumed", "Owner": "", "Notes": "Illustrative screening entry only."
        },
    ]
    mitigations = [
        {
            "ID": "MIT-001", "Related risk ID": "RISK-001",
            "Proposed action": "Check operating/storage limits in relevant component datasheets and record evidence.",
            "Owner": "", "Status": "Not started", "Due date": "",
            "Evidence / reference": "", "Notes": "Use manufacturer documentation; do not infer qualification."
        },
        {
            "ID": "MIT-002", "Related risk ID": "RISK-002",
            "Proposed action": "Document enclosure and connector protection requirements, then identify suitable verification evidence.",
            "Owner": "", "Status": "Not started", "Due date": "",
            "Evidence / reference": "", "Notes": "No rating is assumed by this example."
        },
    ]
    return requirements, risks, mitigations


def _initialise_state() -> None:
    if "rugged_requirements" not in st.session_state:
        req, risks, mits = _seed_data()
        st.session_state.rugged_requirements = req
        st.session_state.rugged_risks = risks
        st.session_state.rugged_mitigations = mits


def _next_id(prefix: str, records: list[dict[str, Any]]) -> str:
    numbers = []
    for row in records:
        raw = str(row.get("ID", ""))
        if raw.startswith(prefix + "-"):
            try:
                numbers.append(int(raw.split("-")[-1]))
            except ValueError:
                pass
    return f"{prefix}-{max(numbers, default=0) + 1:03d}"


def _score(likelihood: Any, impact: Any) -> int:
    return int(likelihood) * int(impact)


def _band(score: int) -> str:
    # These bands are configurable project-screening conventions, not a standard.
    if score >= 16:
        return "High screening priority"
    if score >= 8:
        return "Medium screening priority"
    return "Lower screening priority"


def _normalise_risks(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalised = []
    for source in records:
        row = {col: source.get(col, "") for col in RISK_COLUMNS}
        try:
            row["Likelihood (1-5)"] = max(1, min(5, int(row["Likelihood (1-5)"])))
        except (ValueError, TypeError):
            row["Likelihood (1-5)"] = 1
        try:
            row["Impact (1-5)"] = max(1, min(5, int(row["Impact (1-5)"])))
        except (ValueError, TypeError):
            row["Impact (1-5)"] = 1
        normalised.append(row)
    return normalised


def _risk_dataframe(records: list[dict[str, Any]]) -> pd.DataFrame:
    rows = _normalise_risks(records)
    output = []
    for row in rows:
        score = _score(row["Likelihood (1-5)"], row["Impact (1-5)"])
        output.append({
            **row,
            "Screening score (L × I)": score,
            "Screening priority": _band(score),
        })
    columns = RISK_COLUMNS + ["Screening score (L × I)", "Screening priority"]
    return pd.DataFrame(output, columns=columns)


def _csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8-sig")


def _report_text() -> str:
    requirements = pd.DataFrame(st.session_state.rugged_requirements, columns=REQUIREMENT_COLUMNS)
    risks = _risk_dataframe(st.session_state.rugged_risks)
    mitigations = pd.DataFrame(st.session_state.rugged_mitigations, columns=MITIGATION_COLUMNS)

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        "ENVIRONMENTAL HARDENING & RUGGEDIZED SYSTEM DESIGN",
        f"Generated: {now}",
        "",
        "SCOPE AND IMPORTANT LIMITATIONS",
        "This report is a software-based planning and review aid. It does not certify a design,",
        "demonstrate compliance, or establish a validated probability of failure.",
        "Risk screening score = Likelihood (1-5) × Impact (1-5), range 1-25.",
        "Screening bands used by this app: 1-7 lower, 8-15 medium, 16-25 high priority.",
        "These bands are project conventions, not a standard. Scores are prioritization aids only.",
        "Evidence status must be distinguished: Assumed, Estimated, Documented, Verified, Unknown.",
        "Any claim of compliance requires applicable requirements and valid evidence reviewed by a qualified person.",
        "",
        "1. REQUIREMENTS REGISTER",
        requirements.to_string(index=False) if not requirements.empty else "No requirements entered.",
        "",
        "2. RISK REGISTER",
        risks.to_string(index=False) if not risks.empty else "No risks entered.",
        "",
        "3. MITIGATION TRACKER",
        mitigations.to_string(index=False) if not mitigations.empty else "No mitigations entered.",
        "",
        "REVIEW CHECKLIST",
        "- Confirm environmental assumptions and their sources.",
        "- Replace illustrative starter entries with project-specific requirements.",
        "- Assign owners and due dates.",
        "- Link each mitigation to evidence and verify closure.",
        "- Review requirements, risks, and evidence with the project supervisor.",
        "- Do not treat this software report as certification or a substitute for qualification testing.",
    ]
    return "\n".join(lines)


def render_ruggedization_module() -> None:
    """Render the complete module inside an existing Streamlit app."""
    _initialise_state()

    st.header("Environmental Hardening & Ruggedized System Design")
    st.write(
        "Record environmental requirements, screen potential concerns, track mitigation actions, "
        "and export a review report."
    )
    st.warning(
        "Screening tool only: scores are not failure probabilities or certification. "
        "Starter rows are illustrative assumptions and must be reviewed or replaced."
    )

    requirements_tab, risks_tab, mitigations_tab, report_tab = st.tabs(
        ["1 · Requirements", "2 · Risk assessment", "3 · Mitigations", "4 · Reports & export"]
    )

    with requirements_tab:
        st.subheader("Environmental requirements register")
        with st.form("rugged_add_requirement", clear_on_submit=True):
            a, b = st.columns(2)
            category = a.selectbox(
                "Category",
                ["Temperature", "Thermal cycling", "Dust / moisture", "Low pressure / altitude",
                 "Wind / mechanical loads", "Vibration / shock", "Electrical / component limits",
                 "Connectors / cabling", "Monitoring / maintainability", "Other"],
            )
            req_text = b.text_input("Requirement", placeholder="What condition or capability must be addressed?")
            criteria = st.text_area("Acceptance criteria", placeholder="How will the requirement be judged?")
            c, d = st.columns(2)
            method = c.text_input("Verification method", placeholder="e.g. document review, analysis, qualified test")
            evidence = d.selectbox("Evidence status", EVIDENCE_STATUSES, key="req_evidence_new")
            e, f = st.columns(2)
            owner = e.text_input("Owner")
            notes = f.text_input("Notes / source")
            add_req = st.form_submit_button("Add requirement")
        if add_req:
            if not req_text.strip():
                st.error("Enter a requirement before adding it.")
            else:
                st.session_state.rugged_requirements.append({
                    "ID": _next_id("REQ", st.session_state.rugged_requirements),
                    "Category": category, "Requirement": req_text.strip(),
                    "Acceptance criteria": criteria.strip(), "Verification method": method.strip(),
                    "Evidence status": evidence, "Owner": owner.strip(), "Notes": notes.strip(),
                })
                st.success("Requirement added.")

        st.caption("You can edit cells in the table and then save your edits.")
        req_df = pd.DataFrame(st.session_state.rugged_requirements, columns=REQUIREMENT_COLUMNS)
        edited_req = st.data_editor(
            req_df, key="rugged_req_editor", num_rows="fixed", use_container_width=True,
            hide_index=True,
            column_config={
                "Evidence status": st.column_config.SelectboxColumn(
                    "Evidence status", options=EVIDENCE_STATUSES, required=True
                ),
                "ID": st.column_config.TextColumn("ID", disabled=True),
            },
        )
        if st.button("Save requirements table edits", key="save_rugged_req"):
            st.session_state.rugged_requirements = edited_req.fillna("").to_dict("records")
            st.success("Requirements register updated.")
        if st.session_state.rugged_requirements:
            req_ids = [str(r.get("ID", "")) for r in st.session_state.rugged_requirements]
            req_to_delete = st.selectbox("Remove a requirement", ["— Select —"] + req_ids, key="delete_req_select")
            if st.button("Delete selected requirement", key="delete_req_btn"):
                if req_to_delete != "— Select —":
                    st.session_state.rugged_requirements = [
                        r for r in st.session_state.rugged_requirements if str(r.get("ID", "")) != req_to_delete
                    ]
                    st.rerun()

    with risks_tab:
        st.subheader("Risk assessment")
        st.markdown(
            "**Screening score = Likelihood × Impact.** Rate both from 1 (low) to 5 (high). "
            "The result is a simple screening score used to help prioritize review—not a probability "
            "of failure, a validated reliability metric, or a compliance result."
        )
        with st.expander("Scoring guide"):
            st.markdown(
                "- **Likelihood 1–5:** your team's qualitative estimate of how plausible the concern is "
                "under the stated assumptions.\n"
                "- **Impact 1–5:** your team's qualitative estimate of consequence if it occurs.\n"
                "- **1–7:** lower screening priority; **8–15:** medium; **16–25:** high.\n\n"
                "The bands are configurable project conventions, not prescribed by a standard. "
                "Record the reasoning and evidence behind each rating."
            )
        with st.form("rugged_add_risk", clear_on_submit=True):
            concern = st.text_input("Environmental concern", placeholder="e.g. thermal cycling")
            effect = st.text_area("Potential effect", placeholder="Describe a general reliability or maintainability concern")
            lcol, icol = st.columns(2)
            likelihood = lcol.selectbox("Likelihood (1–5)", [1, 2, 3, 4, 5], index=2)
            impact = icol.selectbox("Impact (1–5)", [1, 2, 3, 4, 5], index=2)
            controls = st.text_input("Existing controls / current evidence")
            risk_mitigation_id = st.text_input("Related mitigation ID (optional)")
            risk_evidence = st.selectbox("Evidence status", EVIDENCE_STATUSES, key="risk_evidence_new")
            r_owner = st.text_input("Owner", key="risk_owner_new")
            r_notes = st.text_input("Notes / rating rationale", key="risk_notes_new")
            add_risk = st.form_submit_button("Add risk")
        if add_risk:
            if not concern.strip():
                st.error("Enter an environmental concern before adding it.")
            else:
                st.session_state.rugged_risks.append({
                    "ID": _next_id("RISK", st.session_state.rugged_risks),
                    "Environmental concern": concern.strip(), "Potential effect": effect.strip(),
                    "Likelihood (1-5)": int(likelihood), "Impact (1-5)": int(impact),
                    "Existing controls": controls.strip(), "Mitigation ID": risk_mitigation_id.strip(),
                    "Evidence status": risk_evidence, "Owner": r_owner.strip(), "Notes": r_notes.strip(),
                })
                st.success("Risk added.")

        risk_df = _risk_dataframe(st.session_state.rugged_risks)
        st.dataframe(risk_df, use_container_width=True, hide_index=True)
        st.caption("To change a risk rating or its details, edit the table below and save. The screening score is recalculated.")
        editable_risk_cols = pd.DataFrame(_normalise_risks(st.session_state.rugged_risks), columns=RISK_COLUMNS)
        edited_risks = st.data_editor(
            editable_risk_cols, key="rugged_risk_editor", num_rows="fixed", use_container_width=True,
            hide_index=True,
            column_config={
                "ID": st.column_config.TextColumn("ID", disabled=True),
                "Likelihood (1-5)": st.column_config.NumberColumn("Likelihood (1–5)", min_value=1, max_value=5, step=1, required=True),
                "Impact (1-5)": st.column_config.NumberColumn("Impact (1–5)", min_value=1, max_value=5, step=1, required=True),
                "Evidence status": st.column_config.SelectboxColumn("Evidence status", options=EVIDENCE_STATUSES, required=True),
            },
        )
        if st.button("Save risk table edits", key="save_rugged_risks"):
            st.session_state.rugged_risks = _normalise_risks(edited_risks.fillna("").to_dict("records"))
            st.success("Risk register updated. Screening scores recalculate from the saved ratings.")
        if st.session_state.rugged_risks:
            risk_ids = [str(r.get("ID", "")) for r in st.session_state.rugged_risks]
            risk_to_delete = st.selectbox("Remove a risk", ["— Select —"] + risk_ids, key="delete_risk_select")
            if st.button("Delete selected risk", key="delete_risk_btn"):
                if risk_to_delete != "— Select —":
                    st.session_state.rugged_risks = [
                        r for r in st.session_state.rugged_risks if str(r.get("ID", "")) != risk_to_delete
                    ]
                    st.rerun()

    with mitigations_tab:
        st.subheader("Mitigation tracker")
        with st.form("rugged_add_mitigation", clear_on_submit=True):
            m_related = st.text_input("Related risk ID", placeholder="e.g. RISK-001")
            action = st.text_area("Proposed action", placeholder="Describe a review, documentation, design assurance, or verification action")
            m1, m2 = st.columns(2)
            m_owner = m1.text_input("Owner", key="mit_owner_new")
            status = m2.selectbox("Status", MITIGATION_STATUSES)
            m3, m4 = st.columns(2)
            due_date = m3.text_input("Due date", placeholder="YYYY-MM-DD (optional)")
            reference = m4.text_input("Evidence / reference", placeholder="Document name, test record, datasheet, etc.")
            m_notes = st.text_input("Notes", key="mit_notes_new")
            add_mit = st.form_submit_button("Add mitigation")
        if add_mit:
            if not action.strip():
                st.error("Enter a mitigation action before adding it.")
            else:
                st.session_state.rugged_mitigations.append({
                    "ID": _next_id("MIT", st.session_state.rugged_mitigations),
                    "Related risk ID": m_related.strip(), "Proposed action": action.strip(),
                    "Owner": m_owner.strip(), "Status": status, "Due date": due_date.strip(),
                    "Evidence / reference": reference.strip(), "Notes": m_notes.strip(),
                })
                st.success("Mitigation added.")

        mit_df = pd.DataFrame(st.session_state.rugged_mitigations, columns=MITIGATION_COLUMNS)
        edited_mits = st.data_editor(
            mit_df, key="rugged_mit_editor", num_rows="fixed", use_container_width=True,
            hide_index=True,
            column_config={
                "ID": st.column_config.TextColumn("ID", disabled=True),
                "Status": st.column_config.SelectboxColumn("Status", options=MITIGATION_STATUSES, required=True),
            },
        )
        if st.button("Save mitigation table edits", key="save_rugged_mits"):
            st.session_state.rugged_mitigations = edited_mits.fillna("").to_dict("records")
            st.success("Mitigation tracker updated.")
        if st.session_state.rugged_mitigations:
            mit_ids = [str(m.get("ID", "")) for m in st.session_state.rugged_mitigations]
            mit_to_delete = st.selectbox("Remove a mitigation", ["— Select —"] + mit_ids, key="delete_mit_select")
            if st.button("Delete selected mitigation", key="delete_mit_btn"):
                if mit_to_delete != "— Select —":
                    st.session_state.rugged_mitigations = [
                        m for m in st.session_state.rugged_mitigations if str(m.get("ID", "")) != mit_to_delete
                    ]
                    st.rerun()

    with report_tab:
        st.subheader("Project report and downloads")
        req_df = pd.DataFrame(st.session_state.rugged_requirements, columns=REQUIREMENT_COLUMNS)
        risks_df = _risk_dataframe(st.session_state.rugged_risks)
        mits_df = pd.DataFrame(st.session_state.rugged_mitigations, columns=MITIGATION_COLUMNS)

        c1, c2, c3 = st.columns(3)
        c1.metric("Requirements", len(req_df))
        c2.metric("Risks", len(risks_df))
        c3.metric("Mitigation actions", len(mits_df))

        if not risks_df.empty:
            high = int((risks_df["Screening priority"] == "High screening priority").sum())
            medium = int((risks_df["Screening priority"] == "Medium screening priority").sum())
            low = int((risks_df["Screening priority"] == "Lower screening priority").sum())
            st.write(f"Current screening summary: **{high} high**, **{medium} medium**, **{low} lower-priority** item(s).")
            st.caption("This summary is only as reliable as the qualitative ratings and evidence entered by the team.")

        st.download_button(
            "Download requirements CSV", data=_csv_bytes(req_df),
            file_name="environmental_requirements.csv", mime="text/csv",
            disabled=req_df.empty, use_container_width=True,
        )
        st.download_button(
            "Download risk register CSV", data=_csv_bytes(risks_df),
            file_name="environmental_risk_register.csv", mime="text/csv",
            disabled=risks_df.empty, use_container_width=True,
        )
        st.download_button(
            "Download mitigation tracker CSV", data=_csv_bytes(mits_df),
            file_name="mitigation_tracker.csv", mime="text/csv",
            disabled=mits_df.empty, use_container_width=True,
        )
        st.download_button(
            "Download consolidated TXT report", data=_report_text().encode("utf-8"),
            file_name="environmental_hardening_report.txt", mime="text/plain",
            use_container_width=True,
        )

        st.markdown("#### Report preview")
        st.text(_report_text())


if __name__ == "__main__":
    st.set_page_config(page_title="Environmental Hardening Module", layout="wide")
    st.title("Environmental Hardening & Ruggedized System Design")
    render_ruggedization_module()
