# Load the preceding SAS stage and expose its public names here.
import importlib.util as _importlib_util
import sys as _sys
from pathlib import Path as _Path

_previous_name = '_translated_sas_stage_02'
_previous_path = _Path(__file__).with_name('1 - First stage_Simple Average of Measure Scores_2025Jul.py')
_previous_module = _sys.modules.get(_previous_name)
_previous_spec = None
if _previous_module is None:
    _previous_spec = _importlib_util.spec_from_file_location(_previous_name, _previous_path)
    if _previous_spec is None or _previous_spec.loader is None:
        raise ImportError(f"Could not load previous translation: {_previous_path}")
    _previous_module = _importlib_util.module_from_spec(_previous_spec)
    _sys.modules[_previous_name] = _previous_module
    try:
        _previous_spec.loader.exec_module(_previous_module)
    except Exception:
        del _sys.modules[_previous_name]
        raise
globals().update({name: value for name, value in vars(_previous_module).items()
                  if not name.startswith("_")})
del _importlib_util, _sys, _Path, _previous_name, _previous_path
del _previous_module, _previous_spec

import numpy as np
import pandas as pd

df_om = Outcome_mortality[['provider_id', 'grp_score']].rename(columns={'grp_score': 'Std_Outcomes_Mortality_score'})
df_or = Outcome_readmission[['provider_id', 'grp_score']].rename(columns={'grp_score': 'Std_Outcomes_Readmission_score'})
df_os = Outcome_safety[['provider_id', 'grp_score']].rename(columns={'grp_score': 'Std_Outcomes_Safety_score'})
df_pt = PtExp[['provider_id', 'grp_score']].rename(columns={'grp_score': 'Std_PatientExp_score'})
df_pr = Process[['provider_id', 'grp_score']].rename(columns={'grp_score': 'Std_Process_score'})

all_df = df_om.merge(df_or, on='provider_id', how='outer') \
             .merge(df_os, on='provider_id', how='outer') \
             .merge(df_pt, on='provider_id', how='outer') \
             .merge(df_pr, on='provider_id', how='outer')

summary_score = all_df.copy()
summary_score['std_weight_PatientExperience'] = 0.22
summary_score['std_weight_Readmission'] = 0.22
summary_score['std_weight_Mortality'] = 0.22
summary_score['std_weight_safety'] = 0.22
summary_score['std_weight_Process'] = 0.12

weights = [0.22, 0.22, 0.22, 0.22, 0.12]
score_cols = [
    'Std_PatientExp_score', 
    'Std_Outcomes_Readmission_score', 
    'Std_Outcomes_Mortality_score', 
    'Std_Outcomes_Safety_score', 
    'Std_Process_score'
]

def calc_summary(row):
    w_arr = np.array(weights)
    scores = np.array([row[c] for c in score_cols])
    is_missing = np.isnan(scores).astype(int)
    
    denom = 1.0 - np.sum(is_missing * w_arr)
    if denom <= 0:
        return np.nan
        
    adj_weights = []
    for k in range(5):
        if np.isnan(scores[k]):
            adj_weights.append(np.nan)
        else:
            adj_weights.append(w_arr[k] / denom)
            
    sum_weighted = 0.0
    for k in range(5):
        if not np.isnan(scores[k]) and not np.isnan(adj_weights[k]):
            sum_weighted += adj_weights[k] * scores[k]
            
    return sum_weighted

summary_score['summary_score'] = summary_score.apply(calc_summary, axis=1)

report_res = report(
    std_data_2025Jul_analysis, 
    'report_indicator', 
    measure_OM, 
    measure_OS, 
    measure_OR, 
    measure_PtExp, 
    measure_Process
)
report_indicator_df = report_res['report_indicator']

summary_score1 = summary_score.sort_values(by='provider_id').reset_index(drop=True)
report_indicator_sorted = report_indicator_df.sort_values(by='provider_id').reset_index(drop=True)

summary_score21 = pd.merge(summary_score1, report_indicator_sorted, on='provider_id', how='left')

