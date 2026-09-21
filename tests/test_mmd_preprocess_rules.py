import importlib.util
from pathlib import Path
import unittest

path=Path(__file__).resolve().parents[1]/'kk_vrc_cloth_tools'/'mmd_preprocess_rules.py'
spec=importlib.util.spec_from_file_location('mmd_rules',path)
r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)


def bone(name,parent=None,deps=()):
    return dict(name=name,parent=parent,dependencies=list(deps))


class PlannerTests(unittest.TestCase):
    def setUp(self):
        self.bones=[bone('root'),bone('weighted','root',('helper',)),bone('tip','weighted'),
                    bone('other_asset','weighted'),bone('other_tip','other_asset'),
                    bone('helper','root',('control',)),bone('control','root'),bone('unused')]
    def test_dependency_closure_and_tip(self):
        p=r.plan(self.bones,{'weighted'},confirmed_removals=['other_asset','other_tip','unused'])
        self.assertEqual(set(p['keep']),{'root','weighted','tip','helper','control'})
        self.assertEqual(set(p['remove']),{'other_asset','other_tip','unused'})
    def test_explicit_chain_with_other_asset_exclusion(self):
        p=r.plan(self.bones,{'weighted'},chains=['weighted'],excluded=['other_asset'])
        self.assertNotIn('other_asset',p['keep']);self.assertIn('tip',p['keep'])
    def test_cannot_exclude_weighted_or_dependencies(self):
        for n in ('weighted','helper','control','root'):
            with self.assertRaises(ValueError):r.plan(self.bones,{'weighted'},excluded=[n])
    def test_override_optional_tip(self):
        self.assertIn('tip',r.plan(self.bones,{'weighted'},excluded=['tip'])['remove'])
    def test_zero_weight_middle_preserved(self):
        p=r.plan([bone('a'),bone('middle','a'),bone('weighted','middle')],{'weighted'})
        self.assertIn('middle',p['keep'])
    def test_unknown_and_missing_dependency(self):
        with self.assertRaises(ValueError):r.plan(self.bones,{'weighted'},pins=['missing'])
        with self.assertRaises(ValueError):r.plan([bone('a',deps=['missing'])],{'a'})
    def test_parent_cycle(self):
        with self.assertRaises(ValueError):r.plan([bone('a','b'),bone('b','a')],{'a'})
    def test_aliases_and_collisions(self):
        self.assertEqual(r.canonical('親指０.L'),'左親指0')
        self.assertEqual(r.arm_mapping([bone('腕.L')])['upper_L'],'腕.L')
        self.assertEqual(r.arm_mapping([bone('腕.L'),bone('左腕')])['upper_L'],'')

    def test_body_protection_without_any_weights_or_optional_tips(self):
        names = sorted(r.PROTECTED_BODY_NAMES | r.PROTECTED_BODY_EXTENSIONS)
        p = r.plan([bone(n) for n in names] + [bone('unrelated')], [], preserve_tips=False,
                   confirmed_removals=['unrelated'])
        self.assertEqual(set(p['keep']), set(names))
        self.assertEqual(p['remove'], ['unrelated'])
        self.assertEqual(set(p['zero_weight_kept']), set(names))

    def test_body_metadata_aliases_and_ambiguous_matches_all_protected(self):
        bones = [bone('親指０.L'), bone('左親指0'), bone('膝.R'), bone('腰キャンセル.L'),
                 dict(bone('renamed'), name_j='右足ＩＫ'), bone('左腕飾り'), bone('左腕.001')]
        p = r.plan(bones, [], preserve_tips=False)
        self.assertEqual(set(p['protected_body']), {'親指０.L','左親指0','膝.R','腰キャンセル.L','renamed'})
        self.assertEqual(set(p['review_required']), {'左腕飾り','左腕.001'})
        self.assertEqual(p['remove'], [])

    def test_body_protection_closes_dependencies_and_overrides_exclusions(self):
        bones = [bone('root'), bone('左足','root',['handle']), bone('handle',deps=['controller']),
                 bone('controller'), bone('other_asset','左足')]
        for name in ('root','左足','handle','controller'):
            with self.assertRaisesRegex(ValueError, 'protected body bones'):
                r.plan(bones, [], excluded=[name], preserve_tips=False)
        p = r.plan(bones, [], excluded=['other_asset'], preserve_tips=False)
        self.assertEqual(set(p['keep']), {'root','左足','handle','controller'})

    def test_invalid_ancestor_reports_value_error_not_key_error(self):
        with self.assertRaisesRegex(ValueError, 'Missing bone parent'):
            r.plan([bone('child','parent'),bone('parent','missing')], [])

    def test_unknown_body_names_and_helpers_kept_without_metadata(self):
        bones = [bone('MySpine'), bone('new_body_extension'), dict(bone('_shadow_custom'),helper=True)]
        p = r.plan(bones, [], preserve_tips=False)
        self.assertEqual(set(p['review_required']), {b['name'] for b in bones})
        self.assertEqual(p['remove'], [])

    def test_unknown_keeps_its_dependencies_even_if_deletion_requested(self):
        bones = [bone('unknown_body', deps=['helper']), bone('helper')]
        with self.assertRaisesRegex(ValueError, 'required dependencies'):
            r.plan(bones, [], confirmed_removals=['helper'])
        p = r.plan(bones, [], confirmed_removals=['unknown_body','helper'])
        self.assertEqual(p['remove'], ['helper','unknown_body'])

    def test_confirmed_removal_never_overrides_protection_or_weights(self):
        for b, weights, pins in [(bone('左腕'), [], []), (bone('custom'), ['custom'], []),
                                  (bone('custom'), [], ['custom'])]:
            with self.assertRaises(ValueError):
                r.plan([b], weights, pins=pins, confirmed_removals=[b['name']])

    def test_confirmation_is_exact_not_recursive(self):
        bones = [bone('parent'),bone('child','parent')]
        with self.assertRaises(ValueError):r.plan(bones, [], confirmed_removals=['parent'])
        self.assertEqual(r.plan(bones, [], excluded=['parent'])['remove'], ['child','parent'])

    def test_unknown_confirmation_name_rejected(self):
        with self.assertRaisesRegex(ValueError,'does not exist'):
            r.plan(self.bones, [], confirmed_removals=['typo'])


if __name__=='__main__':unittest.main()
