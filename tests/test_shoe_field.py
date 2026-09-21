import importlib.util
import pathlib
import unittest
import numpy as np

spec=importlib.util.spec_from_file_location('shoe_field',pathlib.Path(__file__).parents[1]/'kk_vrc_cloth_tools/shoe_field.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


class ShoeFieldTests(unittest.TestCase):
    def test_island_repair_does_not_cross_disconnected_surfaces(self):
        p=np.array([[1.,0],[0.,1],[1.,0],[0.,1],[0.,1]])
        q,r=m.smooth(p,np.array([[0,1],[1,2],[3,4]]),np.array([10.,.02,10.,10.,10.]))
        self.assertTrue(r['converged']);self.assertGreater(q[1,0],.9)
        np.testing.assert_allclose(q[3:],p[3:]);np.testing.assert_allclose(q.sum(1),1)

    def test_constrained_quadratic_and_frozen_budgets(self):
        p=np.array([[.9,.1],[.5,.5],[.2,.8]])
        q,r=m.optimize(p,np.tile(np.eye(2),(3,1,1)),np.tile([.1,.9],(3,1)),[],prior=.01,smoothness=0)
        self.assertTrue(r['converged']);self.assertTrue(np.all(q>=0))
        budget=np.array([1.,.2,0.]);dynamic=1-budget
        np.testing.assert_allclose((q*budget[:,None]).sum(1)+dynamic,1)
        self.assertLess(np.linalg.norm(q-[.1,.9]),np.linalg.norm(p-[.1,.9]))

    def test_projection_extremes(self):
        q=m.simplex(np.array([[-2.,3.,4.],[0.,0.,0.]]))
        np.testing.assert_allclose(q.sum(1),1);self.assertTrue(np.all(q>=0))

    def test_unobserved_bones_cannot_enter_via_optimizer(self):
        p=np.array([[.5,.5,0.]])
        q,r=m.optimize(p,np.eye(3)[None,:,:],np.array([[0.,0.,10.]]),[],allowed=np.array([[True,True,False]]))
        self.assertTrue(r['converged']);self.assertEqual(q[0,2],0)
        np.testing.assert_allclose(q.sum(1),1)

if __name__=='__main__':unittest.main()