summary_score22 = summary_score21[summary_score21['report_indicator'] == 1].copy()

def assign_cnt_grp(row):
    total_m_grp = row['Total_measure_group_cnt']
    if total_m_grp == 3:
        return '1) # of groups=3       '
    elif total_m_grp == 4:
        return '2) # of groups=4       '
    elif total_m_grp == 5:
        return '3) # of groups=5       '
    return np.nan

summary_score22['total_grp'] = (
    (summary_score22['Outcomes_Mortality_cnt'] >= 3).astype(int) +
    (summary_score22['Outcomes_safety_cnt'] >= 3).astype(int) +
    (summary_score22['Outcomes_Readmission_cnt'] >= 3).astype(int) +
    (summary_score22['Patient_Experience_cnt'] >= 3).astype(int) +
    (summary_score22['Process_cnt'] >= 3).astype(int)
)

summary_score22['cnt_grp'] = summary_score22.apply(assign_cnt_grp, axis=1)

cnt_s10 = summary_score22[summary_score22['cnt_grp'] == '1) # of groups=3       '].copy()
cnt_s1 = kmeans_clust(cnt_s10, 'cnt_s1', 'cnt_grp')['cnt_s1'] if len(cnt_s10) > 0 else pd.DataFrame(columns=['provider_id', 'Star', 'cnt_grp'])

cnt_s20 = summary_score22[summary_score22['cnt_grp'] == '2) # of groups=4       '].copy()
cnt_s2 = kmeans_clust(cnt_s20, 'cnt_s2', 'cnt_grp')['cnt_s2'] if len(cnt_s20) > 0 else pd.DataFrame(columns=['provider_id', 'Star', 'cnt_grp'])

cnt_s30 = summary_score22[summary_score22['cnt_grp'] == '3) # of groups=5       '].copy()
cnt_s3 = kmeans_clust(cnt_s30, 'cnt_s3', 'cnt_grp')['cnt_s3'] if len(cnt_s30) > 0 else pd.DataFrame(columns=['provider_id', 'Star', 'cnt_grp'])

cnt_s_str = pd.concat([cnt_s1, cnt_s2, cnt_s3], ignore_index=True)
cnt_s_str = cnt_s_str.sort_values(by='provider_id').reset_index(drop=True)

star_2025Jul = pd.merge(summary_score21, cnt_s_str, on='provider_id', how='left')

summary_avg_res = nation_avg0(star_2025Jul, 'summary_avg', 'Summary_Score_Nat')
summary_avg = summary_avg_res['summary_avg']

summary_avg_peer_res = nation_avg_peer(star_2025Jul, 'summary_avg_peer', 'Summary_Score_Nat', 'Total_measure_group_cnt')
summary_avg_peer = summary_avg_peer_res['summary_avg_peer']

outcome_mortality_avg = nation_avg(Outcome_mortality, 'outcome_mortality_avg', 'Out_Mrt_Grp_Score_Nat')['outcome_mortality_avg']
outcome_safety_avg = nation_avg(Outcome_safety, 'outcome_safety_avg', 'Out_Sft_Grp_Score_Nat')['outcome_safety_avg']
outcome_readmission_avg = nation_avg(Outcome_readmission, 'outcome_readmission_avg', 'Out_Readm_grp_Score_Nat')['outcome_readmission_avg']
ptexp_avg = nation_avg(PtExp, 'ptexp_avg', 'Pt_Exp_Grp_Score_Nat')['ptexp_avg']
process_avg = nation_avg(Process, 'process_avg', 'Prc_of_Care_Grp_Score_Nat')['process_avg']

national_average_2025Jul = pd.concat([
    summary_avg.reset_index(drop=True),
    summary_avg_peer.reset_index(drop=True),
    outcome_mortality_avg.reset_index(drop=True),
    outcome_safety_avg.reset_index(drop=True),
    outcome_readmission_avg.reset_index(drop=True),
    ptexp_avg.reset_index(drop=True),
    process_avg.reset_index(drop=True)
], axis=1)
