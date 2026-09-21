"""Background Blender UI/worker integration using a disposable runtime stub."""
from pathlib import Path
import sys
import time
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bpy
import kk_vrc_cloth_tools as addon
from kk_vrc_cloth_tools import solver_setup as setup, solver_environment as runtime, workflow

addon.register()
p = bpy.context.scene.kkvrc_weight_workflow
before = workflow.dump_settings(p)
value = ('verified-python', {'PYTHONNOUSERSITE':'1'}, {'osqp':'1.0'})
with patch.object(runtime, 'detect', return_value=value):
    assert bpy.ops.kkvrc.solver_environment(action='DETECT') == {'FINISHED'}
    for _ in range(100):
        setup.poll()
        if not setup.busy(): break
        time.sleep(.01)
    setup.poll()
    assert setup.resolve(p) == value[:2]
with patch.object(runtime.Installer, 'install', return_value=value):
    assert bpy.ops.kkvrc.solver_environment(action='INSTALL') == {'FINISHED'}
    for _ in range(100):
        setup.poll()
        if not setup.busy(): break
        time.sleep(.01)
    setup.poll()
    assert setup._status == 'Solver environment ready.'
assert before == workflow.dump_settings(p)
assert not p.manual_python
p.manual_python=True
p.python=bpy.app.binary_path  # Resolve only; never run Blender as Python.
assert setup.resolve(p)[0] == bpy.app.binary_path
addon.unregister()
assert not bpy.app.timers.is_registered(setup.poll)
print('SOLVER_SETUP_UI_TEST_OK')
