"""Support feasibility, objective-aware search, and immutable exception regression."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'kk_vrc_cloth_tools'))
import numpy as np
import influence_policy as ip
import weight_optimizer as opt
import shoe_field

FOUR={'max_influences':4}


def budgets(w,regions):
    return np.stack([w[:,np.array(regions)==r].sum(1) for r in range(6)],axis=1)


class InfluenceTests(unittest.TestCase):
    def test_absent_policy_is_unlimited_and_bitwise_legacy(self):
        w=np.full((2,6),1/6);regions=np.zeros(6,int);fixed=np.zeros_like(w,bool)
        seed,support,report=ip.select(w,regions,budgets(w,regions),fixed,np.ones_like(fixed))
        np.testing.assert_array_equal(seed,w)
        self.assertEqual(report['representation'],'UNLIMITED')
        self.assertFalse(ip.policy()['compress_dynamic'])

    def test_budget_and_finger_slots_are_not_extra_categories(self):
        w=np.array([[.1,.1,.2,.2,.2,.2]])
        r=np.array([1,1,1,0,0,5]);f=np.zeros_like(w,bool);f[:,[0,5]]=True
        out,support,rep=ip.select(w,r,budgets(w,r),f,np.ones_like(f),FOUR)
        self.assertTrue(rep['strict_compatible']);self.assertLessEqual((out>0).sum(),4)
        np.testing.assert_allclose(budgets(out,r),budgets(w,r),atol=1e-12)
        np.testing.assert_array_equal(out[f],w[f])

    def test_fixed_only_finger_needs_no_additional_arm_slot(self):
        w=np.array([[.1,.2,.3,.4]]);r=np.array([1,0,5,5]);f=np.array([[1,0,1,1]],bool)
        out,_,rep=ip.select(w,r,budgets(w,r),f,w>0,FOUR)
        self.assertEqual(rep['exceptions'],[]);np.testing.assert_allclose(out,w)

    def test_unavoidable_dynamic_and_categories_are_preserved(self):
        w=np.array([[.1,.1,.2,.2,.4],[.2,.2,.2,.2,.2]])
        r=np.array([0,1,5,5,5]);f=np.broadcast_to(r==5,w.shape)
        out,_,rep=ip.select(w,r,budgets(w,r),f,w>0,FOUR)
        np.testing.assert_array_equal(out,w)
        self.assertEqual(rep['over_limit_vertices'],[0,1])
        self.assertFalse(rep['strict_compatible'])
        verdict=ip.validate_result(w,out,r,budgets(w,r),f,w>0,FOUR)
        self.assertTrue(verdict['constraints_ok'])
        out[0,0]+=.01;out[0,1]-=.01
        self.assertFalse(ip.validate_result(w,out,r,budgets(w,r),f,w>0,FOUR)['constraints_ok'])

    def test_tiny_category_cannot_be_discarded(self):
        w=np.array([[.2,.2,.2,.4-1e-12,1e-12]])
        r=np.array([0,0,0,0,1]);f=np.zeros_like(w,bool)
        out,_,rep=ip.select(w,r,budgets(w,r),f,w>0,FOUR)
        self.assertEqual(out[0,4],w[0,4]);self.assertTrue(rep['strict_compatible'])

    def test_float32_fixed_roundoff_is_not_a_support_conflict(self):
        exact=np.array([[.1,.1,.2,.2,.2,.2]])
        w=exact.astype(np.float32).astype(float);r=np.array([0,0,0,0,5,5]);f=np.broadcast_to(r==5,w.shape)
        out,_,rep=ip.select(w,r,budgets(exact,r),f,w>0,FOUR)
        self.assertEqual(rep['exceptions'],[]);self.assertTrue(rep['strict_compatible'])
        np.testing.assert_array_equal(out[f],w[f])

    def test_independent_check_rejects_deleting_a_tiny_fixed_influence(self):
        w=np.array([[.25,.25,.25,.25-1e-12,1e-12]])
        r=np.array([0,0,0,0,5]);f=np.broadcast_to(r==5,w.shape)
        out=w.copy();out[0,0]+=out[0,4];out[0,4]=0
        result=ip.validate_result(w,out,r,budgets(w,r),f,w>0,FOUR)
        self.assertFalse(result['fixed_ok']);self.assertFalse(result['constraints_ok'])

    def test_macro_motion_can_retain_a_small_but_important_bone(self):
        rest=np.array([[0.,0.,0.],[1,0,0]])
        w=np.tile([.3,.25,.24,.2,.01],(2,1));r=np.zeros(5,int);f=np.zeros_like(w,bool)
        mats=np.broadcast_to(np.eye(4),(2,5,4,4)).copy();mats[1,4,2,3]=100
        ref=opt.skin(rest,mats,w)
        out,rep=opt.solve_limited(rest,mats,w,ref,r,budgets(w,r),f,np.ones_like(f),[(0,1)],[0,1],
                                 influence_policy=FOUR,prior=.001,smooth=.01)
        self.assertEqual(rep['status'],'solved')
        self.assertTrue(np.all((out>0).sum(1)<=4));self.assertTrue(np.all(out[:,4]>.009))
        np.testing.assert_allclose(out.sum(1),1,atol=1e-10)

    def test_local_bounds_and_exterior_exceptions(self):
        w=np.full((2,6),1/6);r=np.zeros(6,int);f=np.zeros_like(w,bool)
        out,_,rep=ip.select(w,r,budgets(w,r),f,w>0,FOUR,selected=[0],delta_limits=np.array([.01,0]))
        np.testing.assert_array_equal(out,w)
        self.assertEqual(len(rep['exceptions']),2)

    def test_dynamic_compression_opt_in_and_separate_probes(self):
        w=np.array([[.2,.2,.2,.2,.2]]);r=np.array([0,5,5,5,5]);f=np.broadcast_to(r==5,w.shape)
        rest=np.zeros((1,3));mats=np.broadcast_to(np.eye(4),(3,5,4,4)).copy()
        p=dict(FOUR,compress_dynamic=True)
        kept,_,rep=ip.select(w,r,budgets(w,r),f,w>0,p,rest=rest)
        np.testing.assert_array_equal(kept,w)
        out,_,rep=ip.select(w,r,budgets(w,r),f,w>0,p,rest=rest,dynamic_train=mats)
        self.assertTrue(rep['strict_compatible']);self.assertEqual(rep['compressed_vertices'],[0])
        self.assertAlmostEqual(out[0,1:].sum(),.8)
        self.assertFalse(ip.validate_result(w,out,r,budgets(w,r),f,w>0,p,rest=rest)['constraints_ok'])
        self.assertTrue(ip.validate_result(w,out,r,budgets(w,r),f,w>0,p,rest=rest,dynamic_holdout=mats)['constraints_ok'])
        mats[1,1,0,3]=2
        self.assertFalse(ip.validate_result(w,out,r,budgets(w,r),f,w>0,p,rest=rest,dynamic_holdout=mats)['constraints_ok'])
        self.assertFalse(ip.validate_result(w,out,r,budgets(w,r),f,w>0,FOUR,rest=rest,dynamic_holdout=mats)['constraints_ok'])

    def test_dense_correction_anchor_includes_removed_graph_constants(self):
        w=np.array([[.8,.2],[.2,.8]])
        seed=np.array([[1.,0.],[.2,.8]])
        fixed=np.array([[True,True],[False,False]])
        out,_=opt.solve(np.array([[0.,0,0],[1.,0,0]]),np.broadcast_to(np.eye(4),(1,2,4,4)),seed,
            np.array([[[0.,0,0],[1.,0,0]]]),[0,0],np.ones((2,1)),fixed,seed>0,[(0,1)],[1],
            anchor=w,prior=1.,smooth=1.)
        # d0=(+.2,-.2), so d1 should be half of d0 with unit prior.
        np.testing.assert_allclose(out[1],[.3,.7],atol=1e-7)

    def test_shoe_projection_cannot_regrow_support_or_change_exceptions(self):
        p=np.array([[.2,.3,.5],[.3,.2,.5]])
        allowed=np.array([[1,0,1],[1,1,1]],bool);fixed=np.array([False,True])
        a,_=shoe_field.smooth(p,[(0,1)],np.ones(2),allowed=allowed,fixed_rows=fixed)
        b,_=shoe_field.optimize(a,np.tile(np.eye(3),(2,1,1)),p,[(0,1)],allowed=allowed,fixed_rows=fixed)
        self.assertEqual(b[0,1],0);np.testing.assert_array_equal(b[1],p[1])


if __name__=='__main__':unittest.main()
