"""Beginner entry point; the existing workflow remains the only write path."""
import json
import uuid
from pathlib import Path
import bpy
from . import workflow as w
from .optimizer_profiles import CONSERVATIVE_ID, MACRO, TERMINAL


def preset_signature(p):
    return w.core.digest([p.beginner_motion,p.beginner_fingers,p.beginner_terminal,w.dump_settings(p)['motions'],
                          [(b.name,b.enabled,b.weight_target) for b in p.bones if b.finger!='NONE']])


def apply_preset(p):
    w.inputs(p)
    if not p.output:
        if not bpy.data.filepath:raise ValueError('For unsaved files, choose an output directory, then reapply the preset')
        p.output=str(Path(bpy.data.filepath).parent/'KKVRC-Weight-Results')
    root=w.folder(p)
    backup=root/('before-conservative-'+uuid.uuid4().hex[:10]+'.json')
    w.save(backup,w.dump_settings(p))
    if not p.bones and not p.targets:w.scan(p)
    elif not p.bones or not p.targets:raise ValueError('Bone configuration is incomplete; rescan in the detailed workflow')
    # Applying a named preset intentionally resets numerical/motion choices,
    # while preserving reviewed roles, regions, mappings and local masks.
    p.initial_mode='NATIVE';p.confidence=1.;p.contacts=p.collision_policy=='STRICT';p.rings=2;p.small_angle=8
    for x in p.bones:
        if x.role=='BODY' and x.semantic=='NONE':x.semantic=w.vr.VRC_MOTION_SEMANTICS.get(x.name,'NONE')
    # Original finger design is retained by default, sampled fingers stay
    # excluded. Disabling fingers routes their budget to a known same-side hand.
    for x in p.bones:
        if x.role!='BODY' or x.finger=='NONE':continue
        side=x.finger.rsplit('_',1)[-1]
        if p.beginner_fingers:
            x.enabled=True
            if w.finger_name(x.weight_target)!=x.finger:
                mapped=w.weights_body.VRC_TO_KK_BODY_GROUPS.get(x.name)
                if mapped and mapped in {t.name for t in p.targets}:x.weight_target=mapped
        else:
            hand=next((b for b in p.bones if b.role=='BODY' and b.semantic=='HAND_'+side and b.finger=='NONE'),None)
            if hand is None:raise ValueError(x.name+': no confirmed same-side hand mapping; cannot disable fingers automatically')
            x.enabled=False;x.weight_target=hand.weight_target
    w.generate_regions(p);w.analyze_regions(p)
    report=p.status
    slots={x.semantic for x in p.bones if x.role=='BODY'}
    family=p.beginner_motion
    if family=='AUTO':
        arms=any(s.startswith(('UPPER_ARM_','LOWER_ARM_','HAND_')) for s in slots)
        legs=any(s.startswith(('UPPER_LEG_','LOWER_LEG_','FOOT_')) for s in slots)
        family='FULL' if arms and legs else 'LOWER' if legs else 'UPPER'
    p.motions.clear();p.motion_index=0
    p.motion_preset=family;w.generate_motions(p);motion_report=p.status
    if p.beginner_terminal:
        p.motion_preset='WRIST';w.generate_motions(p);motion_report+=' '+p.status
    p.motion_preset=family;p.fingerprint=''
    p.beginner_profile=CONSERVATIVE_ID
    p.beginner_settings=preset_signature(p)
    p.beginner_summary=report+' '+motion_report
    p.status='Conservative preset applied and old configuration backed up; review region modes and bone roles.'
    w.save(root/('conservative-settings-'+uuid.uuid4().hex[:10]+'.json'),
           {'profile':CONSERVATIVE_ID,'macro':MACRO,'terminal':TERMINAL,'settings':w.dump_settings(p),'backup':str(backup)})


def check_ready(p):
    if p.beginner_profile!=CONSERVATIVE_ID:raise ValueError('Apply the conservative preset and complete required checks first')
    if p.beginner_settings!=preset_signature(p):raise ValueError('Preset options, poses, or finger settings changed; reapply the preset or use the detailed workflow')
    w.inputs(p);w.config(p)
    if p.initial_mode!='NATIVE' or p.contacts!=(p.collision_policy=='STRICT') or abs(p.confidence-1)>1e-6 or p.rings!=2 or abs(p.small_angle-8)>1e-6:
        raise ValueError('Conservative settings changed; reapply the preset or use the detailed workflow for custom settings')
    contract=w.optimization.source_pose_contract(p.source) if p.source_sampling=='EVALUATED' else None
    w.optimization._rig(p.source,contract)
    for obj in (p.target,p.body):w.optimization._rig(obj)
    w.native_rest_check(p)
    for local in [False,True] if p.beginner_terminal else [False]:
        actions=w.poses(p,local)
        sr,tr=w.inputs(p)
        for pose in actions:
            for control in pose['controls']:
                for arm,key in [(sr,'source'),(tr,'target')]:
                    if any(n not in arm.data.bones for n,f in control[key]):raise ValueError('Preset pose mapping is incomplete; check source and target motion bones')
    if p.beginner_terminal:
        if not p.local_vertices or p.local_topology!=w.wf.topology(p.source):raise ValueError('Terminal refinement requires a valid local vertex region; disable it to run main optimization first')
        ids=json.loads(p.local_vertices)
        if not ids or any(type(i) is not int or not 0<=i<len(p.source.data.vertices) for i in ids):raise ValueError('Invalid terminal vertex selection')
        if not any(t.local and t.finger=='NONE' for t in p.targets):raise ValueError('Terminal refinement requires selected candidates with actual body weights')
    exe,env=w.python_command(p)
    check=w.subprocess.run([exe,'-c','import numpy,scipy,osqp'],env=env,capture_output=True,text=True,timeout=20,
                          creationflags=getattr(w.subprocess,'CREATE_NO_WINDOW',0))
    if check.returncode:raise ValueError('Solver dependencies unavailable; configure Python and NumPy/SciPy/OSQP in runtime settings: '+check.stderr[-300:])


