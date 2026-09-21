"""Accessory mode is separate from unconditional clothing-body protection."""
import json
from .ui_messages import format_message as _fmt
import bpy
from . import accessory_preprocess as engine, mmd_preprocess_rules as rules


def changed(p,context):
    p.owned_roots='';p.external='';p.job='';p.status='Source object changed; assign ownership and scan again.'


class KKVRC_AccessorySettings(bpy.types.PropertyGroup):
    source:bpy.props.PointerProperty(name='Source accessory',type=bpy.types.Object,poll=lambda s,o:o.type=='MESH',update=changed)
    owned_roots:bpy.props.StringProperty(name='Owned chain roots',description='Complete chains confirmed as belonging to this accessory; unknown bones are not automatically dynamic')
    external:bpy.props.StringProperty(name='External attachment bones',description='Body or other-asset attachment bones; comma-separated exact names')
    mmd_body:bpy.props.BoolProperty(name='Recognize standard MMD body attachment bones',default=True)
    directory:bpy.props.StringProperty(name='Backup/output directory',subtype='DIR_PATH',default='//Accessory-Preprocess')
    job:bpy.props.StringProperty()
    status:bpy.props.StringProperty(default='Create a separate mesh and armature for each accessory.')


def config(p):return {'owned_roots':rules.names(p.owned_roots),'external':rules.names(p.external),'mmd_body':p.mmd_body}


class KKVRC_OT_accessory_preprocess(bpy.types.Operator):
    bl_idname='kkvrc.accessory_preprocess';bl_label='Accessory rig preprocessing';bl_options={'REGISTER','UNDO'}
    action:bpy.props.EnumProperty(items=[(n,t,'') for n,t in [('SOURCE','Use active mesh'),('OWN','Add selected bones as owned roots'),('EXTERNAL','Add selected bones as external attachments'),('SCAN','Scan plan'),('APPLY','Back up and create independent accessory'),('REPORT','View report')]])
    def execute(self,context):
        p=context.scene.kkvrc_accessory
        try:
            if self.action=='SOURCE':
                if not context.object or context.object.type!='MESH':raise ValueError('Select a source mesh')
                p.source=context.object
            elif self.action in {'OWN','EXTERNAL'}:
                if not p.source:raise ValueError('Set the source accessory first')
                rig=next((m.object for m in p.source.modifiers if m.type=='ARMATURE'),None)
                if context.object!=rig or context.mode!='POSE':raise ValueError('Select source rig bones in Pose Mode')
                names=[b.name for b in context.selected_pose_bones or []]
                if not names:raise ValueError('No bones selected')
                field='owned_roots' if self.action=='OWN' else 'external'
                setattr(p,field,', '.join(sorted(set(rules.names(getattr(p,field)))|set(names))))
                p.job='';p.status='Ownership updated; leave Pose Mode and scan.'
            elif self.action=='SCAN':
                job=engine.scan(p.source,config(p));p.job=json.dumps(job,ensure_ascii=False)
                p.status=_fmt('Owned/dependent {v0} bones; fixed attachments {v1}; separate armature for each accessory.', v0=len(job['plan']['owned']), v1=len(job['mapping']))
            elif self.action=='APPLY':
                job=json.loads(p.job or '{}')
                if job.get('status')!='SCANNED' or not p.source or job['source']!=p.source.name or job['config']!=config(p):raise ValueError('Rescan current inputs and settings')
                job=engine.apply(p.source,config(p),job['stamp'],p.directory)
                p.job=json.dumps(job,ensure_ascii=False);p.status='Independent accessory created; attachment points still need target binding. Original preserved.'
            elif self.action=='REPORT':
                text=bpy.data.texts.get('Accessory_Preprocess_Report.json') or bpy.data.texts.new('Accessory_Preprocess_Report.json')
                text.clear();text.write(p.job or '{}')
                if context.area:context.area.type='TEXT_EDITOR';context.area.spaces.active.text=text
            self.report({'INFO'},p.status);return {'FINISHED'}
        except Exception as e:p.status=str(e);self.report({'ERROR'},str(e));return {'CANCELLED'}


class KKVRC_PT_accessory_preprocess(bpy.types.Panel):
    bl_label='Accessory Independent Rig Cleanup';bl_idname='KKVRC_PT_accessory_preprocess'
    bl_space_type='VIEW_3D';bl_region_type='UI';bl_category='model preprocess'
    def draw(self,context):
        p=context.scene.kkvrc_accessory;l=self.layout
        l.prop(p,'source');l.operator('kkvrc.accessory_preprocess',text='Use active mesh').action='SOURCE'
        l.prop(p,'mmd_body')
        for field,action in [('owned_roots','OWN'),('external','EXTERNAL')]:
            l.prop(p,field);l.operator('kkvrc.accessory_preprocess',text='Add selected source bones to the field above').action=action
        l.prop(p,'directory')
        l.label(text='Roots receive external shares; owned dynamic weights remain unchanged.')
        l.label(text='Keep multiple attachment points separate; do not force a single root.')
        l.operator('kkvrc.accessory_preprocess',text='1. Scan plan').action='SCAN'
        l.operator('kkvrc.accessory_preprocess',text='2. Back up and create independent accessory').action='APPLY'
        l.operator('kkvrc.accessory_preprocess',text='View report').action='REPORT'
        l.label(text=p.status)


CLASSES=(KKVRC_AccessorySettings,KKVRC_OT_accessory_preprocess,KKVRC_PT_accessory_preprocess)
