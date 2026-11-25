# Phase 1 data dictionary
`schema.sql` is authoritative for all columns, types, defaults and constraints. IDs are opaque fictional strings; timestamps are UTC; nullable answers mean unknown, not negative.

| Table | Grain / primary key | Main contents |
|---|---|---|
| schema_version | One schema version | Version and installation timestamp |
| staff | staff_id | Demo display name, role, active flag |
| patients | patient_id | Age band, fictional contact token, SMS opt-in, synthetic flag |
| appointments | appointment_id | Patient FK, scheduled time, department, type, status |
| surveys | survey_id | Appointment FK, confidence 0–10, binary barriers (nullable), separate support consent |
| model_registry | model_id | Model kind, version, artifact path, validation status |
| predictions | prediction_id | Appointment/model FKs, probability 0–1, timestamp, optional JSON explanation, simulation flag |
| barriers | barrier_id | Appointment FK, category, source, confirmed flag |
| interventions | intervention_id | Appointment FK, kind, rationale, status, optional synthetic effect estimate in probability units (-1 to 1) |
| intervention_decisions | decision_id | Unique intervention FK, reviewing staff FK, approve/reject, reason |
| communications | message_id | Appointment FK, optional intervention FK, channel, template key, unique dedupe key, simulated/failed status |
| transport_referrals | referral_id | Unique intervention FK, demo eligibility status, mobility notes, status |
| transport_bookings | booking_id | Unique referral FK, simulated provider, pickup timestamp, status |
| audit_events | event_id | Staff FK (nullable for system), action, entity type/id, JSON metadata, timestamp |

`appointment_overview` view: one row per appointment, including latest recorded illustrative probability (not a validated model prediction). `audit_events.entity_id` is a polymorphic reference, not an enforced FK. `support_consent` is separate from SMS opt-in; latest survey controls new transport actions. No real identifiers are required or permitted in this prototype. Future Phase 2 may extend the schema using explicit migrations.
