import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('region_patterns',Path(__file__).resolve().parents[1]/'kk_vrc_cloth_tools/region_patterns.py')
p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)

def strip(values,internal=None,offset=0):
    rows=[];edges=[];width=4
    for y,b in enumerate(values):
        for x in range(width):
            i=y*width+x
            row={'Body':b,'Dynamic':1-b} if internal is None else internal(y,x,b)
            rows.append(row)
            if x:edges.append((offset+i-1,offset+i))
            if y:edges.append((offset+i-width,offset+i))
    return rows,edges

class Patterns(unittest.TestCase):
    def suggest(self,values,internal=None):
        rows,edges=strip(values,internal)
        return p.suggest_pattern(rows,edges,{'Body','OtherBody'},{'Dynamic'},list(range(4,len(rows))))
    def test_uniform_small_follow_and_scale_invariance(self):
        values=[1]+[.08]*7
        r=self.suggest(values);self.assertEqual(r['mode'],'UNIFORM')
        rows,edges=strip(values)
        rows=[{n:w*(i+1) for n,w in row.items()} for i,row in enumerate(rows)]
        self.assertEqual(p.suggest_pattern(rows,edges,{'Body'},{'Dynamic'},list(range(4,len(rows))))['mode'],'UNIFORM')
    def test_edge_gradient(self):
        self.assertEqual(self.suggest([1,.85,.7,.55,.4,.25,.1,.02])['mode'],'EDGE_GRADIENT')
        self.assertEqual(self.suggest([1,.85,.55,.2,.01]+[0]*25)['mode'],'EDGE_GRADIENT')
    def test_oscillating_with_same_range_rejected(self):
        self.assertEqual(self.suggest([1,.85,.1,.7,.02,.55,.25,.4])['mode'],'REVIEW')
    def test_total_constant_internal_distribution_changes(self):
        r=self.suggest([1]+[.2]*7,lambda y,x,b:{'Body':b*(y%2),'OtherBody':b*(1-y%2),'Dynamic':1-b})
        self.assertEqual(r['mode'],'REVIEW')
    def test_mixed_stable_pedestal(self):
        r=self.suggest([1,.85,.7,.55,.4,.25,.15,.08],lambda y,x,b:{'Body':.06,'OtherBody':b-.06,'Dynamic':1-b})
        self.assertEqual(r['mode'],'REVIEW');self.assertIn('combined',r['components'][0]['reason'])
    def test_disconnected_uniform_and_gradient(self):
        rows,e=strip([1,.85,.7,.55,.4,.25,.1,.02]);n=len(rows)
        other,f=strip([1]+[.08]*7,offset=n)
        r=p.suggest_pattern(rows+other,e+f,{'Body'},{'Dynamic'},list(range(4,n))+list(range(n+4,n+len(other))))
        self.assertEqual(r['mode'],'REVIEW')
    def test_unknown_small_and_zero_body(self):
        rows,e=strip([1]+[.08]*7);rows[5]['Unclassified']=.1
        self.assertEqual(p.suggest_pattern(rows,e,{'Body'},{'Dynamic'},list(range(4,len(rows))))['mode'],'REVIEW')
        self.assertEqual(p.suggest_pattern(rows,e,{'Body'},{'Dynamic'},[4,5])['mode'],'REVIEW')
        self.assertEqual(self.suggest([1]+[0]*7)['mode'],'REVIEW')
    def test_missing_attachment_and_step_rejected(self):
        self.assertEqual(self.suggest([.8,.7,.6,.5,.4,.3,.1,.02])['mode'],'REVIEW')
        self.assertEqual(self.suggest([1,.85,.85,.85,.02,.02,.02,.02])['mode'],'REVIEW')

if __name__=='__main__':unittest.main()
