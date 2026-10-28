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

import pandas as pd
import numpy as np

path1 = "src/translation/sas_files"
path2 = "translation/sas_files"
path3 = "translation/sas_files"

year = 2025
quarter = "jul"

measure_mean = f"measure_average_stddev_{year}{quarter}"
measure_analysis = f"Std_data_{year}{quarter}_analysis"
results_ds = f"Star_{year}{quarter}"
national_mean = f"national_average_{year}{quarter}"

measure_all_list = [
    "MORT_30_AMI", "MORT_30_CABG", "MORT_30_COPD", "MORT_30_HF", "MORT_30_PN", "MORT_30_STK", "PSI_4_SURG_COMP",
    "COMP_HIP_KNEE", "HAI_1", "HAI_2", "HAI_3", "HAI_4", "HAI_5", "HAI_6", "PSI_90_SAFETY",
    "EDAC_30_AMI", "EDAC_30_HF", "EDAC_30_PN", "OP_32", "READM_30_CABG", "READM_30_COPD", "READM_30_HIP_KNEE", "READM_30_HOSP_WIDE", "OP_35_ADM", "OP_35_ED", "OP_36",
    "H_COMP_1_STAR_RATING", "H_COMP_2_STAR_RATING", "H_COMP_3_STAR_RATING", "H_COMP_5_STAR_RATING", "H_COMP_6_STAR_RATING", "H_COMP_7_STAR_RATING", "H_GLOB_STAR_RATING", "H_INDI_STAR_RATING",
    "HCP_COVID_19", "IMM_3", "OP_10", "OP_13", "OP_18B", "OP_22", "OP_23", "OP_29", "OP_8", "PC_01", "SAFE_USE_OF_OPIOIDS", "SEP_1"
]

all_data_file = f"{path1}/alldata_{year}{quarter}.csv"
try:
    all_data_2025Jul = pd.read_csv(all_data_file)
    all_data_2025Jul.columns = all_data_2025Jul.columns.str.upper()
    all_data_2025Jul = all_data_2025Jul.rename(columns={"PROVIDER_ID": "provider_id"})
except Exception as e:
    print("Error loading CSV:", repr(e))
    all_data_2025Jul = pd.DataFrame(columns=['provider_id'] + measure_all_list)
measure_volume0 = pd.DataFrame({
    'freq': [all_data_2025Jul[m].notna().sum() if m in all_data_2025Jul.columns else 0 for m in measure_all_list]
}, index=measure_all_list)

include_measure0 = measure_volume0.reset_index().rename(columns={'index': 'measure_in_name', 'freq': 'freq'})
include_measure0['measure_in_std'] = 'std_' + include_measure0['measure_in_name'].astype(str)

measure_in = " ".join(include_measure0['measure_in_name'].tolist())
measure_cnt = len(include_measure0)

measure_volume = measure_volume0.copy()

less100_measure = measure_volume[measure_volume['freq'] <= 100].reset_index().rename(columns={'index': 'measure_name', 'freq': 'freq'})
measure_exclude = " ".join(less100_measure['measure_name'].tolist())
nobs = len(less100_measure)

initial_data_2025Jul = all_data_2025Jul.copy()
if nobs > 0 and measure_exclude.strip() != "":
    cols_to_drop = measure_exclude.split()
    initial_data_2025Jul = initial_data_2025Jul.drop(columns=[c for c in cols_to_drop if c in initial_data_2025Jul.columns])

include_measure = measure_volume[measure_volume['freq'] > 100].reset_index().rename(columns={'index': 'measure_in_name', 'freq': 'freq'})
include_measure['measure_in_std'] = 'std_' + include_measure['measure_in_name'].astype(str)

measure_in = " ".join(include_measure['measure_in_name'].tolist())
measure_in_std = " ".join(include_measure['measure_in_std'].tolist())
measure_cnt = len(include_measure)

