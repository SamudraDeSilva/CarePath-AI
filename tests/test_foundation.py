import sqlite3
import tempfile
import unittest
from pathlib import Path
from carepath.foundation import (initialize, connect, seed_demo, integrity, counts,
    propose, decide, simulate_sms, create_referral, simulate_booking, load_settings)


class FoundationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = initialize(Path(self.tmp.name)/'test.db')
        with connect(self.db) as c:
            seed_demo(c)

    def tearDown(self):
        self.tmp.cleanup()

    def rejected(self, error, callback):
        with self.assertRaises(error):
            with connect(self.db) as c:
                callback(c)

    def test_integrity_and_schema(self):
        with connect(self.db) as c:
            self.assertEqual(integrity(c), {'integrity_check':'ok','foreign_key_violations':[], 'schema_version':1,'table_count':14})

    def test_repeat_initialisation_and_seed(self):
        with connect(self.db) as c: before=counts(c)
        initialize(self.db)
        with connect(self.db) as c:
            self.assertFalse(seed_demo(c)); self.assertEqual(before,counts(c))

    def test_valid_journey(self):
        with connect(self.db) as c:
            self.assertEqual(c.execute("SELECT status FROM interventions WHERE intervention_id='I-001'").fetchone()[0],'in_progress')
            self.assertEqual(c.execute("SELECT status FROM transport_referrals WHERE referral_id='R-001'").fetchone()[0],'submitted')
            self.assertEqual(c.execute("SELECT status FROM transport_bookings WHERE booking_id='BK-001'").fetchone()[0],'simulated')
            self.assertEqual(c.execute("SELECT status FROM interventions WHERE intervention_id='I-002'").fetchone()[0],'rejected')
            self.assertEqual(counts(c)['audit_events'],9)

    def test_foreign_key(self):
        self.rejected(sqlite3.IntegrityError,lambda c:c.execute("INSERT INTO appointments(appointment_id,patient_id,scheduled_at,department,appointment_type) VALUES('BAD','ABSENT','2027-01-01','X','Y')"))

    def test_invalid_probability(self):
        self.rejected(sqlite3.IntegrityError,lambda c:c.execute("INSERT INTO predictions(prediction_id,appointment_id,model_id,no_show_probability) VALUES('BAD','A-001','M-DEMO',1.5)"))

    def test_duplicate_patient(self):
        self.rejected(sqlite3.IntegrityError,lambda c:c.execute("INSERT INTO patients(patient_id,age_band) VALUES('P-001','unknown')"))

    def test_real_patient_flag_blocked(self):
        self.rejected(sqlite3.IntegrityError,lambda c:c.execute("INSERT INTO patients(patient_id,age_band,is_synthetic) VALUES('P-BAD','unknown',0)"))

    def test_analyst_write_denied(self):
        self.rejected(PermissionError,lambda c:propose(c,'S-ANALYST','BAD','A-003','transport','demo'))

    def test_coordinator_cannot_approve(self):
        with connect(self.db) as c: propose(c,'S-COORD','I-NEW','A-003','transport','demo')
        self.rejected(PermissionError,lambda c:decide(c,'S-COORD','D-NEW','I-NEW','approve','demo'))
        self.rejected(sqlite3.IntegrityError,lambda c:c.execute("INSERT INTO intervention_decisions(decision_id,intervention_id,staff_id,decision,reason) VALUES('D-BAD','I-NEW','S-COORD','approve','demo')"))

    def test_inactive_reviewer_denied(self):
        with connect(self.db) as c:
            propose(c,'S-COORD','I-NEW','A-003','transport','demo'); c.execute("UPDATE staff SET active=0 WHERE staff_id='S-REVIEW'")
        self.rejected(PermissionError,lambda c:decide(c,'S-REVIEW','D-NEW','I-NEW','approve','demo'))

    def test_direct_status_bypass_blocked(self):
        with connect(self.db) as c: propose(c,'S-COORD','I-NEW','A-003','transport','demo')
        self.rejected(sqlite3.IntegrityError,lambda c:c.execute("UPDATE interventions SET status='approved' WHERE intervention_id='I-NEW'"))

    def test_unapproved_referral_blocked(self):
        with connect(self.db) as c: propose(c,'S-COORD','I-NEW','A-003','transport','demo')
        self.rejected(sqlite3.IntegrityError,lambda c:create_referral(c,'S-COORD','R-NEW','I-NEW','demo_eligible'))

    def test_rejected_referral_blocked(self):
        self.rejected(sqlite3.IntegrityError,lambda c:create_referral(c,'S-COORD','R-NEW','I-002','demo_eligible'))

    def test_support_consent_required(self):
        with connect(self.db) as c:
            propose(c,'S-COORD','I-NEW','A-002','transport','demo'); decide(c,'S-REVIEW','D-NEW','I-NEW','approve','demo')
        self.rejected(sqlite3.IntegrityError,lambda c:create_referral(c,'S-COORD','R-NEW','I-NEW','demo_eligible'))

    def test_withdrawn_consent_blocks_booking(self):
        with connect(self.db) as c:
            propose(c,'S-COORD','I-NEW','A-003','transport','demo'); decide(c,'S-REVIEW','D-NEW','I-NEW','approve','demo'); create_referral(c,'S-COORD','R-NEW','I-NEW','demo_eligible')
            c.execute("INSERT INTO surveys(survey_id,appointment_id,support_consent) VALUES('SV-NEW','A-003',0)")
        self.rejected(sqlite3.IntegrityError,lambda c:simulate_booking(c,'S-COORD','BK-NEW','R-NEW','2027-01-16T08:00:00Z'))

    def test_ineligible_booking_blocked(self):
        with connect(self.db) as c:
            propose(c,'S-COORD','I-NEW','A-003','transport','demo'); decide(c,'S-REVIEW','D-NEW','I-NEW','approve','demo'); create_referral(c,'S-COORD','R-NEW','I-NEW','demo_ineligible')
        self.rejected(sqlite3.IntegrityError,lambda c:simulate_booking(c,'S-COORD','BK-NEW','R-NEW','2027-01-16T08:00:00Z'))

    def test_late_pickup_blocked(self):
        with connect(self.db) as c:
            propose(c,'S-COORD','I-NEW','A-003','transport','demo'); decide(c,'S-REVIEW','D-NEW','I-NEW','approve','demo'); create_referral(c,'S-COORD','R-NEW','I-NEW','demo_eligible')
        self.rejected(sqlite3.IntegrityError,lambda c:simulate_booking(c,'S-COORD','BK-NEW','R-NEW','2027-01-16T10:00:00Z'))

    def test_sms_consent_required(self):
        self.rejected(sqlite3.IntegrityError,lambda c:simulate_sms(c,'S-COORD','MSG-X','A-002','standard_reminder','new'))

    def test_sms_idempotency(self):
        with connect(self.db) as c:
            before=counts(c); result=simulate_sms(c,'S-COORD','MSG-X','A-001','support_invitation','A-001:invitation:v1')
            self.assertEqual(result,'MSG-001'); self.assertEqual(before,counts(c))

    def test_sms_key_conflict(self):
        self.rejected(ValueError,lambda c:simulate_sms(c,'S-COORD','MSG-X','A-003','support_invitation','A-001:invitation:v1'))

    def test_cross_appointment_message(self):
        self.rejected(sqlite3.IntegrityError,lambda c:simulate_sms(c,'S-COORD','MSG-X','A-003','support_confirmation','new','I-001'))

    def test_confirmation_requires_approval(self):
        self.rejected(ValueError,lambda c:simulate_sms(c,'S-COORD','MSG-X','A-003','support_confirmation','new'))

    def test_audit_immutable(self):
        self.rejected(sqlite3.IntegrityError,lambda c:c.execute('DELETE FROM audit_events'))
        self.rejected(sqlite3.IntegrityError,lambda c:c.execute("UPDATE audit_events SET action='tampered'"))

    def test_decision_immutable(self):
        self.rejected(sqlite3.IntegrityError,lambda c:c.execute("UPDATE intervention_decisions SET decision='reject' WHERE decision_id='D-001'"))

    def test_transaction_rollback(self):
        def work(c):
            propose(c,'S-COORD','I-ROLL','A-003','transport','demo')
            raise RuntimeError('simulated error')
        self.rejected(RuntimeError,work)
        with connect(self.db) as c:
            self.assertIsNone(c.execute("SELECT 1 FROM interventions WHERE intervention_id='I-ROLL'").fetchone())
            self.assertIsNone(c.execute("SELECT 1 FROM audit_events WHERE entity_id='I-ROLL'").fetchone())

    def test_config_offline(self):
        self.assertFalse(load_settings()['allow_external_calls'])
        self.assertFalse(load_settings()['allow_real_patient_data'])

    def test_cancelled_appointment_sms_blocked(self):
        with connect(self.db) as c: c.execute("UPDATE appointments SET status='cancelled' WHERE appointment_id='A-003'")
        self.rejected(sqlite3.IntegrityError,lambda c:simulate_sms(c,'S-COORD','MSG-X','A-003','standard_reminder','new'))

    def test_unknown_schema_refused(self):
        other=Path(self.tmp.name)/'unknown.db'
        # sqlite3.Connection's context manager commits but does not close.
        # Use our closing context manager so Windows can remove the temp DB.
        with connect(other) as c:
            c.execute('CREATE TABLE schema_version(version INTEGER)')
            c.execute('INSERT INTO schema_version VALUES(99)')
        with self.assertRaises(ValueError): initialize(other)

if __name__=='__main__': unittest.main()
