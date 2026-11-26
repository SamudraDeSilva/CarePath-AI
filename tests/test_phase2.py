import unittest, tempfile, sqlite3
from pathlib import Path
import numpy as np
import pandas as pd
from carepath.phase2 import (generate,validate,splits,preprocessor,integrate,verify_database,submit_survey,SEED,N,BASE,FEATURES,BARRIERS,ARMS,dataset_hash)
from carepath.foundation import initialize, connect, seed_demo

class Phase2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.df,cls.oracle=generate(); cls.checks=validate(cls.df,cls.oracle)
        cls.tmp=tempfile.TemporaryDirectory(prefix='CarePath test ')
        cls.db=Path(cls.tmp.name)/'integrated.db'
        integrate(cls.db,cls.df,cls.oracle)
    @classmethod
    def tearDownClass(cls): cls.tmp.cleanup()
    def test_data_quality_all(self): self.assertTrue(all(self.checks.values()),self.checks)
    def test_reproducible(self):
        df,oracle=generate(); self.assertEqual(dataset_hash(df),dataset_hash(self.df)); self.assertEqual(dataset_hash(oracle),dataset_hash(self.oracle))
    def test_different_seed(self):
        df,_=generate(SEED+1); self.assertNotEqual(dataset_hash(df),dataset_hash(self.df))
    def test_no_post_index_features(self):
        self.assertFalse(set(FEATURES)&{'outcome','no_show','treatment','scheduled_at','survey_at','patient_id','appointment_id','active_at_index','split'})
    def test_temporal_label_availability(self): self.assertTrue(self.checks['training_labels_available_before_next_split'])
    def test_missing_is_not_no(self):
        self.assertTrue(self.df.loc[self.df.survey_responded.eq(0),list(BARRIERS)].isna().all().all())
    def test_preprocessing_train_only(self):
        parts=splits(self.df); p=preprocessor(); X=p.fit_transform(parts['train'][FEATURES]); V=p.transform(parts['validation'][FEATURES]); T=p.transform(parts['test'][FEATURES]); self.assertEqual(X.shape[1],V.shape[1]); self.assertEqual(X.shape[1],T.shape[1]); self.assertTrue(np.isfinite(X).all() and np.isfinite(V).all() and np.isfinite(T).all()); self.assertEqual(p.named_transformers_['num'].named_steps['scale'].n_samples_seen_,len(parts['train']))
    def test_baseline_and_survey(self):
        self.assertTrue(set(BASE)<set(FEATURES)); parts=splits(self.df,False); self.assertTrue(set(parts['train'].columns)==set(BASE)|{'appointment_id','patient_id','index_at','no_show'})
    def test_unseen_category(self):
        parts=splits(self.df); p=preprocessor(); p.fit(parts['train'][FEATURES]); r=parts['test'][FEATURES].iloc[:1].copy(); r['department']='unseen department'; self.assertTrue(np.isfinite(p.transform(r)).all())
    def test_oracle_probabilities(self):
        active=self.oracle.active_at_index.eq(1); self.assertTrue((self.oracle.loc[active,'p_transport_offer']<=self.oracle.loc[active,'p_usual_care']).all()); self.assertTrue(self.checks['propensity_overlap'])
    def test_db_roundtrip(self):
        v=verify_database(self.db,self.df,self.oracle); self.assertTrue(all(v.values()),v)
    def test_idempotence(self): self.assertFalse(integrate(self.db,self.df,self.oracle))
    def test_conflicting_run_rejected(self):
        d=self.df.copy(); d.loc[0,'distance_km']+=1; self.assertRaises(ValueError,integrate,self.db,d,self.oracle)
    def test_research_fk_enforced(self):
        with self.assertRaises(sqlite3.IntegrityError):
            with connect(self.db) as c: c.execute("INSERT INTO research_oracle(appointment_id) VALUES('unknown')")
    def test_form_submission(self):
        answers={b:None for b in BARRIERS}; answers['transport_difficulty']=1; answers['financial_difficulty']=0
        with connect(self.db) as c:
            sid=submit_survey(c,'A-003',4,answers,True,now='2026-11-25T12:00:00Z')
            r=c.execute('SELECT * FROM surveys WHERE survey_id=?',(sid,)).fetchone(); self.assertEqual(r['transport_difficulty'],1); self.assertEqual(r['financial_difficulty'],0); self.assertIsNone(r['timing_conflict']); self.assertEqual(r['support_consent'],1)
            self.assertEqual(c.execute('SELECT count(*) FROM barriers WHERE barrier_id=?',(sid+'-transport',)).fetchone()[0],1)
            self.assertEqual(c.execute("SELECT count(*) FROM audit_events WHERE entity_id=?",(sid,)).fetchone()[0],1)
            self.assertEqual(c.execute("SELECT count(*) FROM communications WHERE appointment_id='A-003'").fetchone()[0],0)
    def test_form_invalid_inputs(self):
        with connect(self.db) as c:
            for confidence,answers,consent in [(11,dict.fromkeys(BARRIERS,0),True),(True,dict.fromkeys(BARRIERS,0),True),(3,{},True),(3,dict.fromkeys(BARRIERS,2),True),(3,dict.fromkeys(BARRIERS,0),'yes')]:
                with self.assertRaises(ValueError): submit_survey(c,'A-003',confidence,answers,consent,now='2026-11-25T12:00:00Z')
    def test_form_historical_rejected(self):
        with connect(self.db) as c:
            with self.assertRaises(ValueError): submit_survey(c,self.df.appointment_id.iloc[0],5,dict.fromkeys(BARRIERS,0),False,now='2022-01-01T00:00:00Z')
    def test_form_after_appointment_rejected(self):
        with connect(self.db) as c:
            with self.assertRaises(ValueError): submit_survey(c,'A-003',5,dict.fromkeys(BARRIERS,0),False,now='2027-02-01T00:00:00Z')
    def test_form_rollback(self):
        with connect(self.db) as c: before=c.execute("SELECT count(*) FROM surveys").fetchone()[0]
        with self.assertRaises(RuntimeError):
            with connect(self.db) as c:
                submit_survey(c,'A-003',5,dict.fromkeys(BARRIERS,0),False,now='2026-11-25T12:00:00Z'); raise RuntimeError('rollback test')
        with connect(self.db) as c: self.assertEqual(c.execute('SELECT count(*) FROM surveys').fetchone()[0],before)

if __name__=='__main__': unittest.main()
