"""Shared, non-blocking solver environment UI for beginner and detailed workflows."""
import queue
import threading
import bpy
from . import solver_environment as runtime

_events = queue.Queue()
_thread = None
_installer = None
_resolved = None
_status = 'Solver environment has not been checked.'
_checked = False


def busy():
    return _thread is not None and _thread.is_alive()


def resolve(p):
    if getattr(p, 'manual_python', False):
        import shutil
        from pathlib import Path
        value = bpy.path.abspath(p.python) if '/' in p.python or '\\' in p.python else shutil.which(p.python)
        if not value or not Path(value).is_file():
            raise ValueError('External Python not found; configure it in runtime settings')
        env = runtime.clean_env()
        if p.dependencies: env['PYTHONPATH'] = bpy.path.abspath(p.dependencies)
        return value, env
    global _resolved
    if _resolved is None:
        _resolved = runtime.detect(bpy.path.abspath(p.python), bpy.path.abspath(p.dependencies) if p.dependencies else '')
    return _resolved[0], _resolved[1].copy()


def poll():
    global _status, _resolved
    while not _events.empty():
        kind, value = _events.get()
        if kind == 'ready':
            _resolved = value
            _status = 'Solver environment ready.'
        else:
            _status = value
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas: area.tag_redraw()
    return .5 if busy() or not _events.empty() else None


def start(action, p):
    global _thread, _installer, _status, _checked, _resolved
    if busy(): return
    configured = bpy.path.abspath(p.python)
    dependencies = bpy.path.abspath(p.dependencies) if p.dependencies else ''
    _checked = True
    if action == 'DETECT': _resolved = None
    events = _events
    _status = 'Checking solver environments...' if action == 'DETECT' else 'Preparing solver environment installation...'
    _installer = runtime.Installer(notify=lambda message: events.put(('status', message))) if action == 'INSTALL' else None
    installer = _installer
    def work():
        try:
            value = installer.install() if installer else runtime.detect(configured, dependencies)
            events.put(('ready', value))
        except Exception as exc:
            events.put(('error', str(exc)))
    _thread = threading.Thread(target=work, daemon=True, name='KKVRC-SolverSetup')
    _thread.start()
    if not bpy.app.timers.is_registered(poll): bpy.app.timers.register(poll, first_interval=.1)


def automatic_check():
    if bpy.context.scene and not _checked:
        start('DETECT', bpy.context.scene.kkvrc_weight_workflow)
    return None


def shutdown():
    if _installer: _installer.cancel()
    for callback in (poll, automatic_check):
        if bpy.app.timers.is_registered(callback): bpy.app.timers.unregister(callback)


class KKVRC_OT_solver_environment(bpy.types.Operator):
    bl_idname = 'kkvrc.solver_environment'
    bl_label = 'Solver Environment'
    action: bpy.props.EnumProperty(items=[('DETECT','Detect solver environment',''),
        ('INSTALL','Install solver environment',''),('CANCEL','Cancel installation',''),('LOG','Open installation log','')])

    def execute(self, context):
        global _status
        from . import workflow
        try:
            if self.action == 'LOG':
                path = runtime.runtime_root() / 'install.log'
                if not path.exists(): raise ValueError('No installation log yet.')
                bpy.ops.wm.path_open(filepath=str(path))
            elif self.action == 'CANCEL':
                if _installer:
                    _installer.cancel()
                    _status = 'Cancellation requested; waiting for the current operation to stop.'
            else:
                if workflow._jobs: raise ValueError('Wait for the current solver task to finish before changing environments.')
                start(self.action, context.scene.kkvrc_weight_workflow)
            return {'FINISHED'}
        except Exception as exc:
            self.report({'ERROR'}, str(exc)); return {'CANCELLED'}


def draw(layout, p):
    box = layout.box()
    box.label(text='Solver Environment')
    if p.manual_python:
        box.label(text='Manual Python override is enabled; validate it below.')
    box.label(text=_status)
    if _resolved: box.label(text=_resolved[0], translate=False)
    row = box.row(align=True); row.enabled = not busy()
    row.operator('kkvrc.solver_environment', text='Detect automatically').action = 'DETECT'
    row.operator('kkvrc.solver_environment', text='Install isolated environment').action = 'INSTALL'
    box.label(text='Installation downloads Python if needed and solver packages; internet required.')
    if busy() and _installer:
        box.operator('kkvrc.solver_environment', text='Cancel installation').action = 'CANCEL'
    if runtime.runtime_root().joinpath('install.log').exists():
        box.operator('kkvrc.solver_environment', text='Open installation log').action = 'LOG'
    box.prop(p, 'manual_python')
    if p.manual_python:
        box.prop(p, 'python'); box.prop(p, 'dependencies')
        op = box.operator('kkvrc.weight_workflow', text='Check solver dependencies'); op.action = 'DEPENDENCIES'


class KKVRC_PT_solver_config(bpy.types.Panel):
    bl_label = 'Solver Environment'
    bl_idname = 'KKVRC_PT_solver_config'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'config'

    def draw(self, context):
        draw(self.layout, context.scene.kkvrc_weight_workflow)


CLASSES = (KKVRC_OT_solver_environment, KKVRC_PT_solver_config)
