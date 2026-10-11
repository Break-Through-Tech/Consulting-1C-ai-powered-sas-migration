# Load the preceding SAS stage and expose its public names here.
import importlib.util as _importlib_util
import sys as _sys
from pathlib import Path as _Path

_previous_name = '_translated_sas_stage_00'
_previous_path = _Path(__file__).with_name('Star_Macros.py')
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

path1 = r"\\...\Starrating"
path2 = r"C:\Users\...\2025 Jul\SAS output"
path3 = r"C:\Users\...\2025 Jul\SAS pack"

year = 2025
quarter = "Jul"

measure_all = [
    'MORT_30_AMI', 'MORT_30_CABG', 'MORT_30_COPD', 'MORT_30_HF', 'MORT_30_PN', 'MORT_30_STK', 'PSI_4_SURG_COMP',
    'COMP_HIP_KNEE', 'HAI_1', 'HAI_2', 'HAI_3', 'HAI_4', 'HAI_5', 'HAI_6', 'PSI_90_SAFETY',
    'EDAC_30_AMI', 'EDAC_30_HF', 'EDAC_30_PN', 'OP_32', 'READM_30_CABG', 'READM_30_COPD', 'READM_30_HIP_KNEE', 
    'READM_30_HOSP_WIDE', 'OP_35_ADM', 'OP_35_ED', 'OP_36',
    'H_COMP_1_STAR_RATING', 'H_COMP_2_STAR_RATING', 'H_COMP_3_STAR_RATING', 'H_COMP_5_STAR_RATING', 
    'H_COMP_6_STAR_RATING', 'H_COMP_7_STAR_RATING', 'H_GLOB_STAR_RATING', 'H_INDI_STAR_RATING',
    'HCP_COVID_19', 'IMM_3', 'OP_10', 'OP_13', 'OP_18B', 'OP_22', 'OP_23', 'OP_29', 'OP_8', 'PC_01', 
    'SAFE_USE_OF_OPIOIDS', 'SEP_1'
]

if 'HC_Alldata_2025Jul' in globals():
    all_data = HC_Alldata_2025Jul.copy()
else:
    all_data = pd.DataFrame(columns=['provider_id'] + measure_all)

measure_volume0 = all_data[measure_all].notna().sum().reset_index()
measure_volume0.columns = ['_NAME_', 'COL1']

measure_volume_t0 = measure_volume0.set_index('_NAME_').T.reset_index(drop=True)

include_measure0_list = []
for col in measure_all:
    if col in measure_volume0['_NAME_'].values:
        freq = measure_volume0.loc[measure_volume0['_NAME_'] == col, 'COL1'].values[0]
        include_measure0_list.append({
            'measure_in_name': col,
            'measure_in_std': f'std_{col}',
            'freq': freq
        })

include_measure0 = pd.DataFrame(include_measure0_list)
measure_in = include_measure0['measure_in_name'].tolist()
measure_cnt = len(measure_in)

measure_volume = measure_volume0.copy()
measure_volume_t = measure_volume_t0.copy()

less100_measure = include_measure0[include_measure0['freq'] <= 100].copy()
less100_measure = less100_measure.rename(columns={'measure_in_name': 'measure_name'})
less100_measure = less100_measure[['measure_name', 'freq']]

measure_exclude = less100_measure['measure_name'].tolist()
nobs = len(less100_measure)

initial_data_2025Jul = all_data.copy()
if nobs > 0 and measure_exclude:
    initial_data_2025Jul = initial_data_2025Jul.drop(columns=[m for m in measure_exclude if m in initial_data_2025Jul.columns])

include_measure = include_measure0[include_measure0['freq'] > 100].copy()
measure_in = include_measure['measure_in_name'].tolist()
measure_in_std = include_measure['measure_in_std'].tolist()
measure_cnt = len(measure_in)

om_list = ['MORT_30_AMI', 'MORT_30_CABG', 'MORT_30_COPD', 'MORT_30_HF', 'MORT_30_PN', 'MORT_30_STK', 'PSI_4_SURG_COMP']
os_list = ['COMP_HIP_KNEE', 'HAI_1', 'HAI_2', 'HAI_3', 'HAI_4', 'HAI_5', 'HAI_6', 'PSI_90_SAFETY']
or_list = ['EDAC_30_AMI', 'EDAC_30_HF', 'EDAC_30_PN', 'OP_32', 'READM_30_CABG', 'READM_30_COPD', 'READM_30_HIP_KNEE', 'READM_30_HOSP_WIDE', 'OP_35_ADM', 'OP_35_ED', 'OP_36']
pt_list = ['H_COMP_1_STAR_RATING', 'H_COMP_2_STAR_RATING', 'H_COMP_3_STAR_RATING', 'H_COMP_5_STAR_RATING', 'H_COMP_6_STAR_RATING', 'H_COMP_7_STAR_RATING', 'H_GLOB_STAR_RATING', 'H_INDI_STAR_RATING']
proc_list = ['HCP_COVID_19', 'IMM_3', 'OP_10', 'OP_13', 'OP_18B', 'OP_22', 'OP_23', 'OP_29', 'OP_8', 'PC_01', 'SAFE_USE_OF_OPIOIDS', 'SEP_1']

def get_std_subset(names):
    return [f'std_{m}' for m in names if m in measure_in]

measure_OM = get_std_subset(om_list)
measure_OS = get_std_subset(os_list)
measure_OR = get_std_subset(or_list)
measure_PtExp = get_std_subset(pt_list)
measure_Process = get_std_subset(proc_list)

initial_data_2025Jul = keep_hos(initial_data_2025Jul, measure_in, measure_cnt)

measure_mean_df = initial_data_2025Jul[measure_in].describe().reset_index()

std_data_2025Jul = initial_data_2025Jul.copy()
for m in measure_in:
    s = std_data_2025Jul[m]
    mean_val = s.mean()
    std_val = s.std(ddof=1)
    if std_val != 0 and not pd.isna(std_val):
        std_data_2025Jul[m] = (s - mean_val) / std_val
    else:
        std_data_2025Jul[m] = 0.0

flip_measures = [
    'MORT_30_AMI', 'MORT_30_CABG', 'MORT_30_COPD', 'MORT_30_HF', 'MORT_30_PN', 'MORT_30_STK', 'PSI_4_SURG_COMP',
    'COMP_HIP_KNEE', 'HAI_1', 'HAI_2', 'HAI_3', 'HAI_4', 'HAI_5', 'HAI_6', 'PSI_90_SAFETY',
    'EDAC_30_AMI', 'EDAC_30_HF', 'EDAC_30_PN', 'OP_32', 'READM_30_CABG', 'READM_30_COPD', 'READM_30_HIP_KNEE', 
    'READM_30_HOSP_WIDE', 'OP_35_ADM', 'OP_35_ED', 'OP_36',
    'OP_22', 'PC_01', 'OP_18B', 'OP_8', 'OP_10', 'OP_13', 'SAFE_USE_OF_OPIOIDS'
]

for m in flip_measures:
    if m in std_data_2025Jul.columns:
        std_data_2025Jul[m] = -std_data_2025Jul[m]

std_data_2025Jul_analysis = std_data_2025Jul.copy()
for m, std_m in zip(measure_in, measure_in_std):
    if m in std_data_2025Jul_analysis.columns:
        std_data_2025Jul_analysis[std_m] = std_data_2025Jul_analysis[m]

std_data_2025Jul_analysis = std_data_2025Jul_analysis.drop(columns=measure_in)
