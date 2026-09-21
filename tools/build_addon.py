"""Build the installable add-on including authoritative bone-profile JSON files."""
import argparse, ast, zipfile
from pathlib import Path

def build(destination):
    repo=Path(__file__).resolve().parents[1];package=repo/'kk_vrc_cloth_tools'
    destination=Path(destination);destination.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(destination,'w',zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(package.rglob('*.py')):
            if '__pycache__' not in path.parts:archive.write(path,'kk_vrc_cloth_tools/'+path.relative_to(package).as_posix())
        for path in sorted((repo/'bone_profiles').glob('*.json')):
            archive.write(path,'kk_vrc_cloth_tools/bone_profiles/'+path.name)
    return destination

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('destination');args=parser.parse_args();print(build(args.destination))
