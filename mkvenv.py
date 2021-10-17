import os, subprocess, sys, venv
venv.create(".venv", with_pip=True)
vpy = os.path.join(".venv", "Scripts" if sys.platform == "win32" else "bin", "python")
subprocess.check_call([vpy, "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel"])
subprocess.check_call([vpy, "-m", "pip", "install", "--upgrade", "img2pdf", "pillow"])
