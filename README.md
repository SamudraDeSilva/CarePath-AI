# CarePath-AI

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

**A Human-Centred Causal and Agentic AI Framework for Healthcare Appointment Attendance**

`Python` · `Jupyter Notebook` · `SQLite` · `Research prototype`  
**v0.1.1 — Phase 1 of 12 — Synthetic data only**

## Overview
CarePath-AI investigates appointment attendance barriers, with predictive risk, causal intervention analysis and coordination under human supervision planned for future public releases. This is a research prototype, not an NHS product.

This release provides a relational SQLite foundation, reusable Python services, fictional demonstration workflows, consent checks and human approval safeguards. Risk scores are illustrative placeholders.

## Release at a glance
| Metric | Result |
| --- | ---: |
| SQLite tables | 14 |
| Demo patients | 3 |
| Automated tests passed | 28/28 |
| Foreign key violations | 0 |

Figures are from the original development reports, not real world healthcare performance.

## System architecture
![CarePath-AI foundation architecture](documentation/architecture.png)

## Quick start
Download the complete release ZIP or clone the repository to recreate generated artefacts. Open a terminal in the extracted `CarePath-AI` directory. Python 3.11 or later is recommended.

```sh
python -m venv .venv
```

Activate with `.venv\Scripts\Activate.ps1` on Windows PowerShell or `source .venv/bin/activate` on macOS/Linux. If activation is restricted, invoke the environment's Python directly.

```sh
python -m pip install -r requirements.txt
python -m notebook
```

Open `notebooks/Phase_01_Foundation.ipynb` and select **Restart Kernel and Run All Cells**. The notebook initialises the demo database. Run independent tests from the project root:

```sh
python -m unittest discover -s tests -v
```

Full ZIPs retain all generated artefacts; `.gitignore` excludes generated data, database and preprocessing files from Git. Keep the directory structure intact.

## Documentation and reproducibility
* [Foundation notebook](notebooks/Phase_01_Foundation.ipynb)
* [Requirements](documentation/requirements.md) · [Data dictionary](documentation/data_dictionary.md) · [ERD](documentation/erd.svg)
* [Foundation tests](reports/test_results.txt) · [Validation](reports/validation_report.json)

See the [changelog](CHANGELOG.md) for release history. The numerical results and test reports document the original development experiments. The automated tests and notebooks support reproducibility.

## Development roadmap
| Phase | Scope | Snapshot status |
| --- | --- | --- |
| 1 | System architecture & foundations | Implemented |
| 2 | Data engineering & patient survey | Not included |
| 3 | Predictive ML | Not included |
| 4 | Explainable AI | Not included |
| 5 | Causal AI | Not included |
| 6 | Automated communication | Not included |
| 7 | Patient chatbot | Not included |
| 8 | Agentic AI | Not included |
| 9 | Transport coordination | Not included |
| 10 | Staff dashboard | Not included |
| 11 | Integration & validation | Not included |
| 12 | Final research package | Not included |

## Responsible use and limitations
All records and intervention effects are synthetic. No trained predictive or causal estimator, real messages, bookings or NHS integration. Local SQLite is unencrypted; demo actor IDs are not authentication and direct SQL/file access can bypass controls. Not clinically validated or for actual patient decisions. Windows was not directly tested.

## Citation and contribution transparency
Please use [CITATION.cff](CITATION.cff) when citing this release. AI assistance was used in software development and documentation. The project remains a research prototype; independent adoption and research novelty have not been established.

## Research and healthcare disclaimer
CarePath-AI is an experimental research and software engineering prototype using synthetic healthcare data. It has not been clinically validated and is not intended for clinical diagnosis, medical advice, autonomous healthcare decisions or actual patient management. It is not affiliated with or endorsed by the NHS. Real-world deployment requires appropriate regulatory, ethical, clinical, privacy and security assessment and authorisation. This statement is separate from the Apache License 2.0 warranty and liability provisions.

## Licence and attribution
Copyright 2026 Samudra De Silva, to the extent copyright is held by the project author. Materials owned by the project author are licensed under the [Apache License 2.0](LICENSE). See [NOTICE](NOTICE) for attribution and third party licensing information. Third party dependencies retain their own licences.