om_names = ['MORT_30_AMI', 'MORT_30_CABG', 'MORT_30_COPD', 'MORT_30_HF', 'MORT_30_PN', 'MORT_30_STK', 'PSI_4_SURG_COMP']
os_names = ['COMP_HIP_KNEE', 'HAI_1', 'HAI_2', 'HAI_3', 'HAI_4', 'HAI_5', 'HAI_6', 'PSI_90_SAFETY']
or_names = ['EDAC_30_AMI', 'EDAC_30_HF', 'EDAC_30_PN', 'OP_32', 'READM_30_CABG', 'READM_30_COPD', 'READM_30_HIP_KNEE', 'READM_30_HOSP_WIDE', 'OP_35_ADM', 'OP_35_ED', 'OP_36']
pt_names = ['H_COMP_1_STAR_RATING', 'H_COMP_2_STAR_RATING', 'H_COMP_3_STAR_RATING', 'H_COMP_5_STAR_RATING', 'H_COMP_6_STAR_RATING', 'H_COMP_7_STAR_RATING', 'H_GLOB_STAR_RATING', 'H_INDI_STAR_RATING']
pc_names = ['HCP_COVID_19', 'IMM_3', 'OP_10', 'OP_13', 'OP_18B', 'OP_22', 'OP_23', 'OP_29', 'OP_8', 'PC_01', 'SAFE_USE_OF_OPIOIDS', 'SEP_1']

def filter_group(names):
    sub = measure_volume.loc[measure_volume.index.isin(names)]
    sub = sub[sub['freq'] > 100]
    std_list = ['std_' + idx for idx in sub.index]
    return " ".join(std_list)

measure_OM = filter_group(om_names)
nmeasure_OM = len(om_names)

measure_OS = filter_group(os_names)
nmeasure_OS = len(os_names)

measure_OR = filter_group(or_names)
nmeasure_OR = len(or_names)

measure_PtExp = filter_group(pt_names)
nmeasure_PtExp = len(pt_names)

measure_Process = filter_group(pc_names)
nmeasure_Process = len(pc_names)

initial_data_2025Jul = keep_hos(initial_data_2025Jul, measure_in, measure_cnt)

measure_in_list = measure_in.split()
stats = initial_data_2025Jul[measure_in_list].agg(
    ['count', 'min', 'max', 'mean', 'std']
)

stats.index = ['N', 'MIN', 'MAX', 'MEAN', 'STD']
stats.insert(0, '_STAT_', stats.index)
stats.insert(0, '_FREQ_', len(initial_data_2025Jul))
stats.insert(0, '_TYPE_', 0)

globals()[measure_mean] = stats.reset_index(drop=True)

std_data_2025Jul = initial_data_2025Jul.copy()
for m in measure_in_list:
    if m in std_data_2025Jul.columns:
        col_data = std_data_2025Jul[m]
        mean_v = col_data.mean()
        std_v = col_data.std(ddof=1)
        if std_v != 0 and pd.notna(std_v):
            std_data_2025Jul[m] = (col_data - mean_v) / std_v
        else:
            std_data_2025Jul[m] = 0.0

flip_measures = [
    'MORT_30_AMI', 'MORT_30_CABG', 'MORT_30_COPD', 'MORT_30_HF', 'MORT_30_PN', 'MORT_30_STK', 'PSI_4_SURG_COMP',
    'COMP_HIP_KNEE', 'HAI_1', 'HAI_2', 'HAI_3', 'HAI_4', 'HAI_5', 'HAI_6', 'PSI_90_SAFETY',
    'EDAC_30_AMI', 'EDAC_30_HF', 'EDAC_30_PN', 'OP_32', 'READM_30_CABG', 'READM_30_COPD', 'READM_30_HIP_KNEE', 'READM_30_HOSP_WIDE', 'OP_35_ADM', 'OP_35_ED', 'OP_36',
    'OP_22', 'PC_01', 'OP_18B', 'OP_8', 'OP_10', 'OP_13', 'SAFE_USE_OF_OPIOIDS'
]

for m in flip_measures:
    if m in std_data_2025Jul.columns:
        std_data_2025Jul[m] = -std_data_2025Jul[m]

measure_in_std_list = measure_in_std.split()
analysis_df = std_data_2025Jul.copy()
for i, m in enumerate(measure_in_list):
    if i < len(measure_in_std_list):
        std_col = measure_in_std_list[i]
        analysis_df[std_col] = analysis_df[m]

drop_cols = measure_in_list + [c for c in analysis_df.columns if c in ['i']]
analysis_df = analysis_df.drop(columns=[c for c in drop_cols if c in analysis_df.columns])

globals()[measure_analysis] = analysis_df