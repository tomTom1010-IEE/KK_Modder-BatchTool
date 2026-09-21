# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 tomTom. See LICENSE and NOTICE.md.

bl_info = {
    "name": "KK/VRC Cloth Tools",
    "author": "tomTomIEE + Codex",
    "version": (0, 2, 24),
    "blender": (4, 3, 0),
    "location": "View3D > Sidebar > KK/VRC Tools / model preprocess / mannual edit",
    "description": "Batch tools for grafting VRC clothing bones and remapping weights to Koikatsu armatures.",
    "category": "Rigging",
}

if "bpy" in locals():
    import importlib
    from . import common
    from . import bone_rules
    from . import vrc_bone_rules
    from . import graft
    from . import weights_body
    from . import weights_torso
    from . import weights_breast
    from . import weights_transfer
    from . import weights_hybrid
    from . import weight_features
    from . import weights_features
    from . import weights_optimization
    from . import mmd_weight_profiles
    from . import optimizer_validation
    from . import optimizer_scope, workflow_regions, workflow_presets, region_patterns, optimizer_profiles, workflow, workflow_beginner
    from . import shoe_field, shoe_presets, shoe_workflow, shoe_ui
    from . import glove_align
    from . import bone_cleanup
    from . import topology_export
    from . import ui_messages, translations
    from . import ui, export_cleanup
    from . import mmd_preprocess_rules, mmd_preprocess, mmd_preprocess_ui
    from . import accessory_rules, accessory_preprocess, accessory_ui

    importlib.reload(ui_messages)
    importlib.reload(mmd_weight_profiles)

    for _module in (common, bone_rules, vrc_bone_rules, graft, weights_body, weights_torso, weights_breast, weights_transfer, weights_hybrid, weight_features, weights_features, optimizer_scope, weights_optimization, optimizer_validation, workflow_regions, workflow_presets, region_patterns, optimizer_profiles, workflow, workflow_beginner, shoe_field, shoe_presets, shoe_workflow, shoe_ui, glove_align, bone_cleanup, topology_export, translations, ui, export_cleanup, mmd_preprocess_rules, mmd_preprocess, mmd_preprocess_ui):
        importlib.reload(_module)
    for _module in (accessory_rules,accessory_preprocess,accessory_ui):
        importlib.reload(_module)
else:
    from . import common
    from . import bone_rules
    from . import vrc_bone_rules
    from . import graft
    from . import weights_body
    from . import weights_torso
    from . import weights_breast
    from . import weights_transfer
    from . import weights_hybrid
    from . import weight_features
    from . import weights_features
    from . import weights_optimization
    from . import optimizer_validation
    from . import optimizer_scope, workflow_regions, workflow_presets, region_patterns, optimizer_profiles, workflow, workflow_beginner
    from . import shoe_field, shoe_presets, shoe_workflow, shoe_ui
    from . import glove_align
    from . import bone_cleanup
    from . import topology_export
    from . import ui_messages, translations
    from . import ui, export_cleanup
    from . import mmd_preprocess_rules, mmd_preprocess, mmd_preprocess_ui
    from . import accessory_rules, accessory_preprocess, accessory_ui

import bpy


CLASSES = (
    *accessory_ui.CLASSES,
    *mmd_preprocess_ui.CLASSES,
    *shoe_workflow.CLASSES,
    *shoe_ui.CLASSES,
    *workflow.CLASSES,
    *workflow_beginner.CLASSES,
    ui.KKVRC_ClothToolsProperties,
    graft.KKVRC_OT_graft_clothes_bones,
    weights_body.KKVRC_OT_remap_body_weights,
    weights_torso.KKVRC_OT_mix_torso_hip_weights,
    weights_breast.KKVRC_OT_remap_breast_simple,
    weights_breast.KKVRC_OT_mix_breast_local,
    weights_transfer.KKVRC_OT_transfer_body_weights_to_fitted_clothes,
    weights_transfer.KKVRC_OT_cleanup_dynamic_body_weights,
    weights_transfer.KKVRC_OT_remove_empty_vertex_groups,
    weights_transfer.KKVRC_OT_swap_lr_vertex_group_weights,
    weights_transfer.KKVRC_OT_remove_bnip_weights,
    weights_hybrid.KKVRC_OT_auto_hybrid_clothes_weights,
    weights_hybrid.KKVRC_OT_postprocess_manual_skirt_weights,
    glove_align.KKVRC_OT_align_vrc_glove_pose_to_kk,
    bone_cleanup.KKVRC_OT_detach_dynamic_bone_subtrees,
    bone_cleanup.KKVRC_OT_mark_selected_dynamic_bone_roots,
    bone_cleanup.KKVRC_OT_delete_selected_bone_tree,
    bone_cleanup.KKVRC_OT_simplify_selected_bone_chain,
    bone_cleanup.KKVRC_OT_merge_selected_parallel_bone_chains,
    bone_cleanup.KKVRC_OT_cleanup_hair_tip_placeholders,
    topology_export.KKVRC_OT_export_armature_topology,
    ui.KKVRC_PT_cloth_tools,
    ui.KKVRC_PT_manual_tools,
    *export_cleanup.CLASSES,
)


def register():
    bpy.app.translations.register(__name__, translations.TRANSLATIONS)
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.kkvrc_mmd_preprocess = bpy.props.PointerProperty(type=mmd_preprocess_ui.KKVRC_MMDSettings)
    bpy.types.Scene.kkvrc_accessory = bpy.props.PointerProperty(type=accessory_ui.KKVRC_AccessorySettings)
    bpy.types.Scene.kkvrc_export_cleanup = bpy.props.PointerProperty(type=export_cleanup.KKVRC_ExportCleanup)
    bpy.types.Scene.kkvrc_cloth_tools = bpy.props.PointerProperty(type=ui.KKVRC_ClothToolsProperties)
    bpy.types.Scene.kkvrc_weight_workflow = bpy.props.PointerProperty(type=workflow.KKVRC_WorkflowProperties)
    bpy.types.Scene.kkvrc_shoes = bpy.props.PointerProperty(type=shoe_ui.KKVRC_ShoeSettings)


def unregister():
    workflow.stop_jobs()
    if hasattr(bpy.types.Scene,'kkvrc_accessory'):
        del bpy.types.Scene.kkvrc_accessory
    if hasattr(bpy.types.Scene, 'kkvrc_mmd_preprocess'):
        del bpy.types.Scene.kkvrc_mmd_preprocess
    if hasattr(bpy.types.Scene, "kkvrc_export_cleanup"):
        del bpy.types.Scene.kkvrc_export_cleanup
    if hasattr(bpy.types.Scene, 'kkvrc_shoes'):
        del bpy.types.Scene.kkvrc_shoes
    if hasattr(bpy.types.Scene, 'kkvrc_weight_workflow'):
        del bpy.types.Scene.kkvrc_weight_workflow
    if hasattr(bpy.types.Scene, "kkvrc_cloth_tools"):
        del bpy.types.Scene.kkvrc_cloth_tools
    for cls in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass
    bpy.app.translations.unregister(__name__)
