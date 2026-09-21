import importlib.util
import json
from pathlib import Path
import unittest

ROOT=Path(__file__).parents[1]
spec=importlib.util.spec_from_file_location('shoe_presets',ROOT/'kk_vrc_cloth_tools/shoe_presets.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
CONFIG=json.loads((ROOT/'examples/flat_shoe_neon_vertex.json').read_text(encoding='utf-8-sig'))


class ShoePresetTests(unittest.TestCase):
    def test_preserves_accepted_standard_and_holdout(self):
        poses,meta=m.build(CONFIG['sides'])
        for old,new in zip(CONFIG['poses'],poses):
            for key in ['name','controls','validation']:self.assertEqual(old[key],new[key])
        self.assertEqual(sum(p['kind']=='standard' for p in poses),7)
        self.assertEqual(sum(p['kind']=='holdout' for p in poses),4)
        self.assertEqual(sum(p['kind']=='auxiliary' for p in poses),6)
        self.assertEqual(meta['effective_weight'],.15)

    def test_reproducibility_and_bounds(self):
        a,meta=m.build(CONFIG['sides'],random_count=64)
        self.assertEqual(a,m.build(CONFIG['sides'],random_count=64)[0])
        self.assertNotEqual(a,m.build(CONFIG['sides'],random_count=64,seed=7)[0])
        self.assertLessEqual(meta['auxiliary_total_weight'],.2*meta['standard_total_weight']+1e-12)
        for p in a:
            if p['kind']!='auxiliary':continue
            self.assertFalse(p['validation']);self.assertLess(p['weight'],1)
            for v in p['angles'].values():
                for x,(lo,hi) in zip(v,m.RANGES):self.assertTrue(lo<=x<=hi)
                self.assertLessEqual(sum((x/max(abs(lo),abs(hi)))**2 for x,(lo,hi) in zip(v,m.RANGES)),1+1e-12)

    def test_custom_axes_and_bones(self):
        side={'name':'custom','up':[0,1,0],'forward':[0,0,1],'foot':'Ankle','toes':'Forefoot','tilt_sign':1}
        poses,_=m.build([side],random_enabled=False)
        self.assertEqual(poses[0]['controls'],[{'bone':'Ankle','axis':[1.,0.,0.],'degrees':20}])
        self.assertEqual(len(poses),11)

    def test_old_config_and_invalid_options(self):
        legacy={k:v for k,v in CONFIG.items() if k!='pose_preset'}
        self.assertEqual(m.resolve(legacy),legacy)
        for args in [{'random_weight':1.},{'random_weight':float('nan')},{'random_count':-1},{'seed':1.1}]:
            with self.assertRaises(ValueError):m.build(CONFIG['sides'],**args)
        with self.assertRaises(ValueError):m.resolve({'pose_preset':{'id':'UNKNOWN'}})

if __name__=='__main__':unittest.main()
