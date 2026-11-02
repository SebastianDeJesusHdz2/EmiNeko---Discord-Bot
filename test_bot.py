"""Ejecuta pruebas aisladas sin iniciar sesión ni modificar la base del usuario."""
import subprocess
import sys
if __name__ == '__main__':
    raise SystemExit(subprocess.call([sys.executable, '-m', 'unittest', 'test_emineko', '-v']))
