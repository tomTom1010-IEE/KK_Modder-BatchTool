"""Run in factory-startup Blender; never opens or modifies user projects."""
import ast
from pathlib import Path
import re
import string
import sys
import types

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import bpy
import kk_vrc_cloth_tools as addon
from kk_vrc_cloth_tools import ui_messages as messages

addon.register()
formatter = string.Formatter()
for english, chinese in messages.TEMPLATES.items():
    assert {key for _, key, _, _ in formatter.parse(english) if key} == {
        key for _, key, _, _ in formatter.parse(chinese) if key
    }, english

ui_modules = ['accessory_ui', 'export_cleanup', 'mmd_preprocess_ui', 'shoe_ui',
              'ui', 'workflow', 'workflow_beginner', 'workflow_presets']
for name in ui_modules:
    tree = ast.parse((ROOT / 'kk_vrc_cloth_tools' / (name + '.py')).read_text(encoding='utf-8'))
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            assert not re.search('[\u4e00-\u9fff]', node.value), (name, node.value)

class Layout:
    def box(self): return self
    def row(self, **kwargs): return self
    def column(self, **kwargs): return self
    def split(self, **kwargs): return self
    def separator(self, **kwargs): pass
    def label(self, **kwargs): pass
    def prop(self, obj, key, **kwargs): assert hasattr(obj, key), key
    def prop_search(self, obj, key, *args, **kwargs): assert hasattr(obj, key), key
    def template_list(self, *args, **kwargs): pass
    def operator(self, identifier, **kwargs):
        category, name = identifier.split('.')
        getattr(getattr(bpy.ops, category), name).get_rna_type()
        return types.SimpleNamespace()

panels = [cls for cls in addon.CLASSES if issubclass(cls, bpy.types.Panel)]
for cls in panels:
    cls.draw(types.SimpleNamespace(layout=Layout()), bpy.context)

view = bpy.context.preferences.view
view.use_translate_interface = True
view.language = 'en_US'
translate = bpy.app.translations.pgettext_iface
assert translate('Dynamic Garment Weight Transfer') == 'Dynamic Garment Weight Transfer'
view.language = 'zh_HANS'
assert translate('Dynamic Garment Weight Transfer') == '动骨衣物权重迁移'
assert translate('Manual Editing') == '手动编辑'
assert messages.format_message('Configured: {v0} poses', v0=7) == '已配置 7 个动作'
view.language = 'en_US'
assert messages.format_message('Configured: {v0} poses', v0=7) == 'Configured: 7 poses'
# Bone identifiers and serialized role identifiers must not be translated.
from kk_vrc_cloth_tools import mmd_preprocess_rules as rules
assert rules.canonical('親指０.L') == '左親指0'
props = bpy.context.scene.kkvrc_weight_workflow
bone = props.bones.add()
assert {x.identifier for x in bone.bl_rna.properties['role'].enum_items} == {'REVIEW', 'BODY', 'DYNAMIC', 'IGNORE'}
addon.unregister()
addon.register()
addon.unregister()
print('LOCALIZATION_TEST_OK', len(panels), 'panels;', len(messages.ZH_TO_EN), 'messages;', len(messages.TEMPLATES), 'templates')
