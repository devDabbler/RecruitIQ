# quick import check for frontend modules
import importlib, sys
ROOT = r"c:\Users\seaso\RecruitIQ"
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
mods = [
    'frontend.modules.candidates',
    'frontend.modules.job_detail',
    'frontend.modules.candidate_detail',
    'frontend.modules.interviews_page',
    'frontend.modules.assistant',
]
for m in mods:
    try:
        importlib.import_module(m)
        print('OK:', m)
    except Exception as e:
        print('ERR:', m, '->', repr(e))
