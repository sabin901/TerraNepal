"""Copy only reviewed public assets; no archive export, credentials or network calls."""
from pathlib import Path
import shutil
ROOT = Path(__file__).resolve().parents[1]
ASSETS = ('index.html', 'app.js', 'style.css', 'logic.js', 'favicon.svg', 'i18n.js', 'terra-map.js')

def build(output=None):
    out = Path(output) if output is not None else ROOT/'public'
    if out.exists() and any(out.iterdir()):
        raise ValueError('Output must be empty; do not mix private and public assets')
    out.mkdir(parents=True, exist_ok=True)
    for name in ASSETS:
        shutil.copyfile(ROOT/'public_site/static'/name, out/name)
    for name in ('lab-status.html', 'lab-status.css'):
        shutil.copyfile(ROOT/'disaster_lab/static'/name, out/name)
    # Make the deployed scope unmistakable without changing the GitHub Pages UI.
    index=out/'index.html'
    page=index.read_text(encoding='utf-8').replace('NEPAL / PUBLIC RESEARCH BETA', 'NEPAL / VERCEL PUBLIC RESEARCH')
    page=page.replace('<div id="status"', '<p>Public evidence deployment. Private archive and case editing remain in the local lab. <a href="/api/capabilities">Deployment capabilities</a></p><div id="status"')
    index.write_text(page,encoding='utf-8')
    print('Prepared 9 allowlisted public assets; no local archive or state included.')

if __name__ == '__main__':
    build()
