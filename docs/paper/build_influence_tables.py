"""Generate the deployment-extension tables from the public dry-run extract."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def build():
    data = json.loads((ROOT.parent / 'data/influence-limit-benchmark.json').read_text(encoding='utf-8'))
    timing = []; response = []
    for case in data['cases']:
        label = case['label'].replace(' jacket', '')
        baseline = case['same_input_macro']['legacy']['median']
        for mode, title in [('legacy', 'Legacy'), ('unlimited', 'Unlimited'), ('four', 'Four')]:
            t = case['same_input_macro'][mode]
            timing.append(f"{label} & {title} & {t['median']:.2f} & {t['minimum']:.2f}--{t['maximum']:.2f} & {100*(t['median']/baseline-1):+.2f}\\% & {t['support_median']:.2f} \\\\")
        for mode, title in [('legacy', 'Dense'), ('four', 'Four')]:
            r = case['pipeline'][mode]
            for stage, scope in [('macro', case['macro_scope_vertices']), ('terminal', case['terminal_scope_vertices'])]:
                e = r[stage+'_holdout']
                response.append(f"{label} / {stage} & {title} & {scope:,} & {1e3*e['rms']:.6f} & {1e3*e['p95']:.6f} & {1e3*e['max']:.6f} \\\\")
    out = '\\newcommand{\\InfluenceTimingRows}{%\n'+'\n'.join(timing)+'\n}\n'
    out += '\\newcommand{\\InfluenceResponseRows}{%\n'+'\n'.join(response)+'\n}\n'
    (ROOT/'influence_rows.tex').write_text(out, encoding='utf-8')
    print('Generated total-influence timing and response tables from public JSON.')


if __name__ == '__main__':
    build()
