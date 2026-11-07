# Omnichannel Order Fulfilment Platform – CSA10 Assignment 2

Validation prototype (Python 3, SQLite, simulated payment gateway and courier; synthetic data only).

Run the 15 validation scenarios:

    python3 run_validation.py results.json

Files: `ofp.py` (core), `edge.py` (edge sync agent), `invariants.py` (invariants I1-I8),
`run_validation.py` (scenarios V1-V11, W1-W4), `run_v1_firstpass.log` / `run_v2.log` (run 1 and final run),
`dm.py`, `diagrams1-3.py` (UML / architecture diagram scripts, need matplotlib; create an `img/` folder first),
`requirements_jira_import.csv`, `tests_jira_import.csv` (Jira import files).
