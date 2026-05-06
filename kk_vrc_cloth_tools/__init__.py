bl_info = {
    "name": "KK/VRC Cloth Tools",
    "author": "Tom Xu + Codex",
    "version": (0, 1, 0),
    "blender": (4, 3, 0),
    "location": "View3D > Sidebar > KK/VRC Tools",
    "description": "Batch tools for grafting VRC clothing bones and remapping weights to Koikatsu armatures.",
    "category": "Rigging",
}

if "bpy" in locals():
    import importlib
    from . import common
    from . import graft
    from . import weights_body
    from . import weights_torso
    from . import weights_breast
    from . import weights_transfer
    from . import glove_align
    from . import bone_cleanup
    from . import topology_export
    from . import translations
    from . import ui

    for _module in (common, graft, weights_body, weights_torso, weights_breast, weights_transfer, glove_align, bone_cleanup, topology_export, translations, ui):
        importlib.reload(_module)
else:
    from . import common
    from . import graft
    from . import weights_body
    from . import weights_torso
    from . import weights_breast
    from . import weights_transfer
    from . import glove_align
    from . import bone_cleanup
    from . import topology_export
    from . import translations
    from . import ui

import bpy


CLASSES = (
    ui.KKVRC_ClothToolsProperties,
    graft.KKVRC_OT_graft_clothes_bones,
    weights_body.KKVRC_OT_remap_body_weights,
    weights_torso.KKVRC_OT_mix_torso_hip_weights,
    weights_breast.KKVRC_OT_remap_breast_simple,
    weights_breast.KKVRC_OT_mix_breast_local,
    weights_transfer.KKVRC_OT_transfer_body_weights_to_fitted_clothes,
    weights_transfer.KKVRC_OT_cleanup_dynamic_body_weights,
    glove_align.KKVRC_OT_align_vrc_glove_pose_to_kk,
    bone_cleanup.KKVRC_OT_delete_selected_bone_tree,
    bone_cleanup.KKVRC_OT_simplify_selected_bone_chain,
    bone_cleanup.KKVRC_OT_cleanup_hair_tip_placeholders,
    topology_export.KKVRC_OT_export_armature_topology,
    ui.KKVRC_PT_cloth_tools,
)


def register():
    bpy.app.translations.register(__name__, translations.TRANSLATIONS)
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.kkvrc_cloth_tools = bpy.props.PointerProperty(type=ui.KKVRC_ClothToolsProperties)


def unregister():
    if hasattr(bpy.types.Scene, "kkvrc_cloth_tools"):
        del bpy.types.Scene.kkvrc_cloth_tools
    for cls in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass
    bpy.app.translations.unregister(__name__)
