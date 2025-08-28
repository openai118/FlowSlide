"""Run flake8 CLI via subprocess and write output to scripts/flake_output.txt
"""
import subprocess
from pathlib import Path

out = subprocess.run(["python", "-m", "flake8", "."], capture_output=True, text=True)
path = Path(__file__).resolve().parent / "flake_output.txt"
path.write_text(out.stdout + out.stderr, encoding="utf-8")
print(f"Wrote flake8 output ({len(out.stdout.splitlines()) + len(out.stderr.splitlines())} lines) to {path}")
if out.returncode == 0:
    print("flake8 reported no issues.")
else:
    print(f"flake8 exit code: {out.returncode}")
