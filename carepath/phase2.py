"""CarePath-AI Phase 2: synthetic longitudinal research data, no external calls."""
from pathlib import Path
from datetime import datetime, timezone
from uuid import uuid4
import hashlib, json, sqlite3
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.impute import SimpleImputer
from .foundation import initialize, connect, seed_demo, integrity, audit

ROOT = Path(__file__).resolve().parents[1]
SEED = 20261125
N = 50_000
ARMS = ('usual_care','reminder_offer','transport_offer','scheduling_offer')
BARRIERS = ('transport_difficulty','financial_difficulty','accessibility_need','timing_conflict','language_support','caring_responsibility')
CATEGORIES = ('transport','financial','accessibility','timing','language','caring')
NUM_BASE = ['age','distance_km','lead_days','prior_appointments','prior_no_shows','prior_cancellations','prior_no_show_rate','appointment_hour','weekday','month','sms_opt_in','vehicle_available','area_deprivation_proxy']
CAT_BASE = ['age_band','department','appointment_type','employment','preferred_channel']
NUM_SURVEY = ['survey_responded','attendance_confidence','support_consent',*BARRIERS]
BASE = NUM_BASE + CAT_BASE
FEATURES = BASE + NUM_SURVEY
TRAIN_END = '2025-01-04T00:00:00Z'
VALID_END = '2025-07-05T00:00:00Z'

def sigmoid(x): return 1/(1+np.exp(-x))
def ageband(a): return np.select([a<30,a<45,a<60,a<75],['18-29','30-44','45-59','60-74'],default='75+')
def iso(x): return pd.to_datetime(x).strftime('%Y-%m-%dT%H:%M:%SZ')

