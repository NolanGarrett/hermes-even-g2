"""Package explicit public files only; no environments, logs, auth or runtime data."""
from pathlib import Path
import hashlib
import shutil
import subprocess
import zipfile

ROOT=Path(__file__).resolve().parents[1]
VERSION='0.1.0a1'

def archive(path,entries):
    with zipfile.ZipFile(path,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        for source,target in sorted(entries,key=lambda p:p[1]):
            info=zipfile.ZipInfo(target,date_time=(2026,1,1,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644<<16
            archive.writestr(info,source.read_bytes())

def main():
    if subprocess.check_output(['git','status','--porcelain','--untracked-files=normal'],cwd=ROOT,text=True).strip():
        raise SystemExit('Commit reviewed source and generated documentation before packaging; working tree must be clean')
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    # Ignored build outputs are not covered by git status. Always rebuild them
    # from this clean source, rather than trusting a stale local dist or EHPK.
    for action in ['build','pack']:
        if action=='pack':(ROOT/'companion/hermes-even-g2.ehpk').unlink(missing_ok=True)
        subprocess.run(['npm','run',action],cwd=ROOT/'companion',check=True)
    if subprocess.check_output(['git','status','--porcelain','--untracked-files=normal'],cwd=ROOT,text=True).strip():
        raise SystemExit('Build modified source; review and commit before packaging')
    # Main artifacts are snapshots, never replacements for an immutable release.
    version=VERSION+'+g'+head[:12]
    out=ROOT/'release'/version
    out.mkdir(parents=True,exist_ok=True)
    tracked=[Path(p) for p in subprocess.check_output(['git','ls-files'],cwd=ROOT,text=True).splitlines()]
    plugin=[p for p in tracked if p.parts[0] in {'even_g2','docs'} or str(p) in {'__init__.py','plugin.yaml','LICENSE','README.md','SECURITY.md','THIRD_PARTY_NOTICES.md','CHANGELOG.md'}]
    required={'__init__.py','plugin.yaml','LICENSE','README.md'}
    if not required.issubset({str(p) for p in plugin}):raise SystemExit('Stage the complete source before packaging')
    archive(out/f'hermes-even-g2-plugin-{version}.zip',[(ROOT/p,'hermes-even-g2/'+p.as_posix()) for p in plugin])
    dist=ROOT/'companion/dist'
    if not (dist/'index.html').is_file() or not (dist/'THIRD_PARTY_NOTICES.txt').is_file():raise SystemExit('Build companion with notices before packaging')
    archive(out/f'hermes-even-g2-companion-web-template-{version}.zip',[(p,p.relative_to(dist).as_posix()) for p in dist.rglob('*') if p.is_file()])
    shutil.copy2(ROOT/'companion/hermes-even-g2.ehpk',out/f'hermes-even-g2-companion-template-{version}.ehpk')
    subprocess.run(['git','archive','--format=zip','--prefix=hermes-even-g2/','-o',str(out/f'hermes-even-g2-source-{version}.zip'),'HEAD'],cwd=ROOT,check=True)
    files=sorted(p for p in out.iterdir() if p.is_file() and p.name!='SHA256SUMS')
    (out/'SHA256SUMS').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n' for p in files))
    print('\n'.join(p.name for p in files))

if __name__=='__main__':main()
