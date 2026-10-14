"""Load all translated SAS stages in dependency order."""
import importlib.util as _importlib_util
import sys as _sys
from pathlib import Path as _Path

_stage_files = [
    'Star_Macros.py',
    '0 - Data and Measure Standardization_2025Jul.py',
    '1 - First stage_Simple Average of Measure Scores_2025Jul.py',
    '2 - Second Stage_Weighted Average and Categorize Star_2025Jul.py',
]
for _stage_index, _stage_filename in enumerate(_stage_files):
    _stage_name = f"_translated_sas_stage_{_stage_index:02d}"
    _stage_module = _sys.modules.get(_stage_name)
    if _stage_module is None:
        _stage_path = _Path(__file__).with_name(_stage_filename)
        _stage_spec = _importlib_util.spec_from_file_location(_stage_name, _stage_path)
        if _stage_spec is None or _stage_spec.loader is None:
            raise ImportError(f"Could not load translated stage: {_stage_path}")
        _stage_module = _importlib_util.module_from_spec(_stage_spec)
        _sys.modules[_stage_name] = _stage_module
        try:
            _stage_spec.loader.exec_module(_stage_module)
        except Exception:
            del _sys.modules[_stage_name]
            raise
    globals().update({name: value for name, value in vars(_stage_module).items()
                      if not name.startswith("_")})

del _importlib_util, _sys, _Path, _stage_files, _stage_index
del _stage_filename, _stage_name, _stage_module