def generate(seed=SEED):
    """Exactly 50,000 appointments, 12,500 patients, 2023-25, known DGP.
    All features exist by index time (48 hours before visit). Competing dispositions
    occur before index; only appointments still active enter the binary cohort.
    Historical research offers are hypothetical assignments, not live actions.
    """
    rng=np.random.default_rng(seed); m=12_500
    counts=np.repeat(np.arange(2,7),2500); rng.shuffle(counts)
    age=rng.integers(18,91,m); depr=rng.integers(1,6,m)
    distance=np.round(np.clip(rng.lognormal(1.75,.75,m),.4,65),1)
    employed=rng.random(m)<np.where(age<65,.69,.12)
    employment=np.where(employed,'employed',np.where(age>=65,'retired','not_employed'))
    vehicle=(rng.random(m)<sigmoid(1.1-.43*(depr-3)-.02*np.maximum(age-70,0))).astype(int)
    sms=(rng.random(m)<sigmoid(1.7-.035*np.maximum(age-55,0))).astype(int)
    channel=np.where(sms==1,'sms',rng.choice(['telephone','letter'],m))
    latent=rng.normal(0,.42,m)
    weekday=rng.integers(0,5,m)
    weeks=np.full((m,6),-1,dtype=int)
    for i,c in enumerate(counts): weeks[i,:c]=np.sort(rng.choice(156,c,replace=False))
    previous=np.zeros(m,int); missed=np.zeros(m,int); cancelled=np.zeros(m,int)
    records=[]; truths=[]
    for k in range(6):
        ids=np.flatnonzero(counts>k); s=len(ids); a=age[ids]; d=depr[ids]; km=distance[ids]; car=vehicle[ids]
        hr=rng.choice([8,9,10,11,12,13,14,15,16],s); minute=rng.choice([0,30],s)
        dates=pd.Timestamp('2023-01-02')+pd.to_timedelta(weeks[ids,k]*7+weekday[ids],unit='D')+pd.to_timedelta(hr,unit='h')+pd.to_timedelta(minute,unit='m')
        lead=rng.integers(7,91,s)
        dept=rng.choice(['Outpatients','Physiotherapy','Diagnostics','Cardiology','Diabetes','Ophthalmology'],s,p=[.30,.18,.17,.12,.12,.11])
        typ=rng.choice(['New','Follow-up','Diagnostic'],s,p=[.28,.55,.17])
        transport=rng.random(s)<sigmoid(-1.7+1.2*(1-car)+.035*km+.20*(d-3)+.025*np.maximum(a-65,0))
        financial=rng.random(s)<sigmoid(-2.0+.65*(d-3)+.45*(1-car))
        access=rng.random(s)<sigmoid(-2.6+.055*np.maximum(a-50,0))
        timing=rng.random(s)<sigmoid(-2.0+.95*employed[ids]+.6*(hr<10))
        language=rng.random(s)<.075
        caring=rng.random(s)<sigmoid(-2.4+.8*(a<60)+.4*employed[ids])
        barriers=np.column_stack([transport,financial,access,timing,language,caring]).astype(int)
        confidence=np.clip(np.rint(8.8-1.05*barriers.sum(1)-.7*transport+rng.normal(0,1.3,s)),0,10).astype(int)
        responded=rng.random(s)<sigmoid(1.05+.45*sms[ids]-.25*language-.17*(d-3))
        consent=(rng.random(s)<sigmoid(.35+.7*transport+.30*financial+.25*timing))
        rate=np.divide(missed[ids],previous[ids],out=np.zeros(s,float),where=previous[ids]>0)
        # Competing dispositions are determined before index, not intervention effects.
        early=rng.random(s); cancel=early<.055; reschedule=(early>=.055)&(early<.085); active=~(cancel|reschedule)
        # Assignment depends solely on recorded pre-index covariates; conditional randomization.
        obs=np.where(responded[:,None],barriers,0)
        scores=np.column_stack([np.zeros(s), -.25+.35*sms[ids]+.55*rate, -.7+1.0*obs[:,0]+.45*obs[:,1]+.25*(1-car), -.65+1.1*obs[:,3]+.45*obs[:,5]])
        weights=np.exp(scores); props=.12/4+.88*weights/weights.sum(1,keepdims=True)
        arm=np.minimum((rng.random(s)[:,None]>np.cumsum(props,axis=1)).sum(1),3)
        # Known conditional potential outcome probabilities. Effects are invented.
        p0=sigmoid(-2.55+1.05*transport+.62*financial+.52*access+.80*timing+.36*language+.55*caring+.92*rate+.012*(lead-35)+.22*(hr<10)+.15*(d-3)+latent[ids]+.17*(typ=='New'))
        p=np.column_stack([p0,p0*(1-.14-.10*(confidence<5)),p0*(1-.08-.48*transport-.12*financial),p0*(1-.06-.44*timing-.13*caring)])
        u=rng.random(s); observed=u<p[np.arange(s),arm]
        outcome=np.where(cancel,'cancelled',np.where(reschedule,'rescheduled',np.where(observed,'no_show','attended')))
        appointment_ids=np.array([f'R-A-{i+1:05d}-{k+1}' for i in ids]); patient_ids=np.array([f'R-P-{i+1:05d}' for i in ids])
        index=dates-pd.Timedelta(days=2); survey_dates=dates-pd.Timedelta(days=3)
        rec=pd.DataFrame(dict(appointment_id=appointment_ids,patient_id=patient_ids,scheduled_at=iso(dates),booked_at=iso(dates-pd.to_timedelta(lead,unit='D')),index_at=iso(index),survey_at=np.where(responded,iso(survey_dates),None),age=a,age_band=ageband(a),distance_km=km,lead_days=lead,prior_appointments=previous[ids],prior_no_shows=missed[ids],prior_cancellations=cancelled[ids],prior_no_show_rate=rate,appointment_hour=hr,weekday=dates.weekday,month=dates.month,sms_opt_in=sms[ids],vehicle_available=car,area_deprivation_proxy=d,department=dept,appointment_type=typ,employment=employment[ids],preferred_channel=channel[ids],survey_responded=responded.astype(int),attendance_confidence=np.where(responded,confidence,np.nan),support_consent=np.where(responded,consent.astype(int),np.nan),active_at_index=active.astype(int),treatment=np.where(active,np.array(ARMS)[arm], 'not_applicable'),outcome=outcome,no_show=np.where(active,observed.astype(int),np.nan)))
        for j,b in enumerate(BARRIERS): rec[b]=np.where(responded,barriers[:,j],np.nan)
        records.append(rec)
        tr=pd.DataFrame({'appointment_id':appointment_ids,'active_at_index':active.astype(int),'assigned_treatment':np.where(active,np.array(ARMS)[arm],'not_applicable'),'observed_no_show':np.where(active,observed.astype(int),np.nan)})
        for j,arm_name in enumerate(ARMS):
            tr['p_'+arm_name]=np.where(active,p[:,j],np.nan); tr['propensity_'+arm_name]=np.where(active,props[:,j],np.nan)
        truths.append(tr)
        previous[ids]+=1; missed[ids]+=(outcome=='no_show'); cancelled[ids]+=np.isin(outcome,['cancelled','rescheduled'])
    df=pd.concat(records,ignore_index=True).sort_values(['index_at','appointment_id']).reset_index(drop=True)
    oracle=pd.concat(truths,ignore_index=True).set_index('appointment_id').loc[df.appointment_id].reset_index()
    df['split']=np.select([df.index_at<TRAIN_END,df.index_at<VALID_END],['train','validation'],default='test')
    return df,oracle

