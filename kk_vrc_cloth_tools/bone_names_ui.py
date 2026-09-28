"""One scene-wide suffix setting shared by all source and target rig profiles."""
import bpy


def changed(self, context):
    p = getattr(self, 'kkvrc_weight_workflow', None)
    if p:
        p.fingerprint = ''
        p.status = 'Bone suffix compatibility changed; rescan to update automatic suggestions.'
    shoes = getattr(self, 'kkvrc_shoes', None)
    if shoes:
        shoes.scan_stamp = ''


def register_property():
    bpy.types.Scene.kkvrc_bone_name_mode = bpy.props.EnumProperty(
        name='Bone suffix compatibility',
        description='Global source and target name matching; does not rename bones or vertex groups. Rescan after changing',
        items=[('AUTO', 'Automatic (. / _)', 'Accept exact names and either terminal suffix separator'),
               ('DOT', 'Period (.)', 'Accept exact rule names and period suffix aliases'),
               ('UNDERSCORE', 'Underscore (_)', 'Accept exact rule names and underscore suffix aliases')],
        default='AUTO', update=changed)


def draw(layout, scene):
    layout.prop(scene, 'kkvrc_bone_name_mode')


class KKVRC_PT_bone_names(bpy.types.Panel):
    bl_idname = 'KKVRC_PT_bone_names'
    bl_label = 'Bone Name Compatibility'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'config'

    def draw(self, context):
        draw(self.layout, context.scene)
        self.layout.label(text='Shared by VRC, MMD, and target rigs.')
        self.layout.label(text='Rescan after changing this setting.')


CLASSES = (KKVRC_PT_bone_names,)
