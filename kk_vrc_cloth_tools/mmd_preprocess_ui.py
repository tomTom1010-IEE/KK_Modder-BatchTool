"""Dedicated model preprocess sidebar. Does not add to KK/VRC Tools panels."""
import json
from .ui_messages import format_message as _fmt
import bpy
from . import mmd_preprocess as engine, mmd_preprocess_rules as rules


def source_changed(p, context):
    # Deletion decisions belong to one asset, not merely to matching bone names.
    for field in ('pins','chains','excluded','confirmed_removals','job','stage'):
        setattr(p,field,'')
    for key in MAPPING_KEYS:setattr(p,key,'')
    p.reviewed=False;p.candidate=None;p.result=None;p.plan_rows.clear()
    p.status='Source garment changed; old rules cleared. Rescan.'


class KKVRC_MMDPlanRow(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty()
    kept: bpy.props.BoolProperty()
    reason: bpy.props.StringProperty()


class KKVRC_MMDSettings(bpy.types.PropertyGroup):
    source: bpy.props.PointerProperty(name='Source garment',type=bpy.types.Object,poll=lambda self,o:o.type=='MESH',update=source_changed)
    directory: bpy.props.StringProperty(name='Backup/output directory',subtype='DIR_PATH',default='//MMD-Preprocess')
    auto_tpose: bpy.props.BoolProperty(name='Auto T pose (source armature local X)',default=True)
    preserve_tips: bpy.props.BoolProperty(name='Preserve immediate tip candidates of weighted bones',default=True)
    pins: bpy.props.StringProperty(name='Additional protected bones',description='Exact bone names, separated by commas; or add selected bones')
    chains: bpy.props.StringProperty(name='Roots of chains to preserve',description='Preserves entire branches; explicitly exclude branches belonging to other garments')
    excluded: bpy.props.StringProperty(name='Confirmed branch roots to remove',description='Confirmed unused branches; body protection, explicit pins, positive weights, and dependencies take precedence; conflicts stop execution')
    confirmed_removals: bpy.props.StringProperty(name='Confirmed bones to remove',description='Enter reviewed exact names; applies to these nodes only, not descendants. Cannot override body protection or required dependencies')
    upper_L: bpy.props.StringProperty(name='Left upper arm')
    lower_L: bpy.props.StringProperty(name='Left forearm')
    hand_L: bpy.props.StringProperty(name='Left wrist')
    upper_R: bpy.props.StringProperty(name='Right upper arm')
    lower_R: bpy.props.StringProperty(name='Right forearm')
    hand_R: bpy.props.StringProperty(name='Right wrist')
    job: bpy.props.StringProperty(default='')
    status: bpy.props.StringProperty(default='Select one garment; preserve the original and process a separate copy.')
    stage: bpy.props.StringProperty(default='')
    reviewed: bpy.props.BoolProperty(name='T pose reviewed; apply as rest pose and clean up',default=False)
    plan_rows: bpy.props.CollectionProperty(type=KKVRC_MMDPlanRow)
    active_row: bpy.props.IntProperty(default=0)
    candidate: bpy.props.PointerProperty(type=bpy.types.Object)
    result: bpy.props.PointerProperty(type=bpy.types.Object)


MAPPING_KEYS = [k+'_'+s for s in ('L','R') for k in ('upper','lower','hand')]


def config(p):
    return {'auto_tpose':p.auto_tpose,'preserve_tips':p.preserve_tips,
            'pins':rules.names(p.pins),'chains':rules.names(p.chains),'excluded':rules.names(p.excluded),
            'confirmed_removals':rules.names(p.confirmed_removals),
            'mapping':{k:getattr(p,k) for k in MAPPING_KEYS}}


def report_text(p):
    text=bpy.data.texts.get('MMD_Preprocess_Report.json') or bpy.data.texts.new('MMD_Preprocess_Report.json')
    text.clear();text.write(p.job or '{}')
    return text


def focus(context,obj):
    """Isolate preview locally; do not hide other assets in the scene."""
    engine.activate(obj)
    rig=obj.modifiers[0].object
    area=context.area
    if not area or area.type!='VIEW_3D':return
    region=next((r for r in area.regions if r.type=='WINDOW'),None)
    if not region:return
    space=area.spaces.active
    with context.temp_override(region=region):
        if space.local_view:
            for item in context.view_layer.objects:
                item.local_view_set(space,item in (obj,rig))
        else:
            rig.hide_set(False);rig.select_set(True)
            bpy.ops.view3d.localview(frame_selected=True)
            rig.select_set(False)
        bpy.ops.view3d.view_selected(use_all_regions=False)


class KKVRC_UL_mmd_plan(bpy.types.UIList):
    def draw_item(self,context,layout,data,item,icon,active_data,active_propname,index):
        row=layout.row(align=True)
        row.label(text=item.name,icon='LOCKED' if item.kept else 'TRASH')
        row.label(text=item.reason)


class KKVRC_OT_mmd_preprocess(bpy.types.Operator):
    bl_idname='kkvrc.mmd_preprocess'
    bl_label='MMD Garment Preprocessing'
    bl_description='Scan, T-pose an independent copy, clean up with dependency protection, and validate'
    bl_options={'REGISTER','UNDO'}
    action: bpy.props.EnumProperty(items=[(v,label,'') for v,label in [
        ('SELECT_SOURCE','Use active mesh'),('SCAN','Scan cleanup preview'),('PREPARE','Create pose candidate'),
        ('FINALIZE','Apply T pose and clean up'),('SAVE','Save result copy'),('SHOW','Show current result'),('POSE','Adjust candidate pose'),('REPORT','View report'),
        ('PIN','Protect selected bones'),('CHAIN','Preserve chains rooted at selected bones'),('EXCLUDE','Confirm selected branch roots for removal'),
        ('CONFIRM_REMOVE','Confirm selected bones for removal')]])

    def execute(self,context):
        p=context.scene.kkvrc_mmd_preprocess
        try:
            if self.action=='SELECT_SOURCE':
                if not context.object or context.object.type!='MESH': raise ValueError('Select the source garment mesh first')
                if p.source != context.object:
                    for field in ('pins','chains','excluded','confirmed_removals'):setattr(p,field,'')
                p.source=context.object;p.job='';p.stage='';p.reviewed=False
                p.candidate=None;p.result=None;p.plan_rows.clear()
                for k in MAPPING_KEYS:setattr(p,k,'')
                p.status='Source garment set; scan next.'
            elif self.action in {'PIN','CHAIN','EXCLUDE','CONFIRM_REMOVE'}:
                rig=p.source.modifiers[0].object if p.source and p.source.modifiers and p.source.modifiers[0].type=='ARMATURE' else None
                if context.object!=rig or context.mode!='POSE': raise ValueError('Select source rig bones in Pose Mode, then add them')
                selected=[b.name for b in context.selected_pose_bones or []]
                if not selected: raise ValueError('No bones selected')
                field={'PIN':'pins','CHAIN':'chains','EXCLUDE':'excluded','CONFIRM_REMOVE':'confirmed_removals'}[self.action]
                setattr(p,field,', '.join(sorted(set(rules.names(getattr(p,field)))|set(selected))))
                p.stage='';p.reviewed=False;p.status='Rules changed; leave Pose Mode and rescan.'
            elif self.action=='SCAN':
                if not p.source: raise ValueError('Set the source garment first')
                rig=engine.rig_of(p.source); found=rules.arm_mapping(engine.bones(rig))
                for k,v in found.items():
                    if not getattr(p,k):setattr(p,k,v)
                job=engine.scan(p.source,config(p))
                p.plan_rows.clear()
                for n in job['plan']['remove']:
                    row=p.plan_rows.add();row.name=n;row.kept=False;row.reason='Confirmed removable with no required dependencies'
                for n,reasons in job['plan']['keep'].items():
                    row=p.plan_rows.add();row.name=n;row.kept=True;row.reason='；'.join(reasons)
                p.job=json.dumps(job,ensure_ascii=False);p.stage='SCANNED';p.reviewed=False
                p.status=_fmt('{v0} bones → preserve {v1}, removal candidates {v2}, awaiting review {v3}', v0=job['bones_before'], v1=len(job['plan']['keep']), v2=len(job['plan']['remove']), v3=len(job['plan']['review_required']))
            elif self.action=='PREPARE':
                if p.stage!='SCANNED':raise ValueError('Scan the current inputs first')
                job=json.loads(p.job)
                if job['config']!=config(p):raise ValueError('Rules or mappings changed; rescan')
                if p.source is None or job['source']!=p.source.name:raise ValueError('Source object changed; rescan')
                job=engine.prepare(p.source,config(p),job['stamp'],p.directory)
                p.candidate=bpy.data.objects[job['candidate']];p.result=None
                p.job=json.dumps(job,ensure_ascii=False);p.stage='POSE_REVIEW';p.reviewed=False
                p.status='Backed up and created an independent candidate; refine its rig in Pose Mode.'
                focus(context,p.candidate)
            elif self.action=='POSE':
                if p.stage!='POSE_REVIEW' or not p.candidate:raise ValueError('Create a pose candidate first')
                focus(context,p.candidate)
                rig=p.candidate.modifiers[0].object
                engine.activate(rig);rig.show_in_front=True
                bpy.ops.object.mode_set(mode='POSE')
                p.status='Adjust the candidate rig pose; return to Object Mode and confirm when finished.'
            elif self.action=='FINALIZE':
                if p.stage!='POSE_REVIEW' or not p.reviewed:raise ValueError('Inspect and approve the pose candidate first')
                if context.mode!='OBJECT':raise ValueError('Leave Pose/Edit Mode first')
                job=json.loads(p.job)
                if job['config']!=config(p) or not p.source or job['source']!=p.source.name:
                    raise ValueError('Rules or source object changed; rescan')
                job=engine.finalize(job);p.result=bpy.data.objects[job['result']]
                p.job=json.dumps(job,ensure_ascii=False);p.stage='EDIT_READY';p.reviewed=False
                p.status=_fmt('Ready for editing: {v0} bones; preserve {v1} constraints.', v0=job['bones_after'], v1=job['constraints_remaining'])
                focus(context,p.result)
                p.result.modifiers[0].object.hide_set(True)
                engine.save_result(job)
            elif self.action=='SAVE':
                path=engine.save_result(json.loads(p.job));p.status='Saved result copy: '+path
            elif self.action=='SHOW':
                obj=p.result or p.candidate
                if not obj:raise ValueError('No candidate or result yet')
                focus(context,obj)
            elif self.action=='REPORT':
                text=report_text(p)
                if context.area:context.area.type='TEXT_EDITOR';context.area.spaces.active.text=text
            if self.action!='REPORT':report_text(p)
            self.report({'INFO'},p.status)
            return {'FINISHED'}
        except Exception as e:
            p.status=str(e);self.report({'ERROR'},str(e));return {'CANCELLED'}


class KKVRC_PT_mmd_preprocess(bpy.types.Panel):
    bl_label='MMD Garment Preprocessing'
    bl_idname='KKVRC_PT_mmd_preprocess'
    bl_space_type='VIEW_3D';bl_region_type='UI';bl_category='model preprocess'
    def draw(self,context):
        p=context.scene.kkvrc_mmd_preprocess;l=self.layout
        l.prop(p,'source');l.operator('kkvrc.mmd_preprocess',text='Use active mesh').action='SELECT_SOURCE'
        l.prop(p,'directory');l.prop(p,'auto_tpose')
        l.operator('kkvrc.mmd_preprocess',text='1. Scan cleanup preview',icon='VIEWZOOM').action='SCAN'
        row=l.row();row.enabled=p.stage=='SCANNED'
        row.operator('kkvrc.mmd_preprocess',text='2. Back up and create pose candidate',icon='DUPLICATE').action='PREPARE'
        if p.stage=='POSE_REVIEW':
            l.operator('kkvrc.mmd_preprocess',text='Adjust candidate armature pose').action='POSE'
            l.prop(p,'reviewed')
        row=l.row();row.enabled=p.stage=='POSE_REVIEW' and p.reviewed
        row.operator('kkvrc.mmd_preprocess',text='3. Apply T pose, clean up, and validate',icon='CHECKMARK').action='FINALIZE'
        if p.candidate or p.result:l.operator('kkvrc.mmd_preprocess',text='Show candidate/result').action='SHOW'
        l.label(text=p.status)
        if p.stage=='EDIT_READY':
            job=json.loads(p.job)
            l.label(text='Constraint sampling adaptation is still required before optimization' if not job['optimizer_ready'] else 'Standard LBS rig checks passed',icon='INFO')
            l.operator('kkvrc.mmd_preprocess',text='Save result copy again').action='SAVE'
        l.label(text='Preserves originals; this version does not process shape keys or SDEF.')


class KKVRC_PT_mmd_rules(bpy.types.Panel):
    bl_label='Preservation Rules and Cleanup Preview'
    bl_parent_id='KKVRC_PT_mmd_preprocess'
    bl_space_type='VIEW_3D';bl_region_type='UI';bl_category='model preprocess'
    bl_options={'DEFAULT_CLOSED'}
    def draw(self,context):
        p=context.scene.kkvrc_mmd_preprocess;l=self.layout
        l.label(text='Always preserve standard body bones, including zero-weight bones',icon='LOCKED')
        l.prop(p,'preserve_tips')
        l.label(text='Keep bones with unknown purpose until reviewed.')
        for field,action in [('pins','PIN'),('chains','CHAIN'),('excluded','EXCLUDE'),('confirmed_removals','CONFIRM_REMOVE')]:
            l.prop(p,field);l.operator('kkvrc.mmd_preprocess',text='Add selected source bones to the field above').action=action
        l.label(text='Complete chains may include other garments; check ownership.')
        l.template_list('KKVRC_UL_mmd_plan','',p,'plan_rows',p,'active_row',rows=6)
        l.operator('kkvrc.mmd_preprocess',text='View full report in the Text Editor').action='REPORT'


class KKVRC_PT_mmd_mapping(bpy.types.Panel):
    bl_label='T-Pose Bone Mapping'
    bl_parent_id='KKVRC_PT_mmd_preprocess'
    bl_space_type='VIEW_3D';bl_region_type='UI';bl_category='model preprocess'
    bl_options={'DEFAULT_CLOSED'}
    def draw(self,context):
        p=context.scene.kkvrc_mmd_preprocess;l=self.layout
        rig=None
        if p.source:
            rig=next((m.object for m in p.source.modifiers if m.type=='ARMATURE' and m.object),None)
        for k in MAPPING_KEYS:
            if rig:l.prop_search(p,k,rig.data,'bones')
            else:l.prop(p,k)
        l.label(text='Fill in unrecognized mappings, or disable automatic posing.')


CLASSES=(KKVRC_MMDPlanRow,KKVRC_MMDSettings,KKVRC_UL_mmd_plan,KKVRC_OT_mmd_preprocess,
         KKVRC_PT_mmd_preprocess,KKVRC_PT_mmd_rules,KKVRC_PT_mmd_mapping)