def splits(df, survey=True):
    cols=FEATURES if survey else BASE
    return {name:df.loc[(df.split==name)&(df.active_at_index==1),['appointment_id','patient_id','index_at',*cols,'no_show']].copy() for name in ('train','validation','test')}

def preprocessor(survey=True):
    nums=NUM_BASE+(NUM_SURVEY if survey else [])
    return ColumnTransformer([('num',Pipeline([('impute',SimpleImputer(strategy='median',add_indicator=True)),('scale',StandardScaler())]),nums),('cat',Pipeline([('impute',SimpleImputer(strategy='constant',fill_value='unknown')),('encode',OneHotEncoder(handle_unknown='ignore',sparse_output=False))]),CAT_BASE)],remainder='drop')

def dataset_hash(df):
    return hashlib.sha256(df.to_csv(index=False,float_format='%.10g',lineterminator='\n').encode('utf-8')).hexdigest()

def validate(df,oracle):
    checks={}
    checks['exactly_50000']=len(df)==N
    checks['unique_appointments']=df.appointment_id.is_unique
    checks['12500_patients']=df.patient_id.nunique()==12500
    checks['valid_patient_appointment_counts']=df.groupby('patient_id').size().between(2,6).all()
    checks['no_real_identifiers']=df.patient_id.str.fullmatch(r'R-P-\d{5}').all()
    checks['valid_dispositions']=set(df.outcome)=={'attended','no_show','cancelled','rescheduled'}
    active=df.active_at_index.eq(1); responded=df.survey_responded.eq(1)
    checks['binary_target_only_active']=df.loc[active,'no_show'].isin([0,1]).all() and df.loc[~active,'no_show'].isna().all() and (df.loc[active,'no_show']==df.loc[active,'outcome'].eq('no_show')).all()
    checks['competing_dispositions_excluded']=active.equals(df.outcome.isin(['attended','no_show']))
    checks['survey_missingness_preserved']=df.loc[~responded,NUM_SURVEY[1:]].isna().all().all() and df.loc[responded,NUM_SURVEY[1:]].notna().all().all()
    checks['survey_timestamps_pre_index']=(df.loc[responded,'survey_at']<df.loc[responded,'index_at']).all()
    checks['booking_pre_index']=(df.booked_at<df.index_at).all()
    checks['index_pre_appointment']=(df.index_at<df.scheduled_at).all()
    checks['survey_confidence_range']=df.loc[responded,'attendance_confidence'].between(0,10).all()
    checks['survey_flags_binary']=df.loc[responded,[*BARRIERS,'support_consent']].isin([0,1]).all().all()
    checks['patient_history_exact']=True
    sort=df.sort_values(['patient_id','scheduled_at']); g=sort.groupby('patient_id'); prev_date=g.scheduled_at.shift()
    checks['prior_outcomes_available']=((prev_date.isna())|(prev_date<sort.index_at)).all()
    checks['patient_history_exact']=(sort.prior_appointments==g.cumcount()).all() and (sort.prior_no_shows==(sort.outcome.eq('no_show').astype(int).groupby(sort.patient_id).cumsum()-sort.outcome.eq('no_show').astype(int))).all() and (sort.prior_cancellations==(sort.outcome.isin(['cancelled','rescheduled']).astype(int).groupby(sort.patient_id).cumsum()-sort.outcome.isin(['cancelled','rescheduled']).astype(int))).all()
    parts=splits(df); checks['strict_temporal_splits']=parts['train'].index_at.max()<parts['validation'].index_at.min() and parts['validation'].index_at.max()<parts['test'].index_at.min()
    checks['training_labels_available_before_next_split']=df.loc[df.split.eq('train'),'scheduled_at'].max()<parts['validation'].index_at.min() and df.loc[df.split.eq('validation'),'scheduled_at'].max()<parts['test'].index_at.min()
    checks['split_exhaustiveness']=sum(map(len,parts.values()))==int(active.sum())
    checks['feature_allowlist_no_leakage']=not set(FEATURES)&{'appointment_id','patient_id','outcome','no_show','treatment','active_at_index','split','index_at'} and all(set(p.columns)==set(FEATURES)|{'appointment_id','patient_id','index_at','no_show'} for p in parts.values())
    checks['oracle_alignment']=oracle.appointment_id.equals(df.appointment_id) and oracle.assigned_treatment.equals(df.treatment)
    prob=oracle.loc[active,['p_'+a for a in ARMS]]; prop=oracle.loc[active,['propensity_'+a for a in ARMS]]
    checks['oracle_probabilities_valid']=prob.ge(0).all().all() and prob.le(1).all().all()
    checks['propensity_overlap']=prop.gt(.029).all().all() and np.allclose(prop.sum(axis=1),1)
    checks['oracle_missing_for_inactive']=oracle.loc[~active,['p_'+a for a in ARMS]+['propensity_'+a for a in ARMS]].isna().all().all()
    checks['all_arms_observed']=set(df.loc[active,'treatment'])==set(ARMS)
    checks['no_future_oracle_in_features']=not set(FEATURES)&set(oracle.columns)
    return {k:bool(v) for k,v in checks.items()}

