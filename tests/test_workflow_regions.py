import unittest,sys,importlib,types
from pathlib import Path
pkg=types.ModuleType('workflow_test_package');pkg.__path__=[str(Path(__file__).resolve().parents[1]/'kk_vrc_cloth_tools')];sys.modules[pkg.__name__]=pkg
regions=importlib.import_module(pkg.__name__+'.workflow_regions')
core=importlib.import_module(pkg.__name__+'.weight_features')

class RegionTests(unittest.TestCase):
    def setUp(self):
        self.rows=[{'Body':.5,'Cloth':.5}]*3;self.roles={'Body':'BODY','Cloth':'DYNAMIC'}
    def test_chain_and_explicit_mask(self):
        r=[{'name':'root','mode':'UNIFORM','bones':['Cloth']}]
        self.assertEqual(regions.resolve_regions(self.rows,self.roles,r),dict.fromkeys(range(3),'UNIFORM'))
        r=[{'name':'a','mode':'UNIFORM','vertices':[0]},{'name':'b','mode':'EDGE_GRADIENT','vertices':[1,2]}]
        self.assertEqual(regions.resolve_regions(self.rows,self.roles,r)[2],'EDGE_GRADIENT')
    def test_conflict_unknown_uncovered(self):
        for r in [[{'name':'x','mode':'REVIEW','bones':['Cloth']}],[],
                  [{'name':'a','mode':'UNIFORM','bones':['Cloth']},{'name':'b','mode':'EDGE_GRADIENT','vertices':[0]}]]:
            with self.assertRaises(ValueError):regions.resolve_regions(self.rows,self.roles,r)
    def test_explicit_gradient_overrides_stable_heuristic_without_budget_drift(self):
        snapshot=core.snapshot(self.rows,[[0,1],[1,2]],self.roles,'topo')
        args=(snapshot,{'Body':{'A':1}},{'Cloth':{'Cloth':1}},{'A','B'},{'Body':'TORSO'},{'A':'TORSO','B':'TORSO'})
        for mode,dest in [('UNIFORM','A'),('EDGE_GRADIENT','B')]:
            p=core.plan_regions(*args,samples={i:{'B':1} for i in range(3)},confidence=dict.fromkeys(range(3),1),region_modes=dict.fromkeys(range(3),mode))
            for row in p['writes'].values():self.assertEqual(row,{dest:.5,'Cloth':.5})
    def test_pure_dynamic_needs_no_body_mode(self):
        self.assertEqual(regions.resolve_regions([{'Cloth':1}],self.roles,[]),{})

if __name__=='__main__':unittest.main()
