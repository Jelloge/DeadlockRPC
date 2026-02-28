"""Build DeadlockRPC into a standalone binary."""

import subprocess
import sys

def main():
    sep = ";" if sys.platform == "win32" else ":"

    is_windows = sys.platform == "win32"
    output_name = "DeadlockRPC"

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--name", output_name,
        f"--add-data=src/config.json{sep}.",
        f"--add-data=src/favicon.ico{sep}.",
        "src/main.py",
    ]

    # --noconsole hides the terminal window on Windows; on Linux it has no effect
    # but including it would suppress stdout, so skip it there.
    if is_windows:
        cmd += ["--noconsole", "--icon=src/favicon.ico"]

    print("Running:", " ".join(cmd))
    subprocess.run(cmd, check=True)

    artifact = f"dist/{output_name}.exe" if is_windows else f"dist/{output_name}"
    print(f"\nDone! → {artifact}")

if __name__ == "__main__":
    main()
