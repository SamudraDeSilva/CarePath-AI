"""SQLite foundation. All data and external actions are simulated.
Staff identifiers are demo role assertions, NOT authenticated identities.
Use the service methods rather than direct SQL for audited write operations.
"""
import json
import logging
import sqlite3
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG = logging.getLogger('carepath')


def load_settings(root=ROOT):
    settings = json.loads((Path(root) / 'config/settings.json').read_text(encoding='utf-8'))
    if (settings['mode'] != 'simulation' or settings['allow_external_calls'] is not False
            or settings['allow_real_patient_data'] is not False or settings['timezone'] != 'UTC'):
        raise ValueError('Phase 1 supports synthetic, offline UTC simulation only')
    path = Path(settings['database'])
    if path.is_absolute() or '..' in path.parts:
        raise ValueError('Database must be inside project')
    return settings


@contextmanager
def connect(path):
    conn = sqlite3.connect(path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys=ON')
    conn.execute('PRAGMA busy_timeout=10000')
    try:
        with conn:
            yield conn
    except Exception as exc:
        LOG.warning('Database transaction rolled back: %s', type(exc).__name__)
        raise
    finally:
        conn.close()


def initialize(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with connect(path) as conn:
        # Fail closed when opening a database belonging to an unknown schema.
        exists = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='schema_version'").fetchone()
        if exists and [r[0] for r in conn.execute('SELECT version FROM schema_version')] != [1]:
            raise ValueError('Unsupported schema version')
        conn.executescript((ROOT / 'carepath/schema.sql').read_text(encoding='utf-8'))
    return path


def authorize(conn, actor, roles):
    row = conn.execute('SELECT role, active FROM staff WHERE staff_id=?', (actor,)).fetchone()
    if not row or not row['active'] or row['role'] not in roles:
        raise PermissionError('Role not authorised for this operation')


def audit(conn, actor, action, entity, entity_id, details=None):
    conn.execute('INSERT INTO audit_events(actor_id,action,entity_type,entity_id,details_json) VALUES(?,?,?,?,?)',
                 (actor, action, entity, entity_id, json.dumps(details or {}, sort_keys=True)))


def propose(conn, actor, intervention_id, appointment_id, kind, rationale):
    authorize(conn, actor, {'admin','reviewer','coordinator'})
    if not rationale.strip():
        raise ValueError('Rationale required')
    conn.execute('INSERT INTO interventions(intervention_id,appointment_id,kind,rationale) VALUES(?,?,?,?)',
                 (intervention_id, appointment_id, kind, rationale))
    audit(conn, actor, 'proposed', 'intervention', intervention_id, {'kind':kind})


def decide(conn, actor, decision_id, intervention_id, decision, reason):
    authorize(conn, actor, {'admin','reviewer'})
    conn.execute('INSERT INTO intervention_decisions(decision_id,intervention_id,staff_id,decision,reason) VALUES(?,?,?,?,?)',
                 (decision_id, intervention_id, actor, decision, reason))
    audit(conn, actor, decision, 'intervention', intervention_id)


def simulate_sms(conn, actor, message_id, appointment_id, template_key, dedupe_key, intervention_id=None):
    authorize(conn, actor, {'admin','reviewer','coordinator'})
    existing = conn.execute('SELECT * FROM communications WHERE dedupe_key=?', (dedupe_key,)).fetchone()
    if existing:
        if (existing['appointment_id'],existing['template_key'],existing['intervention_id']) != (appointment_id,template_key,intervention_id):
            raise ValueError('Deduplication key conflict')
        return existing['message_id']
    if template_key not in {'standard_reminder','support_invitation','support_confirmation','transport_confirmation'}:
        raise ValueError('Unknown template')
    if template_key in {'support_confirmation','transport_confirmation'} and intervention_id is None:
        raise ValueError('Confirmation requires an approved intervention')
    if template_key == 'transport_confirmation' and not conn.execute('''SELECT 1 FROM transport_bookings b JOIN transport_referrals r ON r.referral_id=b.referral_id WHERE r.intervention_id=? AND b.status='simulated' AND r.status='submitted' ''',(intervention_id,)).fetchone():
        raise ValueError('Transport confirmation requires simulated booking')
    conn.execute('INSERT INTO communications(message_id,appointment_id,intervention_id,channel,template_key,dedupe_key) VALUES(?,?,?,\'sms\',?,?)',
                 (message_id, appointment_id, intervention_id, template_key, dedupe_key))
    audit(conn, actor, 'sms_simulated', 'communication', message_id)
    return message_id


def create_referral(conn, actor, referral_id, intervention_id, eligibility_status='review_required', mobility_notes=None):
    authorize(conn, actor, {'admin','reviewer','coordinator'})
    conn.execute('INSERT INTO transport_referrals(referral_id,intervention_id,eligibility_status,mobility_notes) VALUES(?,?,?,?)',
                 (referral_id, intervention_id, eligibility_status, mobility_notes))
    audit(conn, actor, 'referral_created', 'transport_referral', referral_id)


def simulate_booking(conn, actor, booking_id, referral_id, pickup_at):
    authorize(conn, actor, {'admin','reviewer','coordinator'})
    conn.execute("INSERT INTO transport_bookings(booking_id,referral_id,provider,pickup_at) VALUES(?,?,'SIMULATED_PROVIDER',?)",
                 (booking_id, referral_id, pickup_at))
    conn.execute("UPDATE transport_referrals SET status='submitted' WHERE referral_id=?", (referral_id,))
    conn.execute("UPDATE interventions SET status='in_progress' WHERE intervention_id=(SELECT intervention_id FROM transport_referrals WHERE referral_id=?)", (referral_id,))
    audit(conn, actor, 'booking_simulated', 'transport_booking', booking_id)


def seed_demo(conn):
    """One deterministic synthetic fixture set; never overwrite existing data."""
    if conn.execute("SELECT 1 FROM audit_events WHERE action='demo_seeded' AND entity_id='phase1'").fetchone():
        return False
    conn.executemany('INSERT INTO staff(staff_id,display_name,role) VALUES(?,?,?)', [
        ('S-ADMIN','Demo Admin','admin'),('S-REVIEW','Demo Reviewer','reviewer'),
        ('S-COORD','Demo Coordinator','coordinator'),('S-ANALYST','Demo Analyst','analyst')])
    conn.executemany('INSERT INTO patients(patient_id,age_band,contact_ref,sms_opt_in) VALUES(?,?,?,?)',[
        ('P-001','60-74','DEMO-CONTACT-001',1),('P-002','30-44',None,0),('P-003','45-59','DEMO-CONTACT-003',1)])
    conn.executemany('INSERT INTO appointments(appointment_id,patient_id,scheduled_at,department,appointment_type) VALUES(?,?,?,?,?)',[
        ('A-001','P-001','2027-01-15T10:00:00Z','Outpatients','Follow-up'),('A-002','P-002','2027-01-15T11:00:00Z','Physiotherapy','New'),('A-003','P-003','2027-01-16T09:00:00Z','Outpatients','Follow-up')])
    conn.executemany('INSERT INTO surveys(survey_id,appointment_id,attendance_confidence,transport_difficulty,financial_difficulty,support_consent) VALUES(?,?,?,?,?,?)',[
        ('SV-001','A-001',3,1,1,1),('SV-002','A-002',8,0,0,0),('SV-003','A-003',5,0,0,1)])
    conn.execute("INSERT INTO model_registry(model_id,model_kind,version) VALUES('M-DEMO','placeholder','0.1.0')")
    conn.executemany('INSERT INTO predictions(prediction_id,appointment_id,model_id,no_show_probability) VALUES(?,?,?,?)',[
        ('PR-001','A-001','M-DEMO',0.82),('PR-002','A-002','M-DEMO',0.15),('PR-003','A-003','M-DEMO',0.61)])
    conn.executemany('INSERT INTO barriers(barrier_id,appointment_id,category,source,confirmed) VALUES(?,?,?,?,?)',[
        ('B-001','A-001','transport','survey',1),('B-002','A-001','financial','survey',1),('B-003','A-003','timing','staff',1)])
    propose(conn,'S-COORD','I-001','A-001','transport','Synthetic transport difficulty')
    simulate_sms(conn,'S-COORD','MSG-001','A-001','support_invitation','A-001:invitation:v1')
    decide(conn,'S-REVIEW','D-001','I-001','approve','Demo review only')
    create_referral(conn,'S-COORD','R-001','I-001','demo_eligible','Synthetic mobility support')
    simulate_booking(conn,'S-COORD','BK-001','R-001','2027-01-15T09:00:00Z')
    simulate_sms(conn,'S-COORD','MSG-002','A-001','transport_confirmation','A-001:transport:v1','I-001')
    propose(conn,'S-COORD','I-002','A-003','reschedule','Synthetic scheduling conflict')
    decide(conn,'S-REVIEW','D-002','I-002','reject','Demo rejection; no schedule change')
    audit(conn,'S-ADMIN','demo_seeded','fixture','phase1',{'synthetic':True})
    return True


def integrity(conn):
    return {'integrity_check':conn.execute('PRAGMA integrity_check').fetchone()[0],
            'foreign_key_violations':[tuple(r) for r in conn.execute('PRAGMA foreign_key_check')],
            'schema_version':conn.execute('SELECT version FROM schema_version').fetchone()[0],
            'table_count':conn.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchone()[0]}


def counts(conn):
    return {name:conn.execute(f'SELECT count(*) FROM "{name}"').fetchone()[0] for name in [
        'staff','patients','appointments','surveys','model_registry','predictions','barriers','interventions','intervention_decisions','communications','transport_referrals','transport_bookings','audit_events']}
