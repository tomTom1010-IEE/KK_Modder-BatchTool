"""Run with optional optimizer dependencies on PYTHONPATH; no Blender required."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'kk_vrc_cloth_tools'))
import numpy as np
import weight_optimizer as opt
from optimizer_scope import pure_dynamic_vertices, check_body_admission


class OptimizerTests(unittest.TestCase):
    def test_weight_admission_is_not_pose_bone_admission(self):
        good={'target_names':['Skin','Cloth'],'allowed_body_bones':['Skin'],
              'retained_dynamic_bones':['Cloth'],'poses':[{'control':'UnusedJoint'}]}
        check_body_admission(good)
        with self.assertRaises(ValueError):check_body_admission(dict(good,target_names=['UnusedJoint']))
        with self.assertRaises(ValueError):check_body_admission({'target_names':['Skin']})
    def test_transport_rigid_and_anisotropic_sculpt_rest(self):
        s=np.array([[0.,0,0],[1,0,0],[1,1,0],[0,1,0]])
        j0=np.diag([2.,.7,1.])
        t=s@j0.T+[4,7,2]
        edges=np.array([[0,1],[1,2],[2,3],[3,0],[0,2]])
        tri=np.array([[0,1,2],[0,2,3]])
        j,fb=opt.fit_rest_transport(s,t,edges,tri,np.broadcast_to(j0,(4,3,3)))
        frames=np.broadcast_to(np.eye(4),(2,4,4,4)).copy()
        posed=np.stack([s,s+[.1,.2,0]])
        ref=opt.motion_reference(s,t,posed,frames,frames,j)
        np.testing.assert_allclose(ref[0],t,atol=1e-12)
        np.testing.assert_allclose(ref[1]-t,np.tile([.2,.14,0],(4,1)),atol=1e-10)

    def test_local_motion_does_not_fit_world_offsets(self):
        s=np.array([[1.,2,0]]);t=np.array([[4.,5,0]])
        sf=np.broadcast_to(np.eye(4),(2,1,4,4)).copy();tf=sf.copy()
        sf[1,0,:3,3]=[10,0,0];tf[1,0,:3,3]=[30,0,0]
        ref=opt.motion_reference(s,t,np.stack([s,s+[10,0,0]]),sf,tf,np.eye(3)[None])
        np.testing.assert_allclose(ref[1],t+[30,0,0])

    def fixture(self):
        rest=np.array([[0.,0,.1],[1,0,.1]])
        mats=np.broadcast_to(np.eye(4),(3,3,4,4)).copy()
        mats[1,0,0,3]=1;mats[2,1,1,3]=1
        w0=np.array([[.4,.4,.2],[.2,.3,.5]])
        wanted=np.array([[.1,.7,.2],[.4,.1,.5]])
        fixed=np.zeros_like(w0,bool);fixed[:,2]=True
        return rest,mats,w0,wanted,fixed

    def test_recovers_known_weights_and_fixed_dynamic(self):
        rest,mats,w0,wanted,fixed=self.fixture()
        out,report=opt.solve(rest,mats,w0,opt.skin(rest,mats,wanted),[0,0,1],
            np.array([[.8,.2],[.5,.5]]),fixed,np.ones_like(fixed),[],[0,1,1],prior=1e-7,smooth=0)
        np.testing.assert_allclose(out,wanted,atol=2e-6)
        np.testing.assert_array_equal(out[:,2],w0[:,2])
        self.assertLess(report['candidate_rms'],report['baseline_rms'])

    def test_selected_boundary_preserved(self):
        rest,mats,w0,wanted,fixed=self.fixture()
        out,_=opt.solve(rest,mats,w0,opt.skin(rest,mats,wanted),[0,0,1],
            np.array([[.8,.2],[.5,.5]]),fixed,np.ones_like(fixed),[(0,1)],[0,1,1],selected=[0])
        np.testing.assert_array_equal(out[1],w0[1])

    def test_exact_triangle_nearest_and_contact(self):
        sf=opt.TriangleSurface(np.array([[-2.,-2,0],[2,-2,0],[0,2,0]]),[[0,1,2]])
        q,n,d=sf.nearest([[0,0,-.2],[0,0,.3],[3,0,0]])
        np.testing.assert_allclose(d[:2],[-.2,.3]);self.assertGreater(np.linalg.norm(q[2]-[3,0,0]),0)
        rest=np.array([[0.,0,.1]])
        mats=np.broadcast_to(np.eye(4),(2,2,4,4)).copy()
        mats[1,0,2,3]=-.3;mats[1,1,2,3]=.3
        w0=np.array([[.8,.2]])
        out,report=opt.solve(rest,mats,w0,opt.skin(rest,mats,w0),[0,0],np.array([[1.]]),
            np.zeros_like(w0,bool),np.ones_like(w0,bool),[],[0,1],surfaces={1:sf},trust=1.)
        self.assertEqual(report['status'],'solved')
        self.assertGreaterEqual(opt.skin(rest,mats,out)[1,0,2],-1e-7)

    def test_invalid_budget_rejected(self):
        rest,mats,w0,wanted,fixed=self.fixture()
        with self.assertRaises(ValueError):
            opt.solve(rest,mats,w0,opt.skin(rest,mats,wanted),[0,0,1],np.ones((2,2)),fixed,np.ones_like(fixed),[],[1,1,1])

    def test_immutable_contact_is_reported_without_futile_iterations(self):
        rest,mats,w0,wanted,fixed=self.fixture()
        rest[0,2]=-.1;fixed[0]=True
        surface=opt.TriangleSurface(np.array([[-2.,-2,0],[2,-2,0],[0,2,0]]),[[0,1,2]])
        out,report=opt.solve(rest,mats,w0,opt.skin(rest,mats,w0),[0,0,1],
            np.array([[.8,.2],[.5,.5]]),fixed,np.ones_like(fixed),[],[1,1,1],surfaces={0:surface})
        self.assertEqual(report['status'],'fixed_contact_conflict')
        self.assertEqual(len(report['history']),1)
        np.testing.assert_array_equal(out[0],w0[0])
        out,report=opt.solve(rest,mats,w0,opt.skin(rest,mats,w0),[0,0,1],
            np.array([[.8,.2],[.5,.5]]),fixed,np.ones_like(fixed),[],[1,1,1],
            surfaces={0:surface},contact_excluded=np.array([True,False]))
        self.assertEqual(report['status'],'solved')
        np.testing.assert_array_equal(out[0],w0[0])

    def test_scope_keeps_mixed_and_frozen_body_vertices(self):
        budgets=np.array([[0,0,0,0,0,1],[.01,0,0,0,0,.99],[1,0,0,0,0,0]])
        np.testing.assert_array_equal(pure_dynamic_vertices(budgets),[True,False,False])

    def test_local_correction_bounds_and_frozen_exterior(self):
        rest,mats,w0,wanted,fixed=self.fixture()
        out,report=opt.solve(rest,mats,w0,opt.skin(rest,mats,wanted),[0,0,1],
            np.array([[.8,.2],[.5,.5]]),fixed,np.ones_like(fixed),[],[0,1,1],
            selected=[0],delta_limits=np.array([.05,0]),residual_scale=.1,prior=1e-7,smooth=0)
        self.assertEqual(report['status'],'solved')
        self.assertLessEqual(np.max(abs(out[0]-w0[0])),.0500001)
        np.testing.assert_array_equal(out[1],w0[1])

    def test_bucketed_nearest_matches_all_triangles(self):
        rng=np.random.default_rng(196)
        triangles=rng.normal(size=(24,3,3))*np.geomspace(.001,10,24)[:,None,None]
        points=rng.normal(size=(530,3))
        surface=opt.TriangleSurface(triangles.reshape(-1,3),np.arange(72).reshape(-1,3))
        q,_,_=surface.nearest(points)
        distances=[]
        for triangle in triangles:
            one=opt.TriangleSurface(triangle,[[0,1,2]])
            nearest,_,_=one.nearest(points)
            distances.append(np.linalg.norm(nearest-points,axis=1))
        np.testing.assert_allclose(np.linalg.norm(q-points,axis=1),np.min(distances,axis=0),atol=1e-9)

    def test_barycentric_contact_reaches_face_interior(self):
        class Bump:
            def nearest(self,points):
                points=np.asarray(points);q=points.copy()
                q[:,2]=np.where(np.linalg.norm(points[:,:2],axis=1)<.2,.2,0.)
                normals=np.tile([0.,0,1],(len(points),1))
                return q,normals,points[:,2]-q[:,2]
        rest=np.array([[-1.,-1,.1],[1,-1,.1],[0,2,.1]])
        mats=np.broadcast_to(np.eye(4),(2,2,4,4)).copy();mats[1,1,2,3]=1
        initial=np.tile([1.,0],(3,1))
        out,report=opt.solve(rest,mats,initial,opt.skin(rest,mats,initial),[0,0],np.ones((3,1)),
            np.zeros((3,2),bool),np.ones((3,2),bool),[],[0,1],surfaces={1:Bump()},trust=1.,
            contact_samples={1:(np.array([[0,1,2]]),np.array([[1/3]*3]))})
        self.assertEqual(report['status'],'solved')
        self.assertGreaterEqual(opt.skin(rest,mats,out)[1].mean(axis=0)[2],.2-1e-7)


if __name__=='__main__':unittest.main()
