import unittest, importlib.util
from pathlib import Path
spec=importlib.util.spec_from_file_location('accessory_rules',Path(__file__).resolve().parents[1]/'kk_vrc_cloth_tools/accessory_rules.py')
r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
def b(n,p=None,d=(),helper=False):return {'name':n,'parent':p,'dependencies':d,'helper':helper}
class Tests(unittest.TestCase):
    def test_fixed_anchor_boundary(self):
        p=r.plan([b('body','parent'),b('parent'),b('chain','body'),b('tip','chain')],['body','chain'],['chain'],['body'])
        self.assertEqual(p['owned'],['chain','tip']);self.assertEqual(p['anchors'],['body']);self.assertEqual(p['remove'],['parent'])
    def test_unknown_weighted_rejected(self):
        with self.assertRaises(ValueError):r.plan([b('unknown')],['unknown'])
    def test_multi_anchor_no_collapse(self):
        p=r.plan([b('neck'),b('chest')],['neck','chest'],external=['neck','chest'])
        self.assertTrue(p['multi_anchor']);self.assertEqual(len(p['anchors']),2)
    def test_cross_asset_parent_explicit(self):
        bones=[b('skirt'),b('rope','skirt')]
        with self.assertRaises(ValueError):r.plan(bones,['rope'],['rope'])
        self.assertEqual(r.plan(bones,['rope'],['rope'],['skirt'])['anchors'],['skirt'])
    def test_helper_closure(self):
        bones=[b('body'),b('chain','body',['shadow']),b('shadow','body',['dummy'],True),b('dummy','body',helper=True)]
        self.assertEqual(set(r.plan(bones,['chain'],['chain'],['body'])['owned']),{'chain','shadow','dummy'})
    def test_exact_weight_remap(self):
        rows=[{'body':.15,'dynamic':.85},{'body':1.},{'dynamic':1.}]
        out=r.remap(rows,{'body':'root'})
        self.assertEqual(out[0],{'root':.15,'dynamic':.85});self.assertEqual(out[2],rows[2])
    def test_collision_accumulates(self):self.assertEqual(r.remap([{'a':.2,'b':.3,'c':.5}],{'a':'r','b':'r'}),[{'r':.5,'c':.5}])
    def test_invalid_weights(self):
        for w in [-1,float('nan')]:
            with self.assertRaises(ValueError):r.remap([{'b':w}],{})
if __name__=='__main__':unittest.main()
