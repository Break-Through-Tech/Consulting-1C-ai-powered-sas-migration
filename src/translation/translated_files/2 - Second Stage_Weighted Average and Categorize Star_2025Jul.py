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

import pandas as pd
import numpy as np

def merge_dfs(left, right, on):
    if left is None:
        return right
    if right is None:
        return left
    return pd.merge(left, right, on=on, how='outer')

all_df = None
for ds_name in ['Outcome_mortality', 'Outcome_readmission', 'Outcome_safety', 'PtExp', 'Process']:
    df = globals().get(ds_name)
    if df is not None:
        sub = df[['provider_id', 'grp_score']].copy()
        if ds_name == 'Outcome_mortality':
            sub = sub.rename(columns={'grp_score': 'Std_Outcomes_Mortality_score'})
        elif ds_name == 'Outcome_readmission':
            sub = sub.rename(columns={'grp_score': 'Std_Outcomes_Readmission_score'})
        elif ds_name == 'Outcome_safety':
            sub = sub.rename(columns={'grp_score': 'Std_Outcomes_Safety_score'})
        elif ds_name == 'PtExp':
            sub = sub.rename(columns={'grp_score': 'Std_PatientExp_score'})
        elif ds_name == 'Process':
            sub = sub.rename(columns={'grp_score': 'Std_Process_score'})
        all_df = merge_dfs(all_df, sub, 'provider_id')

summary_score = all_df.copy()
std_w1 = 0.22
std_w2 = 0.22
std_w3 = 0.22
std_w4 = 0.22
std_w5 = 0.12

scores_cols = [
    'Std_PatientExp_score', 'Std_Outcomes_Readmission_score', 
    'Std_Outcomes_Mortality_score', 'Std_Outcomes_Safety_score', 'Std_Process_score'
]
std_weights = [std_w1, std_w2, std_w3, std_w4, std_w5]

def calc_summary(row):
    grp_scores = [row.get(c, np.nan) for c in scores_cols]
    I = [1 if pd.isna(g) else 0 for g in grp_scores]
    denom = 1.0 - sum(I[k] * std_weights[k] for k in range(5))
    
    weights = []
    for k in range(5):
        if pd.isna(grp_scores[k]):
            weights.append(np.nan)
        else:
            weights.append(std_weights[k] / denom if denom > 0 else np.nan)
            
    sum_wt_aves = []
    for k in range(5):
        if pd.isna(weights[k]):
            sum_wt_aves.append(0.0)
        else:
            sum_wt_aves.append(weights[k] * grp_scores[k])
            
    return sum(sum_wt_aves)

summary_score['summary_score'] = summary_score.apply(calc_summary, axis=1)

report(
    globals()[measure_analysis], 'report_indicator', 
    nmeasure_OM, nmeasure_OS, nmeasure_OR, nmeasure_PtExp, nmeasure_Process,
    measure_OM, measure_OS, measure_OR, measure_PtExp, measure_Process
)
report_indicator_df = globals()['report_indicator']

summary_score1 = summary_score.sort_values(by='provider_id').copy()
report_indicator_sorted = report_indicator_df.sort_values(by='provider_id').copy()

summary_score21 = pd.merge(summary_score1, report_indicator_sorted, on='provider_id', how='left')

summary_score22 = summary_score21[summary_score21['report_indicator'] == 1].copy()

summary_score22['total_grp'] = (
    (summary_score22['Outcomes_Mortality_cnt'] >= 3).astype(int) + 
    (summary_score22['Outcomes_safety_cnt'] >= 3).astype(int) + 
    (summary_score22['Outcomes_Readmission_cnt'] >= 3).astype(int) + 
    (summary_score22['Patient_Experience_cnt'] >= 3).astype(int) + 
    (summary_score22['Process_cnt'] >= 3).astype(int)
)

def assign_cnt_grp(val):
    if val == 3:
        return '1) # of groups=3       '
    elif val == 4:
        return '2) # of groups=4       '
    elif val == 5:
        return '3) # of groups=5       '
    return np.nan

summary_score22['cnt_grp'] = summary_score22['Total_measure_group_cnt'].apply(assign_cnt_grp)

cnt_s10 = summary_score22[summary_score22['cnt_grp'] == '1) # of groups=3       '].copy()
cnt_s1 = kmeans(cnt_s10, 'cnt_s1', grp='cnt_grp')

cnt_s20 = summary_score22[summary_score22['cnt_grp'] == '2) # of groups=4       '].copy()
cnt_s2 = kmeans(cnt_s20, 'cnt_s2', grp='cnt_grp')

cnt_s30 = summary_score22[summary_score22['cnt_grp'] == '3) # of groups=5       '].copy()
cnt_s3 = kmeans(cnt_s30, 'cnt_s3', grp='cnt_grp')

cnt_s_str = pd.concat([cnt_s1, cnt_s2, cnt_s3], ignore_index=True).sort_values(by='provider_id')

results_final = pd.merge(summary_score21, cnt_s_str, on='provider_id', how='left')
globals()[results_ds] = results_final

summary_avg = nation_avg0(results_final, 'summary_avg', 'Summary_Score_Nat')
summary_avg_peer = nation_avg_peer(results_final, 'summary_avg_peer', 'Summary_Score_Nat', 'Total_measure_group_cnt')

outcome_mortality_avg = nation_avg(globals().get('Outcome_mortality'), 'outcome_mortality_avg', 'Out_Mrt_Grp_Score_Nat')
outcome_safety_avg = nation_avg(globals().get('Outcome_safety'), 'outcome_safety_avg', 'Out_Sft_Grp_Score_Nat')
outcome_readmission_avg = nation_avg(globals().get('Outcome_readmission'), 'outcome_readmission_avg', 'Out_Readm_grp_Score_Nat')
ptexp_avg = nation_avg(globals().get('Outcome_mortality'), 'ptexp_avg', 'Pt_Exp_Grp_Score_Nat') if globals().get('Outcome_mortality') is not None else pd.DataFrame({'Pt_Exp_Grp_Score_Nat': [np.nan]})
if globals().get('PtExp') is not None:
    ptexp_avg = nation_avg(globals().get('PtExp'), 'ptexp_avg', 'Pt_Exp_Grp_Score_Nat')

process_avg = nation_avg(globals().get('Process'), 'process_avg', 'Prc_of_Care_Grp_Score_Nat')

nat_mean_parts = [summary_avg, summary_avg_peer, outcome_mortality_avg, outcome_safety_avg, outcome_readmission_avg, ptexp_avg, process_avg]
national_mean_df = pd.concat([p.reset_index(drop=True) for p in nat_mean_parts if p is not None], axis=1)
globals()[national_mean] = national_mean_df
