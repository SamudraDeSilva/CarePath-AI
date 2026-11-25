# CarePath-AI | Phase 1 requirements baseline
Version 0.1.0 · Research prototype · Synthetic only

## Functional requirements and traceability
| ID | Requirement | Phase 1 implementation / verification |
|---|---|---|
| F01 | Initialise persistent relational database and version | schema.sql; integrity and repeat initialisation tests |
| F02 | Unique patient and appointment IDs, one-to-many relationships | Primary and foreign keys; duplicate and orphan tests |
| F03 | Store survey answers, barriers, predictions and model versions | surveys, barriers, predictions, model_registry; demo fixtures |
| F04 | Propose and review interventions | propose/decide, role checks, immutable decision, state triggers |
| F05 | Enforce separate staff reviewer approval | coordinator, inactive reviewer and direct status bypass tests |
| F06 | Simulate consent-aware SMS with deduplication | simulate_sms and SQL constraints; opt-in, replay and mismatch tests |
| F07 | Simulate approved transport referral and booking | create_referral/simulate_booking; consent, eligibility and pickup tests |
| F08 | Record operational audit events and transaction failures | audit_events, append-only triggers, rollback test, Python logger |
| F09 | Expose appointment overview for later dashboard | appointment_overview view and notebook output |
| F10 | Reserve future model/explanation/causal metadata | model_registry, predictions.explanation_json, interventions.estimated_benefit; no trained model yet |

## Non-functional requirements
- Reproducibility: deterministic synthetic identifiers, repeatable setup, tests on isolated databases, no external calls.
- Integrity: SQL constraints and foreign keys on every service connection, explicit schema version, atomic workflow transactions.
- Privacy: no actual identifiers or telephone numbers; fixtures are invented. No patient record uploads. Synthetic flag alone cannot verify data provenance.
- Safety: no live SMS, bookings, clinical diagnosis or emergency dispatch. Human decision recorded for consequential interventions. Transport eligibility is a demo flag, not an NHS eligibility determination.
- Access control: four roles (admin, reviewer, coordinator, analyst); actor IDs asserted by the demo caller. Not authentication, not a secure multi-user deployment.
- Auditability: service-level event log plus database append-only protections. Not cryptographically tamper-proof; direct file access can bypass protections. Initial fixture data is logged as one seed event.
- Maintainability: separate SQL, configuration, Python functions, notebook and automated tests. Later phases should add migrations rather than silently altering existing tables.
- Time: use UTC ISO timestamps with Z for application inputs; SQLite normalises timestamps for pickup comparison. Production timezone validation remains pending.
- Performance: no production throughput or availability guarantees; indexes on common access patterns; benchmark with Phase 2 data.

## Roles
| Role | Propose / send simulated SMS / referral / booking | Approve or reject | Read via local notebook |
|---|---|---|---|
| Admin | Yes | Yes | Yes |
| Reviewer | Yes | Yes | Yes |
| Coordinator | Yes | No | Yes |
| Analyst | No | No | Yes |

These permissions apply to the implemented service functions; the database file is not a security boundary. Independent clinical/administrative approval rules and authenticated identities must be designed before any deployment.

## Deferred scope
Real data ingestion, trained models, patient-facing survey and chatbot, Causal AI, autonomous agents, live APIs, dashboard UI, authentication, encryption, access monitoring, backup and restore policy, clinical safety and regulatory assurance are outside Phase 1. No production readiness or clinical efficacy is claimed.
