# Load the preceding SAS stage and expose its public names here.
import importlib.util as _importlib_util
import sys as _sys
from pathlib import Path as _Path

_previous_name = '_translated_sas_stage_01'
_previous_path = _Path(__file__).with_name('0 - Data and Measure Standardization_2025Jul.py')
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

measure_OM_cnt = len(measure_OM)
Outcome_mortality_res = grp_score(std_data_2025Jul_analysis, 'OM', measure_OM, measure_OM_cnt, 'R.Outcome_mortality')
Outcome_mortality = Outcome_mortality_res['R.Outcome_mortality']

measure_OS_cnt = len(measure_OS)
Outcome_safety_res = grp_score(std_data_2025Jul_analysis, 'OS', measure_OS, measure_OS_cnt, 'R.Outcome_safety')
Outcome_safety = Outcome_safety_res['R.Outcome_safety']

measure_OR_cnt = len(measure_OR)
Outcome_readmission_res = grp_score(std_data_2025Jul_analysis, 'OR', measure_OR, measure_OR_cnt, 'R.Outcome_readmission')
Outcome_readmission = Outcome_readmission_res['R.Outcome_readmission']

measure_PtExp_cnt = len(measure_PtExp)
PtExp_res = grp_score(std_data_2025Jul_analysis, 'PtExp', measure_PtExp, measure_PtExp_cnt, 'R.PtExp')
PtExp = PtExp_res['R.PtExp']

measure_Process_cnt = len(measure_Process)
Process_res = grp_score(std_data_2025Jul_analysis, 'Process', measure_Process, measure_Process_cnt, 'R.Process')
Process = Process_res['R.Process']
