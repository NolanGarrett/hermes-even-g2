"""Package explicit public files only; no environments, logs, auth or runtime data."""
from pathlib import Path
import hashlib
import shutil
import subprocess
import zipfile

ROOT=Path(__file__).resolve().parents[1]
VERSION='0.1.0a1'
OUT=ROOT/'release'

def archive(path,entries):
    with zipfile.ZipFile(path,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        for source,target in sorted(entries,key=lambda p:p[1]):
            info=zipfile.ZipInfo(target,date_time=(2026,1,1,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644<<16
            archive.writestr(info,source.read_bytes())

def main():
    OUT.mkdir(exist_ok=True)
    tracked=[Path(p) for p in subprocess.check_output(['git','ls-files'],cwd=ROOT,text=True).splitlines()]
    plugin=[p for p in tracked if p.parts[0] in {'even_g2','docs'} or str(p) in {'__init__.py','plugin.yaml','LICENSE','README.md','SECURITY.md','THIRD_PARTY_NOTICES.md','CHANGELOG.md'}]
    required={'__init__.py','plugin.yaml','LICENSE','README.md'}
    if not required.issubset({str(p) for p in plugin}):raise SystemExit('Stage the complete source before packaging')
    archive(OUT/f'hermes-even-g2-plugin-{VERSION}.zip',[(ROOT/p,'hermes-even-g2/'+p.as_posix()) for p in plugin])
    dist=ROOT/'companion/dist'
    if not (dist/'index.html').is_file() or not (dist/'THIRD_PARTY_NOTICES.txt').is_file():raise SystemExit('Build companion with notices before packaging')
    archive(OUT/f'hermes-even-g2-companion-web-template-{VERSION}.zip',[(p,p.relative_to(dist).as_posix()) for p in dist.rglob('*') if p.is_file()])
    shutil.copy2(ROOT/'companion/hermes-even-g2.ehpk',OUT/f'hermes-even-g2-companion-template-{VERSION}.ehpk')
    subprocess.run(['git','archive','--format=zip','--prefix=hermes-even-g2/','-o',str(OUT/f'hermes-even-g2-source-{VERSION}.zip'),'HEAD'],cwd=ROOT,check=True)
    files=sorted(p for p in OUT.iterdir() if p.is_file() and p.name!='SHA256SUMS')
    (OUT/'SHA256SUMS').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n' for p in files))
    print('\n'.join(p.name for p in files))

if __name__=='__main__':main()