def start(p):
    check_ready(p)
    w.prepare(p);w.write_initial(p)
    w.save(Path(p.run)/'beginner-run.json',{'profile':CONSERVATIVE_ID,'macro':MACRO,'terminal':TERMINAL,
                                         'include_terminal':p.beginner_terminal,'settings':w.dump_settings(p)})


def finish_stage(p,stage):
    """Same independent validation/write gates as the detailed workflow."""
    w.validate_stage(p,stage)
    path,*_=w.stage_data(p,stage)
    report=json.loads((path/'validation.json').read_text(encoding='utf-8'))
    if not report['accepted'] and not (p.collision_policy=='REVIEW' and report.get('non_contact_ok')):raise ValueError('Non-collision checks or strict policy failed; report retained, optimization copy not written')
    w.write_stage(p,stage)


class KKVRC_OT_beginner(bpy.types.Operator):
    bl_idname='kkvrc.beginner_weights'
    bl_label='Beginner conservative weight workflow'
    bl_description='Apply existing conservative settings; unrecognized or unreviewed regions stop execution; write results to copies only'
    action:bpy.props.StringProperty(default='APPLY')

    def execute(self,context):
        p=context.scene.kkvrc_weight_workflow
        try:
            if context.scene.as_pointer() in w._jobs:raise ValueError('A solve is running')
            if self.action=='APPLY':apply_preset(p)
            else:
                start(p)
                result=bpy.ops.kkvrc.weight_workflow_solve('INVOKE_DEFAULT',stage='macro',automatic=True,include_terminal=p.beginner_terminal)
                if result=={'CANCELLED'}:raise ValueError(p.status)
            return {'FINISHED'}
        except Exception as exc:
            p.status='Automatic workflow stopped: '+str(exc);self.report({'ERROR'},p.status);return {'CANCELLED'}


class KKVRC_PT_beginner_weights(bpy.types.Panel):
    bl_label='Garment Weights · Beginner Preset'
    bl_idname='KKVRC_PT_beginner_weights'
    bl_space_type='VIEW_3D';bl_region_type='UI';bl_category='KK/VRC Tools'
    bl_order=-1

    def draw(self,context):
        p=context.scene.kkvrc_weight_workflow;layout=self.layout
        for key in ('source','target','body'):layout.prop(p,key)
        layout.prop(p,'source_profile');layout.prop(p,'source_sampling');layout.prop(p,'reference_mode')
        layout.prop(p,'collision_policy');layout.prop(p,'exclude_bnip')
        layout.prop(p,'output');layout.prop(p,'beginner_motion');layout.prop(p,'beginner_fingers');layout.prop(p,'beginner_terminal')
        layout.label(text='Nearest face interpolation · six-class conservation · collision checks · separate copies')
        layout.operator('kkvrc.beginner_weights',text='1. Apply conservative preset and scan').action='APPLY'
        layout.label(text='2. Review region modes and dynamic bone roles')
        layout.template_list('KKVRC_UL_wf','beginner_regions',p,'regions',p,'region_index',rows=4)
        if p.regions:
            r=p.regions[min(p.region_index,len(p.regions)-1)];layout.prop(r,'mode')
            row=layout.row(align=True);w.button(row,'Highlight region','PREVIEW_REGION');w.button(row,'Confirm region mode','CONFIRM_REGION')
            w.button(layout,'Confirm this chain as retained dynamic bones','MARK_CHAIN')
        layout.label(text='Unrecognized: agent analysis or manual handling required')
        layout.label(text='After highlighting, press Tab to return to Object Mode before solving')
        layout.label(text='Preview and restore poses in the detailed workflow below')
        layout.operator('kkvrc.beginner_weights',text='3. Solve → validate → create copies').action='RUN'
        layout.label(text='Press Esc to cancel; results are saved as a separate blend file')
        row=layout.row(align=True);w.button(row,'Select collision vertices','REVIEW_CONTACTS');w.button(row,'Revert to previous version','ROLLBACK_RESULT')
        if p.beginner_terminal:layout.label(text='Terminal refinement uses only the specified local selection and candidates')
        layout.label(text=p.status[:110])


CLASSES=(KKVRC_OT_beginner,KKVRC_PT_beginner_weights)
