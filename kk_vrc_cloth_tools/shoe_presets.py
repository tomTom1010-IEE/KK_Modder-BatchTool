"""Reproducible, anatomically configured flat-shoe training/holdout poses."""
import copy
import math
import random

PRESET='FLAT_SHOE_V1'
STANDARD=[('ankle_up',20,0,0),('ankle_down',-20,0,0),
          ('tilt_in',0,0,10),('tilt_out',0,0,-10),
          ('forefoot_up',0,18,0),('forefoot_down',0,-12,0),
          ('combined',12,10,0)]
HOLDOUT=[('rest_check',0,0,0),('heldout_up',13,7,0),
         ('heldout_down',-14,-8,0),('heldout_tilt',5,11,7)]
RANGES=((-15.,15.),(-8.,12.),(-6.,6.))


def unit(v):
    if len(v)!=3 or not all(math.isfinite(x) for x in v):raise ValueError('Invalid anatomical axis')
    length=math.sqrt(sum(x*x for x in v))
    if length<1e-8:raise ValueError('Degenerate anatomical axis')
    return [x/length for x in v]


def axes(side):
    up=unit(side['up']);forward=unit(side['forward'])
    right=unit([up[1]*forward[2]-up[2]*forward[1],up[2]*forward[0]-up[0]*forward[2],up[0]*forward[1]-up[1]*forward[0]])
    sign=side.get('tilt_sign',{'L':1,'R':-1}.get(side['name']))
    if sign not in (-1,1):raise ValueError('Explicit left/right tilt_sign required')
    return right,forward,sign


def controls(side,angles):
    foot,toe,tilt=angles;right,forward,sign=axes(side);out=[]
    for bone,axis,angle in [(side['foot'],right,foot),(side['foot'],forward,tilt*sign),(side['toes'],right,toe)]:
        if angle:out.append({'bone':bone,'axis':axis,'degrees':angle})
    return out


def build(sides, *, random_enabled=True, random_count=6, random_weight=.15, seed=20260919):
    if not sides:raise ValueError('No anatomical sides')
    if type(random_count) is not int or not 0<=random_count<=64:raise ValueError('Random count must be 0..64')
    if not math.isfinite(random_weight) or not 0<random_weight<1:raise ValueError('Auxiliary weight must be positive and below standard weight 1')
    if type(seed) is not int:raise ValueError('Integer seed required')
    poses=[]
    for validation,entries in [(False,STANDARD),(True,HOLDOUT)]:
        for name,foot,toe,tilt in entries:
            poses.append({'name':name,'controls':[c for s in sides for c in controls(s,(foot,toe,tilt))],
                          'validation':validation,'weight':1.,'kind':'holdout' if validation else 'standard'})
    count=random_count if random_enabled else 0
    # Many small-weight samples must not collectively dominate the seven standards.
    effective=min(random_weight,.2*len(STANDARD)/count) if count else 0.
    rng=random.Random(seed)
    for i in range(count):
        ctrl=[];angles={}
        for side in sides:
            a=[rng.uniform(lo,hi) for lo,hi in RANGES]
            # Joint limits alone allow extreme compound corners; bound the joint
            # combination inside an ellipsoid, contracting toward neutral only.
            radius=math.sqrt(sum((v/max(abs(lo),abs(hi)))**2 for v,(lo,hi) in zip(a,RANGES)))
            if radius>1:a=[v/radius for v in a]
            angles[side['name']]=a;ctrl.extend(controls(side,a))
        poses.append({'name':f'aux_{i+1:02d}','controls':ctrl,'validation':False,
                      'weight':effective,'kind':'auxiliary','angles':angles})
    return poses,{'id':PRESET,'seed':seed,'random_count':count,'requested_weight':random_weight,
                  'effective_weight':effective,'auxiliary_total_weight':count*effective,
                  'standard_total_weight':float(len(STANDARD)),'ranges':RANGES,
                  'compound_limit':'unit ellipsoid','validation_randomized':False}


def resolve(config):
    out=copy.deepcopy(config);spec=out.get('pose_preset')
    if spec is None:return out
    if spec.get('id')!=PRESET:raise ValueError('Unknown shoe pose preset')
    args={k:v for k,v in spec.items() if k!='id'}
    out['poses'],out['pose_preset_resolved']=build(out['sides'],**args)
    return out