def sql_value(v):
    if pd.isna(v): return None
    return v.item() if isinstance(v,np.generic) else v

def rows(frame, cols): return (tuple(sql_value(v) for v in r) for r in frame[cols].itertuples(index=False,name=None))

def insert_frame(conn,table,frame,cols):
    conn.executemany(f'INSERT INTO {table} ({",".join(cols)}) VALUES ({",".join("?" for _ in cols)})',rows(frame,cols))

def integrate(path,df,oracle,seed=SEED):
    """Create/extend a separate integrated DB; retain original Phase 1 fixture DB.
    Historical research offers are in separate table, never operational approvals.
    Refuse replacement of another research run; repeat same run is a no-op.
    """
    initialize(path)
    with connect(path) as conn:
        seed_demo(conn)
        conn.executescript((ROOT/'carepath/phase2_schema.sql').read_text(encoding='utf-8'))
        fingerprint=dataset_hash(df); oracle_hash=dataset_hash(oracle)
        old=conn.execute('SELECT dataset_hash,oracle_hash FROM research_runs WHERE run_id=?',('phase2-v0.2.0',)).fetchone()
        if old:
            if tuple(old)!=(fingerprint,oracle_hash): raise ValueError('Existing research run differs; choose a new database path')
            if conn.execute('SELECT count(*) FROM research_appointments').fetchone()[0]!=N or conn.execute('SELECT count(*) FROM research_oracle').fetchone()[0]!=N: raise ValueError('Existing research run incomplete')
            return False
        patients=df.drop_duplicates('patient_id')[['patient_id','age_band','sms_opt_in']].copy()
        patients['contact_ref']=np.where(patients.sms_opt_in.eq(1),'SYNTH-'+patients.patient_id,None); patients['created_at']='2022-09-01T00:00:00Z'
        insert_frame(conn,'patients',patients,['patient_id','age_band','contact_ref','sms_opt_in','created_at'])
        ap=df.rename(columns={'outcome':'status','booked_at':'created_at'})
        insert_frame(conn,'appointments',ap,['appointment_id','patient_id','scheduled_at','department','appointment_type','status','created_at'])
        sv=df.loc[df.survey_responded.eq(1)].copy(); sv['survey_id']='R-SV-'+sv.appointment_id; sv['recorded_at']=sv.survey_at
        insert_frame(conn,'surveys',sv,['survey_id','appointment_id','recorded_at','attendance_confidence',*BARRIERS,'support_consent'])
        for b,c in zip(BARRIERS,CATEGORIES):
            subset=sv.loc[sv[b].eq(1),['appointment_id','survey_at']].copy(); subset['barrier_id']='R-B-'+subset.appointment_id+'-'+c; subset['category']=c; subset['source']='survey'; subset['recorded_at']=subset.survey_at; subset['confirmed']=0
            insert_frame(conn,'barriers',subset,['barrier_id','appointment_id','category','source','recorded_at','confirmed'])
        conn.execute('INSERT INTO research_runs(run_id,seed,record_count,dataset_hash,oracle_hash) VALUES(?,?,?,?,?)',('phase2-v0.2.0',seed,len(df),fingerprint,oracle_hash))
        research=df.copy(); research['run_id']='phase2-v0.2.0'
        cols=['appointment_id','run_id','index_at','survey_at','age','distance_km','lead_days','prior_appointments','prior_no_shows','prior_cancellations','prior_no_show_rate','appointment_hour','weekday','month','vehicle_available','area_deprivation_proxy','employment','preferred_channel','survey_responded','active_at_index','treatment','no_show','split']
        insert_frame(conn,'research_appointments',research,cols)
        insert_frame(conn,'research_oracle',oracle,['appointment_id',*['p_'+a for a in ARMS],*['propensity_'+a for a in ARMS]])
        audit(conn,'S-ADMIN','research_imported','research_run','phase2-v0.2.0',{'count':len(df),'synthetic':True,'dataset_hash':fingerprint})
    return True

