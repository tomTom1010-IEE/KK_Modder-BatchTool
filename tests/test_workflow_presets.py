import unittest,importlib,types,sys
from pathlib import Path
pkg=types.ModuleType('preset_test_package');pkg.__path__=[str(Path(__file__).resolve().parents[1]/'kk_vrc_cloth_tools')];sys.modules[pkg.__name__]=pkg
p=importlib.import_module(pkg.__name__+'.workflow_presets')

class PresetTests(unittest.TestCase):
    def test_unweighted_first_segment(self):
        parents={'Body':None,'Root':'Body','Second':'Root','Tip':'Second'}
        result=p.discover_roots(parents,{'Body':'BODY','Second':'DYNAMIC','Tip':'DYNAMIC'},{'Second','Tip'})
        self.assertEqual(result,{'Root':['Second','Tip']})
    def test_body_boundary_and_sibling_chains(self):
        parents={'Body':None,'A':'Body','A1':'A','B':'Body','B1':'B','Support':'Body'}
        r=p.discover_roots(parents,{'Body':'BODY','A1':'REVIEW','B1':'DYNAMIC'},{'A1','B1','Support'},['Support'])
        self.assertEqual(set(r),{'A','B'})
    def test_templates_have_semantic_slots_and_no_dynamic_motion(self):
        self.assertEqual(len(p.motion_templates('WRIST')),6)
        self.assertTrue(all(row[-1] for row in p.motion_templates('WRIST')))
        self.assertFalse(any(row[-1] for row in p.motion_templates('FULL')))
        self.assertEqual(len(p.motion_templates('FULL')),15)
    def test_unweighted_organizational_root(self):
        parents={'Body':None,'Container':'Body','A':'Container','A1':'A','B':'Container','B1':'B'}
        roles={'Body':'BODY','A1':'REVIEW','B1':'REVIEW'}
        self.assertEqual(p.discover_roots(parents,roles,{'A1','B1'}),{'A':['A1'],'B':['B1']})
        roles['Container']='DYNAMIC'
        self.assertEqual(p.discover_roots(parents,roles,{'A1','B1'}),{'Container':['A1','B1']})

if __name__=='__main__':unittest.main()
