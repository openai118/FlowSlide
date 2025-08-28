import subprocess
import sys
from pathlib import Path

out = Path('scripts/web_flake_after.txt')
try:
    res = subprocess.run([sys.executable, '-m', 'flake8', 'src/flowslide/web'], capture_output=True, text=True)
    out.write_text(res.stdout + '\n' + res.stderr)
    print('Wrote flake results to', out)
    sys.exit(res.returncode)
except Exception as e:
    out.write_text('ERROR: ' + str(e))
    print('Failed to run flake8:', e)
    sys.exit(1)
