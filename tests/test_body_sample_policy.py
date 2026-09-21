import importlib.util,unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('policy_core',Path(__file__).resolve().parents[1]/'kk_vrc_cloth_tools/weight_features.py')
core=importlib.util.module_from_spec(spec);spec.loader.exec_module(core)

class BodySamplePolicyTests(unittest.TestCase):
    def test_redirect_preserves_torso_total_and_other_weights(self):
        rows=[{'bnipL':.2,'bustL':.3,'bustR':.1,'arm':.4}]
        r=core.redirect_body_samples(rows,{'bnipL':{'bustL':1}},
            {'bnipL':'TORSO','bustL':'TORSO','bustR':'TORSO','arm':'ARM_L'}, {'bustL','bustR','arm'})
        self.assertEqual(r,[{'bustL':.5,'bustR':.1,'arm':.4}])
        self.assertEqual(rows[0]['bnipL'],.2)
    def test_invalid_maps_stop(self):
        regions={'bnip':'TORSO','bust':'TORSO','arm':'ARM_L'}
        for mapping in [{'arm':1},{'bust':.5},{'missing':1},{'bnip':1}]:
            with self.assertRaises(ValueError):core.redirect_body_samples([],{'bnip':mapping},regions,{'bust','arm'})

if __name__=='__main__':unittest.main()
