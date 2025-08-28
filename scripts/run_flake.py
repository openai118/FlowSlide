import subprocess
import sys
from pathlib import Path

out = Path(__file__).parent / "flake_output.txt"
proc = subprocess.run([sys.executable, "-m", "flake8", "src", "tests"], capture_output=True, text=True)
with out.open("w", encoding="utf-8") as f:
    if proc.stdout:
        f.write(proc.stdout)
    if proc.stderr:
        f.write("\nSTDERR:\n")
        f.write(proc.stderr)
print(f"Wrote flake output to: {out}")
print(proc.returncode)
