# Phase 2 data dictionary

All fields synthetic. Timing is relative to prediction index (48 h before visit). The observed appointment file is the canonical Phase 2 analytical export. Missing values are empty CSV cells / SQLite NULL, never negative sentinel numbers.

| Field | Type / domain | Timing and meaning |
|---|---|---|
| appointment_id | string R-A-xxxxx-n | unique fictional appointment, audit only |
| patient_id | string R-P-xxxxx | repeated fictional patient, grouping only |
| scheduled_at | UTC ISO string | scheduled visit |
| booked_at | UTC ISO string | appointment booking |
| index_at | UTC ISO string | risk prediction / offer time |
| survey_at | nullable UTC ISO | survey response at index−1 day |
| age | int 18-90 | fixed synthetic baseline age |
| age_band | category | 18-29, 30-44, 45-59, 60-74, 75+ |
| distance_km | float | fictional travel distance, km |
| lead_days | int 7-90 | booking to appointment |
| prior_appointments | int 0-5 | earlier appointments with known outcomes |
| prior_no_shows | int | prior no-shows |
| prior_cancellations | int | prior cancellations and reschedulings |
| prior_no_show_rate | float 0-1 | prior no-shows divided by all prior visits, 0 for first visit |
| appointment_hour | int 8-16 | scheduled hour UTC |
| weekday | int 0-4 | Monday-Friday |
| month | int 1-12 | scheduled month |
| sms_opt_in | binary | fictional communication permission |
| vehicle_available | binary | access to private vehicle |
| area_deprivation_proxy | int 1-5 | invented proxy, higher indicates more deprivation; not official IMD |
| department | category | Outpatients, Physiotherapy, Diagnostics, Cardiology, Diabetes, Ophthalmology |
| appointment_type | category | New, Follow-up, Diagnostic |
| employment | category | employed, retired, not_employed |
| preferred_channel | category | sms, telephone, letter |
| survey_responded | binary | survey availability before index |
| attendance_confidence | nullable int 0-10 | self-rated confidence |
| support_consent | nullable binary | permission for support-team review, not SMS permission |
| transport_difficulty | nullable binary | patient reports travel barrier |
| financial_difficulty | nullable binary | patient reports financial barrier |
| accessibility_need | nullable binary | patient reports accessibility need |
| timing_conflict | nullable binary | patient reports appointment timing conflict |
| language_support | nullable binary | patient reports language support need |
| caring_responsibility | nullable binary | patient reports caring-related barrier |
| active_at_index | binary | early cancelled/rescheduled visits excluded from binary cohort |
| treatment | category | usual_care, reminder_offer, transport_offer, scheduling_offer, not_applicable; post-index exposure, never predictor |
| outcome | category | attended, no_show, cancelled, rescheduled; target information only |
| no_show | nullable binary | 1 no-show, 0 attended, NULL early disposition |
| split | category | chronological train/validation/test; audit only |

## Oracle
`appointment_id`, `active_at_index`, `assigned_treatment`, `observed_no_show` align with observed table. `p_<arm>` is the known synthetic potential no-show probability under each of the four hypothetical offers; `propensity_<arm>` is its known conditional assignment probability. All eight probabilities are NULL for inactive visits. ATE risk reduction is mean(p_usual_care − p_arm) across the specified active population. Not observed patient outcomes or clinical evidence.

## New database tables
`research_runs`: run ID, seed, expected row count and fingerprints. `research_appointments`: FK to base appointments and run, historical feature metadata, hypothetical treatment, target and split. `research_oracle`: FK to research appointment, eight potential risk and propensity values. Patient, appointment, survey and barrier data also persist in original Phase 1 tables; operational intervention approvals are not bypassed. See `carepath/phase2_schema.sql` for full constraints.
