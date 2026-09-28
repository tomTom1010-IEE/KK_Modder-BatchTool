"""Run with factory-startup Blender: exercise real restricted add-on registration."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bpy
import addon_utils

legacy = bpy.context.scene
legacy['kkvrc_weight_workflow'] = {'run': 'legacy-config'}
new_scene = bpy.data.scenes.new('Fresh influence settings')
errors = []

def enable():
    module = addon_utils.enable('kk_vrc_cloth_tools', default_set=True,
                               handle_error=lambda exc: errors.append(str(exc)))
    assert module is not None and not errors, errors
    return module

for cycle in range(2):
    module = enable()
    migration = module.influence_blender.migrate_existing
    assert bpy.app.timers.is_registered(migration)
    # Simulate the callback after RestrictBlend has been released. Background
    # scripts do not otherwise yield to Blender's normal UI timer loop.
    bpy.app.timers.unregister(migration)
    migration()
    assert legacy.kkvrc_weight_workflow.total_influences == 'UNLIMITED'
    assert legacy['kkvrc_weight_workflow']['run'] == 'legacy-config'
    if cycle == 0:
        legacy.kkvrc_weight_workflow.confidence = 0.73
    else:
        assert abs(legacy.kkvrc_weight_workflow.confidence - 0.73) < 1e-6
    assert new_scene.kkvrc_weight_workflow.total_influences == 'FOUR'
    assert legacy.kkvrc_bone_name_mode == 'AUTO'
    if cycle == 0:
        # Disabling before a queued migration executes must cancel the timer.
        bpy.app.timers.register(migration, first_interval=0.0)
    addon_utils.disable('kk_vrc_cloth_tools', default_set=True,
                        handle_error=lambda exc: errors.append(str(exc)))
    assert not errors, errors
    assert not bpy.app.timers.is_registered(migration)
    assert migration not in bpy.app.handlers.load_post
    assert not hasattr(bpy.types.Scene, 'kkvrc_weight_workflow')

print('ADDON_REGISTRATION_OK: restricted enable, deferred migration, disable and re-enable')