def submit_survey(conn,appointment_id,confidence,answers,support_consent,now=None):
    """Local fictional patient form. Append responses; never approve or send anything."""
    if isinstance(confidence,bool) or not isinstance(confidence,(int,np.integer)) or not 0<=confidence<=10: raise ValueError('Confidence must be integer 0–10')
    if set(answers)!=set(BARRIERS) or any(v not in (0,1,True,False,None) for v in answers.values()): raise ValueError('Use exactly the six barrier fields, yes/no/not answered')
    if not isinstance(support_consent,bool): raise ValueError('Explicit support consent boolean required')
    now=now or datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    try: stamp=datetime.strptime(now,'%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)
    except (ValueError,TypeError) as e: raise ValueError('Timestamp must be UTC ISO format') from e
    ap=conn.execute("SELECT a.status,a.scheduled_at,p.is_synthetic FROM appointments a JOIN patients p USING(patient_id) WHERE a.appointment_id=?",(appointment_id,)).fetchone()
    if not ap or ap['status']!='scheduled' or not ap['is_synthetic'] or appointment_id.startswith('R-A-'): raise ValueError('Only scheduled fictional demonstration appointments can receive this form')
    scheduled=datetime.fromisoformat(ap['scheduled_at'].replace('Z','+00:00')); scheduled=scheduled if scheduled.tzinfo else scheduled.replace(tzinfo=timezone.utc)
    if stamp>=scheduled: raise ValueError('Survey must precede appointment')
    sid='FORM-'+uuid4().hex
    conn.execute('INSERT INTO surveys(survey_id,appointment_id,recorded_at,attendance_confidence,transport_difficulty,financial_difficulty,accessibility_need,timing_conflict,language_support,caring_responsibility,support_consent) VALUES(?,?,?,?,?,?,?,?,?,?,?)',(sid,appointment_id,now,confidence,*[answers[b] for b in BARRIERS],int(support_consent)))
    for b,c in zip(BARRIERS,CATEGORIES):
        if answers[b]==1: conn.execute("INSERT INTO barriers(barrier_id,appointment_id,category,source,recorded_at,confirmed) VALUES(?,?,?,'survey',?,0)",(sid+'-'+c,appointment_id,c,now))
    audit(conn,None,'synthetic_survey_submitted','survey',sid,{'appointment_id':appointment_id,'support_consent':support_consent})
    return sid


def survey_widget(db):
    """Optional Jupyter widget, uses the same validated service as the editable cell."""
    import ipywidgets as w
    with connect(db) as c:
        opts=[r[0] for r in c.execute("SELECT appointment_id FROM appointments WHERE status='scheduled' AND appointment_id NOT LIKE 'R-A-%' ORDER BY appointment_id")]
    ap=w.Dropdown(options=opts,description='Appointment'); confidence=w.IntSlider(min=0,max=10,value=5,description='Confidence')
    fields={b:w.Dropdown(options=[('Not answered',None),('No',0),('Yes',1)],description=b.replace('_',' ').title(),style={'description_width':'180px'}) for b in BARRIERS}
    consent=w.Checkbox(value=False,description='I agree to support-team review'); button=w.Button(description='Save simulated survey',button_style='success'); out=w.Output()
    def save(_):
        with out:
            out.clear_output()
            try:
                with connect(db) as c: sid=submit_survey(c,ap.value,confidence.value,{b:f.value for b,f in fields.items()},consent.value,now='2026-11-25T12:00:00Z')
                print('Saved fictional survey:',sid)
            except Exception as e: print(type(e).__name__,str(e))
    button.on_click(save)
    return w.VBox([w.HTML('<b>Fictional appointment support survey</b> — no real patient information; simulated clock 25 November 2026'),ap,confidence,*fields.values(),consent,button,out])

def verify_database(db,df,oracle):
    """Compare persisted historical data to generated data, excluding demo fixtures."""
    with connect(db) as c:
        info=integrity(c)
        n=c.execute('SELECT count(*) FROM research_appointments').fetchone()[0]
        patients=c.execute("SELECT count(*) FROM patients WHERE patient_id LIKE 'R-P-%'").fetchone()[0]
        q='''SELECT r.appointment_id,a.patient_id,a.scheduled_at,a.created_at AS booked_at,r.index_at,r.survey_at,r.age,p.age_band,r.distance_km,r.lead_days,r.prior_appointments,r.prior_no_shows,r.prior_cancellations,r.prior_no_show_rate,r.appointment_hour,r.weekday,r.month,p.sms_opt_in,r.vehicle_available,r.area_deprivation_proxy,a.department,a.appointment_type,r.employment,r.preferred_channel,r.survey_responded,s.attendance_confidence,s.support_consent,r.active_at_index,r.treatment,a.status AS outcome,r.no_show,s.transport_difficulty,s.financial_difficulty,s.accessibility_need,s.timing_conflict,s.language_support,s.caring_responsibility,r.split FROM research_appointments r JOIN appointments a USING(appointment_id) JOIN patients p USING(patient_id) LEFT JOIN surveys s ON s.survey_id='R-SV-'||r.appointment_id ORDER BY r.index_at,r.appointment_id'''
        persisted=pd.read_sql_query(q,c)
        stored_oracle=pd.read_sql_query('SELECT o.* FROM research_oracle o JOIN research_appointments r USING(appointment_id) ORDER BY r.index_at,r.appointment_id',c)
        operations=c.execute("SELECT count(*) FROM interventions WHERE appointment_id LIKE 'R-A-%'").fetchone()[0]+c.execute("SELECT count(*) FROM communications WHERE appointment_id LIKE 'R-A-%'").fetchone()[0]
        survey_count=c.execute("SELECT count(*) FROM surveys WHERE appointment_id LIKE 'R-A-%'").fetchone()[0]
        manifest=c.execute('SELECT dataset_hash,oracle_hash FROM research_runs').fetchone()
    try:
        pd.testing.assert_frame_equal(persisted[df.columns],df,check_dtype=False,rtol=1e-10,atol=1e-10); data_equal=True
    except AssertionError: data_equal=False
    cols=['appointment_id',*['p_'+a for a in ARMS],*['propensity_'+a for a in ARMS]]
    try:
        pd.testing.assert_frame_equal(stored_oracle[cols],oracle[cols],check_dtype=False,rtol=1e-10,atol=1e-10); oracle_equal=True
    except AssertionError: oracle_equal=False
    return {'database_integrity':info['integrity_check']=='ok','foreign_keys_clean':not info['foreign_key_violations'],'schema_extension_tables':info['table_count']==17,'research_appointment_count':n==N,'research_patient_count':patients==12500,'survey_count_matches':survey_count==int(df.survey_responded.sum()),'research_data_roundtrip':data_equal,'oracle_roundtrip':oracle_equal,'no_live_research_actions':operations==0,'manifest_hashes_match':tuple(manifest)==(dataset_hash(df),dataset_hash(oracle))}
