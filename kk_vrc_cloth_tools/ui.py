import bpy
from bpy.app.translations import pgettext_iface as iface_

from . import common


class KKVRC_ClothToolsProperties(bpy.types.PropertyGroup):
    graft_include_priority_1: bpy.props.BoolProperty(name="Priority 1 torso/skirt roots", default=True)
    graft_include_priority_2: bpy.props.BoolProperty(name="Priority 2 breast/upper-clothes roots", default=False)
    graft_selected_meshes_only: bpy.props.BoolProperty(
        name="Only graft bones used by selected meshes",
        default=False,
        description="Only copy clothing bone chains weighted by selected meshes; useful for gloves/socks cleanup",
    )
    graft_delete_vrc_armature: bpy.props.BoolProperty(name="Delete VRC source Armature after graft", default=True)
    graft_attachment_mode: bpy.props.EnumProperty(
        name="Parent-derived attach mode",
        items=(
            ("PELVIS", "Pelvis / Low Skirt", "Attach Hips-parented roots to cf_j_hips"),
            ("WAIST", "Waist Skirt", "Attach Hips-parented roots to lower KK waist"),
            ("HIGH_WAIST", "High Waist / Dress", "Attach Hips-parented roots to upper KK waist"),
        ),
        default="WAIST",
    )

    body_normalize_after_apply: bpy.props.BoolProperty(name="Normalize after apply", default=False)
    body_limit_total: bpy.props.IntProperty(name="Limit total weights", default=4, min=0, max=32)

    torso_mode: bpy.props.EnumProperty(
        name="Mode",
        items=(
            ("BALANCED", "Balanced Torso", "Distribute across waist/spine/siri chains"),
            ("CONSERVATIVE", "Conservative Torso", "Use fewer KK target bones"),
        ),
        default="BALANCED",
    )
    torso_remove_source_groups: bpy.props.BoolProperty(name="Remove source torso/hip groups after apply", default=True)
    torso_normalize_affected_only: bpy.props.BoolProperty(name="Normalize affected vertices only", default=True)
    torso_smooth_after_apply: bpy.props.BoolProperty(name="Smooth after apply", default=True)
    torso_smooth_iterations: bpy.props.IntProperty(name="Smooth iterations", default=2, min=0, max=10)
    torso_smooth_strength: bpy.props.FloatProperty(name="Smooth strength", default=0.35, min=0.0, max=1.0)
    torso_smooth_expand_rings: bpy.props.IntProperty(name="Smooth expand rings", default=1, min=0, max=5)

    breast_simple_mode: bpy.props.EnumProperty(
        name="Mode",
        items=(
            ("SIMPLE", "Simple J Chain", "Direct cf_j_bust01/02/03 targets"),
            ("DISTRIBUTED", "Distributed J Chain", "Distribute across adjacent KK bust bones"),
        ),
        default="SIMPLE",
    )
    breast_simple_remove_source_groups: bpy.props.BoolProperty(name="Remove source breast groups after apply", default=True)
    breast_simple_normalize_affected_only: bpy.props.BoolProperty(name="Normalize affected vertices only", default=True)
    breast_simple_smooth_after_apply: bpy.props.BoolProperty(name="Smooth after apply", default=True)
    breast_simple_smooth_iterations: bpy.props.IntProperty(name="Smooth iterations", default=2, min=0, max=10)
    breast_simple_smooth_strength: bpy.props.FloatProperty(name="Smooth strength", default=0.35, min=0.0, max=1.0)
    breast_simple_smooth_expand_rings: bpy.props.IntProperty(name="Smooth expand rings", default=1, min=0, max=5)

    breast_local_mode: bpy.props.EnumProperty(
        name="Breast Target Mapping",
        items=(
            ("DIRECT", "Direct J Chain", "Direct cf_j_bust01/02/03 targets"),
            ("DISTRIBUTED", "Distributed J Chain", "Distribute across adjacent KK bust bones"),
        ),
        default="DISTRIBUTED",
    )
    breast_local_include_root_group: bpy.props.BoolProperty(name="Include Breast_root.L/R", default=False)
    breast_local_breast_factor: bpy.props.FloatProperty(name="Breast influence", default=0.7, min=0.0, max=1.0)
    breast_local_body_factor: bpy.props.FloatProperty(name="Body influence", default=0.3, min=0.0, max=1.0)
    breast_local_remove_source_groups: bpy.props.BoolProperty(name="Remove source breast groups after apply", default=True)
    breast_local_normalize_affected_only: bpy.props.BoolProperty(name="Normalize affected vertices only", default=True)
    breast_local_smooth_after_apply: bpy.props.BoolProperty(name="Smooth after apply", default=True)
    breast_local_smooth_iterations: bpy.props.IntProperty(name="Smooth iterations", default=2, min=0, max=10)
    breast_local_smooth_strength: bpy.props.FloatProperty(name="Smooth strength", default=0.35, min=0.0, max=1.0)
    breast_local_smooth_expand_rings: bpy.props.IntProperty(name="Smooth expand rings", default=1, min=0, max=5)

    transfer_source_body_mesh: bpy.props.PointerProperty(name="Source body mesh", type=bpy.types.Object)
    transfer_physical_threshold: bpy.props.FloatProperty(
        name="Physical weight threshold",
        default=0.05,
        min=0.0,
        max=1.0,
        description="Only vertices with non-KK physical weight at or below this value receive transferred body weights",
    )
    transfer_replace_body_weights: bpy.props.BoolProperty(name="Replace existing KK body weights", default=True)
    transfer_treat_vrc_humanoid_as_body: bpy.props.BoolProperty(
        name="Treat VRC humanoid groups as body weights",
        default=True,
        description="Do not count VRC humanoid/finger groups as protected physical weights during transfer",
    )
    transfer_remove_replaced_non_kk_groups: bpy.props.BoolProperty(
        name="Remove replaced non-KK groups after apply",
        default=True,
        description="Remove replaceable VRC humanoid/finger groups from affected vertices after applying transfer",
    )
    transfer_normalize_affected_only: bpy.props.BoolProperty(name="Normalize affected vertices only", default=True)
    transfer_max_distance: bpy.props.FloatProperty(
        name="Max transfer distance",
        default=0.0,
        min=0.0,
        description="0 disables distance filtering",
    )
    transfer_dynamic_cleanup_threshold: bpy.props.FloatProperty(
        name="Dynamic cleanup threshold",
        default=0.05,
        min=0.0,
        max=1.0,
        description="Remove KK body weights from vertices whose clothing dynamic weight is above this value",
    )
    transfer_dynamic_cleanup_normalize: bpy.props.BoolProperty(
        name="Normalize after dynamic cleanup",
        default=True,
    )

    glove_align_side: bpy.props.EnumProperty(
        name="Side",
        items=(
            ("BOTH", "Both Hands", "Align both left and right VRC hands"),
            ("LEFT", "Left Hand", "Align only the left VRC hand"),
            ("RIGHT", "Right Hand", "Align only the right VRC hand"),
        ),
        default="BOTH",
    )
    glove_align_transform_mode: bpy.props.EnumProperty(
        name="Pose transform",
        items=(
            ("ROTATION", "Rotate only", "Match KK joint-chain directions while preserving VRC joint positions"),
            ("ROTATION_LOCATION", "Rotate + move", "Match KK joint-chain directions and joint positions"),
        ),
        default="ROTATION",
    )
    glove_align_influence: bpy.props.FloatProperty(
        name="Influence",
        default=1.0,
        min=0.0,
        max=1.0,
        description="Blend between current VRC hand pose and KK-aligned pose",
    )

    last_status: bpy.props.StringProperty(name="Last Status", default="Ready")


