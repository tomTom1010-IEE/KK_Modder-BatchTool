"""Read-only shoe A checkpoint test in factory Blender; no scene fixture needed.

blender --background --factory-startup --python this.py -- CHECKPOINT_DIR OUT_DIR
"""
import sys,json,time
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from kk_vrc_cloth_tools import shoe_workflow as shoe
from kk_vrc_cloth_tools.influence_policy import audit

source,out=map(Path,sys.argv[sys.argv.index('--')+1:])
if source.resolve()==out.resolve():raise ValueError('Use a separate output directory')
meta=json.loads((source/'field-context.json').read_text(encoding='utf-8'))
with np.load(source/'field-context.npz') as z:a={k:z[k] for k in z.files}
config=meta['config'];config['influence_policy']={'max_influences':4,'compress_dynamic':False}
contexts=[]
for i in range(len(config['sides'])):
    prefix=f'ctx_{i}_';contexts.append({k[len(prefix):]:v for k,v in a.items() if k.startswith(prefix)})
start=time.perf_counter()
w,rep=shoe.constrain_field(a['output'],meta['names'],config,contexts,None,None,a['xyz'],a['ct'],a['bt'])
body_error=max(float(np.max(abs(w[:,ctx['j']].sum(1)-a['output'][:,ctx['j']].sum(1)))) for ctx in contexts)
dynamic=[meta['names'].index(n) for side in config['sides'] for n in side['dynamic']]
dynamic_error=float(np.max(abs(w[:,dynamic]-a['output'][:,dynamic])))
report=dict(rep,vertices=len(w),seconds=time.perf_counter()-start,body_budget_error=body_error,
            dynamic_error=dynamic_error,before=audit(a['output'],config['influence_policy']),
            collision_validation='NOT_RUN',runtime_validation='NOT_TESTED')
out.mkdir(parents=True,exist_ok=True)
np.savez_compressed(out/'candidate.npz',weights=w)
(out/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
assert body_error<1e-6 and dynamic_error==0
assert rep['strict_compatible'],rep
print(json.dumps({k:report[k] for k in ['vertices','seconds','body_budget_error','dynamic_error','strict_compatible','maximum']}))
