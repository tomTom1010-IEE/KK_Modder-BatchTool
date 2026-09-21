import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('runtime_test', ROOT / 'kk_vrc_cloth_tools/solver_environment.py')
r = importlib.util.module_from_spec(spec); spec.loader.exec_module(r)


class RuntimeTests(unittest.TestCase):
    def test_requirements_match_distribution(self):
        lines = (ROOT / 'requirements-optimizer.txt').read_text().splitlines()
        self.assertEqual(tuple(x for x in lines if x and not x.startswith('#')), r.REQUIREMENTS)

    def test_environment_isolation(self):
        with patch.dict(os.environ, {'PYTHONPATH':'bad', 'PYTHONHOME':'bad', 'VIRTUAL_ENV':'bad'}):
            env = r.clean_env()
            self.assertNotIn('PYTHONPATH', env)
            self.assertNotIn('PYTHONHOME', env)
            self.assertNotIn('VIRTUAL_ENV', env)
            self.assertEqual(env['PYTHONNOUSERSITE'], '1')

    def test_failed_install_preserves_active_environment_and_log(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); marker=root/'active.json'; marker.write_text('{"old": true}')
            worker=r.Installer(root)
            with patch.object(worker,'bootstrap',side_effect=ValueError('network unavailable')):
                with self.assertRaisesRegex(ValueError,'network'): worker.install()
            self.assertEqual(json.loads(marker.read_text()),{'old':True})
            self.assertIn('network unavailable',(root/'install.log').read_text())

    def test_cancel_does_not_promote(self):
        with tempfile.TemporaryDirectory() as d:
            worker=r.Installer(d); worker.cancel()
            with self.assertRaisesRegex(ValueError,'canceled'):worker.install()
            self.assertFalse((Path(d)/'active.json').exists())

    def test_marker_rejects_external_interpreter(self):
        import sys
        with tempfile.TemporaryDirectory() as d:
            (Path(d)/'active.json').write_text(json.dumps({'python':sys.executable}))
            self.assertIsNone(r.managed_python(d))

    def test_detect_skips_broken_candidate(self):
        with patch.object(r,'candidates',return_value=['broken','working']), patch.object(r,'managed_python',return_value=None):
            with patch.object(r,'probe',side_effect=[ValueError('missing library'),{'osqp':'1.0'}]):
                exe,env,info=r.detect()
            self.assertEqual(exe,'working')

    def test_lock_excludes_parallel_install(self):
        with tempfile.TemporaryDirectory() as d:
            with r.install_lock(Path(d)):
                with self.assertRaises((ValueError,OSError)):
                    with r.install_lock(Path(d)): pass


if __name__ == '__main__': unittest.main()