def action_buttons(layout, operator_id, preview="PREVIEW", apply="APPLY", report="REPORT", report_text="Report"):
    row = layout.row(align=True)
    op = row.operator(operator_id, text="Preview")
    op.action = preview
    op = row.operator(operator_id, text="Apply")
    op.action = apply
    op = row.operator(operator_id, text=report_text)
    op.action = report


class KKVRC_PT_cloth_tools(bpy.types.Panel):
    bl_label = "KK/VRC Cloth Tools"
    bl_idname = "KKVRC_PT_cloth_tools"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "KK/VRC Tools"

    def draw(self, context):
        layout = self.layout
        props = context.scene.kkvrc_cloth_tools
        kk_name, vrc_name, mesh_count = common.get_selection_status(context)

        box = layout.box()
        box.label(text="Selection Status")
        box.label(text=f"{iface_('Active/KK')}: {kk_name}", translate=False)
        box.label(text=f"{iface_('VRC source')}: {vrc_name}", translate=False)
        box.label(text=f"{iface_('Selected meshes')}: {mesh_count}", translate=False)

        box = layout.box()
        box.label(text="Step 1 - Graft Clothes Physical Bones To KK")
        box.prop(props, "graft_include_priority_1")
        box.prop(props, "graft_include_priority_2")
        box.prop(props, "graft_selected_meshes_only")
        box.prop(props, "graft_attachment_mode")
        box.prop(props, "graft_delete_vrc_armature")
        action_buttons(box, "kkvrc.graft_clothes_bones", "SCAN", "APPLY", "REPORT", "Report Roots")

        box = layout.box()
        box.label(text="Step 2 - Remap Low-Risk Body Groups")
        box.prop(props, "body_normalize_after_apply")
        box.prop(props, "body_limit_total")
        action_buttons(box, "kkvrc.remap_body_weights", "PREVIEW", "APPLY", "REPORT", "Report Orphans")

        box = layout.box()
        box.label(text="Step 3 - Mix Torso / Hip / Butt Weights")
        box.prop(props, "torso_mode")
        box.prop(props, "torso_remove_source_groups")
        box.prop(props, "torso_normalize_affected_only")
        box.prop(props, "torso_smooth_after_apply")
        if props.torso_smooth_after_apply:
            row = box.row(align=True)
            row.prop(props, "torso_smooth_iterations")
            row.prop(props, "torso_smooth_strength")
            box.prop(props, "torso_smooth_expand_rings")
        action_buttons(box, "kkvrc.mix_torso_hip_weights")

        box = layout.box()
        box.label(text="Step 4A - Breast Simple Remap")
        box.prop(props, "breast_simple_mode")
        box.prop(props, "breast_simple_remove_source_groups")
        box.prop(props, "breast_simple_normalize_affected_only")
        box.prop(props, "breast_simple_smooth_after_apply")
        if props.breast_simple_smooth_after_apply:
            row = box.row(align=True)
            row.prop(props, "breast_simple_smooth_iterations")
            row.prop(props, "breast_simple_smooth_strength")
            box.prop(props, "breast_simple_smooth_expand_rings")
        action_buttons(box, "kkvrc.remap_breast_simple")

        box = layout.box()
        box.label(text="Step 4B - Breast Local Mix")
        box.prop(props, "breast_local_mode")
        box.prop(props, "breast_local_include_root_group")
        box.prop(props, "breast_local_breast_factor")
        box.prop(props, "breast_local_body_factor")
        box.prop(props, "breast_local_remove_source_groups")
        box.prop(props, "breast_local_normalize_affected_only")
        box.prop(props, "breast_local_smooth_after_apply")
        if props.breast_local_smooth_after_apply:
            row = box.row(align=True)
            row.prop(props, "breast_local_smooth_iterations")
            row.prop(props, "breast_local_smooth_strength")
            box.prop(props, "breast_local_smooth_expand_rings")
        action_buttons(box, "kkvrc.mix_breast_local")

        box = layout.box()
        box.label(text="Step 5 - Transfer KK Body Weights To Fitted Clothes")
        box.prop(props, "transfer_source_body_mesh")
        box.prop(props, "transfer_physical_threshold")
        box.prop(props, "transfer_replace_body_weights")
        box.prop(props, "transfer_treat_vrc_humanoid_as_body")
        box.prop(props, "transfer_remove_replaced_non_kk_groups")
        box.prop(props, "transfer_normalize_affected_only")
        box.prop(props, "transfer_max_distance")
        action_buttons(box, "kkvrc.transfer_body_weights_to_fitted_clothes")
        box.separator()
        box.prop(props, "transfer_dynamic_cleanup_threshold")
        box.prop(props, "transfer_dynamic_cleanup_normalize")
        action_buttons(box, "kkvrc.cleanup_dynamic_body_weights", "PREVIEW", "APPLY", "REPORT", "Report Cleanup")

        box = layout.box()
        box.label(text="Step 6 - Align VRC Glove Hand Pose To KK")
        box.prop(props, "glove_align_side")
        box.prop(props, "glove_align_transform_mode")
        box.prop(props, "glove_align_influence")
        action_buttons(box, "kkvrc.align_vrc_glove_pose_to_kk", "PREVIEW", "APPLY", "RESET", "Reset Hand Pose")

        box = layout.box()
        box.label(text="Utilities")
        box.operator("kkvrc.export_armature_topology", text="Export Armature Topology JSON")

        box = layout.box()
        box.label(text="Last Status")
        box.label(text=props.last_status)
