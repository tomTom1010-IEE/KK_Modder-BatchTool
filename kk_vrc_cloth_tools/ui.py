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
    hybrid_weight_mode: bpy.props.EnumProperty(
        name="Mode",
        items=(
            ("TRANSFER", "Transfer Body Weights", "Transfer KK body weights on VRC-body-controlled vertices"),
            ("MAP", "Map VRC Body Weights", "Map VRC body groups to KK body groups and optionally mix S/D deformation bones"),
            ("BLEND", "Distance Blend Transfer/Map", "Blend transfer and mapping near dynamic-body transition areas"),
            ("SKIRT_SAFE", "Skirt Safe Hybrid", "Transfer only near-body areas and softly blend into dynamic/mapped skirt areas"),
        ),
        default="BLEND",
    )
    hybrid_dynamic_threshold: bpy.props.FloatProperty(
        name="Dynamic protect threshold",
        default=0.05,
        min=0.0,
        max=1.0,
    )
    hybrid_remove_replaced_vrc_groups: bpy.props.BoolProperty(
        name="Remove replaced VRC body groups after apply",
        default=True,
    )
    hybrid_normalize_affected_only: bpy.props.BoolProperty(
        name="Normalize affected vertices only",
        default=True,
    )
    hybrid_include_sd_bones: bpy.props.BoolProperty(
        name="Include S deformation bones",
        default=True,
    )
    hybrid_sd_influence: bpy.props.FloatProperty(
        name="S/D influence",
        default=0.35,
        min=0.0,
        max=1.0,
    )
    hybrid_blend_width_rings: bpy.props.IntProperty(
        name="Blend width rings",
        default=3,
        min=1,
        max=16,
    )
    hybrid_blend_smooth_iterations: bpy.props.IntProperty(
        name="Blend smooth iterations",
        default=2,
        min=0,
        max=10,
    )
    hybrid_max_distance: bpy.props.FloatProperty(
        name="Max transfer distance",
        default=0.0,
        min=0.0,
        description="0 disables distance filtering",
    )
    hybrid_skirt_safe_body_distance: bpy.props.FloatProperty(
        name="Skirt body transfer distance",
        default=0.06,
        min=0.0,
        description="Only vertices within this distance from the source body become direct transfer region; 0 disables distance filtering",
    )
    hybrid_skirt_safe_transition_rings: bpy.props.IntProperty(
        name="Skirt transition rings",
        default=3,
        min=1,
        max=16,
    )
    hybrid_skirt_safe_ignore_leg_weights: bpy.props.BoolProperty(
        name="Skirt mode: ignore leg/foot body weights",
        default=True,
    )
    hybrid_body_falloff_full_distance: bpy.props.FloatProperty(
        name="Body transfer full distance",
        default=0.0,
        min=0.0,
        description="Transfer is fully used at or below this distance from the source body",
    )
    hybrid_body_falloff_zero_distance: bpy.props.FloatProperty(
        name="Body transfer zero distance",
        default=0.0,
        min=0.0,
        description="Transfer fades to mapping at this distance from the source body; 0 disables body-distance falloff",
    )
    manual_skirt_dynamic_threshold: bpy.props.FloatProperty(
        name="Dynamic protect threshold",
        default=0.05,
        min=0.0,
        max=1.0,
        description="After manual Data Transfer, vertices above this clothing-dynamic weight keep dynamic influence and body weights fill only the remaining capacity",
    )
    manual_skirt_ignore_leg_weights: bpy.props.BoolProperty(
        name="Remove leg/foot/S-D lower body weights",
        default=True,
        description="Remove thigh, leg, foot, toe, knee, and lower-body S/D weights from skirt-like clothes while preserving siri weights",
    )
    manual_skirt_normalize_affected_only: bpy.props.BoolProperty(
        name="Normalize affected vertices only",
        default=True,
    )
    manual_skirt_smooth_iterations: bpy.props.IntProperty(
        name="Smooth iterations",
        default=1,
        min=0,
        max=10,
    )
    cleanup_empty_group_threshold: bpy.props.FloatProperty(
        name="Empty group weight threshold",
        default=0.0,
        min=0.0,
        max=1.0,
        description="Remove vertex groups whose maximum vertex weight is at or below this value",
    )
    cleanup_mirror_weights_remove_empty: bpy.props.BoolProperty(
        name="Remove empty groups after swap",
        default=True,
        description="After swapping L/R weights, remove paired vertex groups that no longer contain weights",
    )
    cleanup_bnip_merge_to_bust: bpy.props.BoolProperty(
        name="Merge nipple weights to bust/spine",
        default=True,
        description="Move removed cf_*_bnip weights to nearby bust or spine groups instead of simply deleting them",
    )
    cleanup_bnip_normalize_affected: bpy.props.BoolProperty(
        name="Normalize affected vertices only",
        default=True,
    )
    cleanup_delete_mode: bpy.props.EnumProperty(
        name="Bone delete mode",
        items=(
            ("SUBTREE_TO_PARENT", "Merge subtree to parent", "Delete the whole selected subtree and merge all subtree weights to the outside parent"),
            ("NODE_TO_PARENT", "Merge node, graft children", "Delete only the selected node, merge its weights to parent, and graft child chains to parent"),
        ),
        default="SUBTREE_TO_PARENT",
    )
    cleanup_simplify_keep_every: bpy.props.IntProperty(
        name="Keep every N bones",
        default=2,
        min=1,
        max=32,
    )
    cleanup_reconnect_simplified_chain: bpy.props.BoolProperty(
        name="Reconnect simplified chain tails",
        default=True,
        description="After simplifying, move parent bone tails to preserved child heads so the chain displays continuously",
    )
    cleanup_connect_single_child_bones: bpy.props.BoolProperty(
        name="Connect single-child bones",
        default=True,
        description="For non-branching simplified chains, mark child bones as connected to their parents",
    )
    cleanup_parallel_merge_target: bpy.props.EnumProperty(
        name="Merge to chain",
        items=(
            ("ACTIVE", "Active selected root", "Merge all selected parallel chains into the active selected root chain"),
            ("FIRST", "First selected root", "Merge all selected parallel chains into the first selected root chain"),
            ("LAST", "Last selected root", "Merge all selected parallel chains into the last selected root chain"),
        ),
        default="ACTIVE",
    )
    cleanup_parallel_merge_match: bpy.props.EnumProperty(
        name="Chain match mode",
        items=(
            ("TOP", "From top/root", "Match bones by depth from the selected roots"),
            ("BOTTOM", "From bottom/tip", "Match bones by reverse depth from the leaf tips"),
            ("RATIO", "Whole-chain ratio", "Match bones by normalized position along each chain"),
        ),
        default="TOP",
    )
    cleanup_parallel_merge_tolerance: bpy.props.IntProperty(
        name="Length tolerance",
        default=1,
        min=0,
        max=16,
        description="Maximum allowed segment-count difference between selected parallel chains",
    )
    cleanup_hair_tip_patterns: bpy.props.StringProperty(
        name="Hair tip patterns",
        default="CYCRHair*_tip,*Hair*_tip,*_tip",
        description="Comma-separated leaf bone name patterns",
    )
    cleanup_merge_weighted_hair_tips: bpy.props.BoolProperty(
        name="Merge weighted hair tips",
        default=False,
        description="If enabled, weighted hair tip placeholders are merged to parent before deletion",
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

    ui_show_status: bpy.props.BoolProperty(name="Selection Status", default=True)
    ui_show_bone_tools: bpy.props.BoolProperty(name="Bone Setup", default=True)
    ui_show_body_weights: bpy.props.BoolProperty(name="Body Weight Mapping", default=True)
    ui_show_breast_weights: bpy.props.BoolProperty(name="Breast Weight Tools", default=False)
    ui_show_transfer_postprocess: bpy.props.BoolProperty(name="Manual Transfer Postprocess", default=True)
    ui_show_glove_tools: bpy.props.BoolProperty(name="Glove / Pose Tools", default=False)
    ui_show_utilities: bpy.props.BoolProperty(name="Utilities", default=False)

    last_status: bpy.props.StringProperty(name="Last Status", default="Ready")


def action_buttons(layout, operator_id, preview="PREVIEW", apply="APPLY", report="REPORT", report_text="Report"):
    row = layout.row(align=True)
    op = row.operator(operator_id, text="Preview")
    op.action = preview
    op = row.operator(operator_id, text="Apply")
    op.action = apply
    op = row.operator(operator_id, text=report_text)
    op.action = report


def draw_foldout_section(layout, props, prop_name, title, hint=""):
    box = layout.box()
    row = box.row(align=True)
    is_open = getattr(props, prop_name)
    icon = "TRIA_DOWN" if is_open else "TRIA_RIGHT"
    row.prop(props, prop_name, text=title, icon=icon, emboss=False)
    if hint:
        row.label(text=hint)
    return box if is_open else None


def draw_section_title(layout, title):
    layout.separator()
    layout.label(text=title)


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

        box = draw_foldout_section(layout, props, "ui_show_status", "Selection Status")
        if box:
            box.label(text=f"{iface_('Active/KK')}: {kk_name}", translate=False)
            box.label(text=f"{iface_('VRC source')}: {vrc_name}", translate=False)
            box.label(text=f"{iface_('Selected meshes')}: {mesh_count}", translate=False)

        box = draw_foldout_section(layout, props, "ui_show_bone_tools", "Bone Setup", "Step 1")
        if box:
            box.label(text="Step 1 - Graft Clothes Physical Bones To KK")
            box.prop(props, "graft_include_priority_1")
            box.prop(props, "graft_include_priority_2")
            box.prop(props, "graft_selected_meshes_only")
            box.prop(props, "graft_attachment_mode")
            box.prop(props, "graft_delete_vrc_armature")
            action_buttons(box, "kkvrc.graft_clothes_bones", "SCAN", "APPLY", "REPORT", "Report Roots")

            draw_section_title(box, "Delete Selected Bone Chain/Subtree")
            box.prop(props, "cleanup_delete_mode")
            row = box.row(align=True)
            op = row.operator("kkvrc.delete_selected_bone_tree", text="Preview")
            op.action = "PREVIEW"
            op = row.operator("kkvrc.delete_selected_bone_tree", text="Apply")
            op.action = "APPLY"

            draw_section_title(box, "Simplify Selected Physical Bone Chain")
            box.prop(props, "cleanup_simplify_keep_every")
            box.prop(props, "cleanup_reconnect_simplified_chain")
            if props.cleanup_reconnect_simplified_chain:
                box.prop(props, "cleanup_connect_single_child_bones")
            row = box.row(align=True)
            op = row.operator("kkvrc.simplify_selected_bone_chain", text="Preview")
            op.action = "PREVIEW"
            op = row.operator("kkvrc.simplify_selected_bone_chain", text="Apply")
            op.action = "APPLY"

            draw_section_title(box, "Merge Selected Parallel Bone Chains")
            box.prop(props, "cleanup_parallel_merge_target")
            box.prop(props, "cleanup_parallel_merge_match")
            box.prop(props, "cleanup_parallel_merge_tolerance")
            row = box.row(align=True)
            op = row.operator("kkvrc.merge_selected_parallel_bone_chains", text="Preview")
            op.action = "PREVIEW"
            op = row.operator("kkvrc.merge_selected_parallel_bone_chains", text="Apply")
            op.action = "APPLY"

            draw_section_title(box, "Clean VRC Hair Tip Placeholders")
            box.prop(props, "cleanup_hair_tip_patterns")
            box.prop(props, "cleanup_merge_weighted_hair_tips")
            row = box.row(align=True)
            op = row.operator("kkvrc.cleanup_hair_tip_placeholders", text="Preview")
            op.action = "PREVIEW"
            op = row.operator("kkvrc.cleanup_hair_tip_placeholders", text="Apply")
            op.action = "APPLY"

        box = draw_foldout_section(layout, props, "ui_show_body_weights", "Body Weight Mapping", "Step 2 / 3 / 5")
        if box:
            box.label(text="Step 2 - Remap Low-Risk Body Groups")
            box.prop(props, "body_normalize_after_apply")
            box.prop(props, "body_limit_total")
            action_buttons(box, "kkvrc.remap_body_weights", "PREVIEW", "APPLY", "REPORT", "Report Orphans")

            draw_section_title(box, "Step 3 - Mix Torso / Hip / Butt Weights")
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

            draw_section_title(box, "Step 5 - Transfer KK Body Weights To Fitted Clothes")
            box.prop(props, "transfer_source_body_mesh")
            box.prop(props, "transfer_physical_threshold")
            box.prop(props, "transfer_replace_body_weights")
            box.prop(props, "transfer_treat_vrc_humanoid_as_body")
            box.prop(props, "transfer_remove_replaced_non_kk_groups")
            box.prop(props, "transfer_normalize_affected_only")
            box.prop(props, "transfer_max_distance")
            action_buttons(box, "kkvrc.transfer_body_weights_to_fitted_clothes")

        box = draw_foldout_section(layout, props, "ui_show_breast_weights", "Breast Weight Tools", "Step 4A / 4B")
        if box:
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

            draw_section_title(box, "Step 4B - Breast Local Mix")
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

        box = draw_foldout_section(layout, props, "ui_show_transfer_postprocess", "Manual Transfer Postprocess", "Step 5B")
        if box:
            box.label(text="Step 5B - Postprocess Manual Weight Transfer")
            box.label(text="Run Blender Data Transfer first, then use these cleanup tools.")
            box.separator()
            box.label(text="Skirt / Dynamic Bone Protection")
            box.label(text="Protect clothing dynamic bones and remove lower-body leg/foot weights from skirt areas.")
            box.prop(props, "transfer_source_body_mesh")
            box.prop(props, "manual_skirt_dynamic_threshold")
            box.prop(props, "manual_skirt_ignore_leg_weights")
            box.prop(props, "manual_skirt_normalize_affected_only")
            box.prop(props, "manual_skirt_smooth_iterations")
            action_buttons(box, "kkvrc.postprocess_manual_skirt_weights", "PREVIEW", "APPLY", "REPORT", "Report Postprocess")
            box.separator()
            box.label(text="Upper-Clothes Nipple Detail Cleanup")
            box.label(text="Remove cf_*_bnip weights that can create chest bumps after transfer.")
            box.prop(props, "cleanup_bnip_merge_to_bust")
            box.prop(props, "cleanup_bnip_normalize_affected")
            action_buttons(box, "kkvrc.remove_bnip_weights", "PREVIEW", "APPLY", "REPORT", "Report Nipple")

        box = draw_foldout_section(layout, props, "ui_show_glove_tools", "Glove / Pose Tools", "Step 6")
        if box:
            box.label(text="Step 6 - Align VRC Glove Hand Pose To KK")
            box.prop(props, "glove_align_side")
            box.prop(props, "glove_align_transform_mode")
            box.prop(props, "glove_align_influence")
            action_buttons(box, "kkvrc.align_vrc_glove_pose_to_kk", "PREVIEW", "APPLY", "RESET", "Reset Hand Pose")

        box = draw_foldout_section(layout, props, "ui_show_utilities", "Utilities")
        if box:
            box.label(text="Swap L/R Vertex Group Weights")
            box.prop(props, "cleanup_mirror_weights_remove_empty")
            action_buttons(box, "kkvrc.swap_lr_vertex_group_weights", "PREVIEW", "APPLY", "REPORT", "Report Swap")
            box.separator()
            box.label(text="Remove Empty Vertex Groups")
            box.prop(props, "cleanup_empty_group_threshold")
            action_buttons(box, "kkvrc.remove_empty_vertex_groups", "PREVIEW", "APPLY", "REPORT", "Report Empty")
            box.separator()
            box.label(text="Clean Body Weights From Dynamic Areas")
            box.prop(props, "transfer_dynamic_cleanup_threshold")
            box.prop(props, "transfer_dynamic_cleanup_normalize")
            action_buttons(box, "kkvrc.cleanup_dynamic_body_weights", "PREVIEW", "APPLY", "REPORT", "Report Cleanup")
            box.separator()
            box.operator("kkvrc.export_armature_topology", text="Export Armature Topology JSON")

        box = layout.box()
        box.label(text="Last Status")
        box.label(text=props.last_status)
