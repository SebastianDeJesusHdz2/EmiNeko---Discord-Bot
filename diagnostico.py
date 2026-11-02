"""Diagnóstico local: no imprime secretos ni se conecta a Discord."""
import importlib
import os
from pathlib import Path
import shutil
import sys
ROOT=Path(__file__).resolve().parent

def main():
    failures=[]
    print('EmiNeko - diagnóstico local')
    for name in ('discord','aiohttp','yt_dlp','nacl','dotenv','PIL','tzdata','imageio_ffmpeg','requests'):
        try: importlib.import_module(name); print('[OK] '+name)
        except ImportError: failures.append(name); print('[FALTA] '+name)
    if failures:
        print('Ejecuta instalar.bat para completar dependencias.'); return 1
    from dotenv import load_dotenv
    load_dotenv(ROOT/'.env')
    token=os.getenv('DISCORD_TOKEN','')
    print('[OK] Token Discord presente (no validado)' if token and token not in ('TU_TOKEN_DE_DISCORD_AQUI','PEGA_TU_TOKEN_AQUI') else '[CONFIGURAR] DISCORD_TOKEN en .env')
    if '--discord' in sys.argv and token:
        import requests
        try:
            response=requests.get('https://discord.com/api/v10/users/@me',headers={'Authorization':'Bot '+token},timeout=12,allow_redirects=False)
            if response.status_code==200 and response.json().get('bot'):
                print('[OK] Discord acepta el token de bot (consulta de solo lectura)')
            else:
                print('[REVISAR] Discord respondió HTTP '+str(response.status_code)); return 2
        except (requests.RequestException,ValueError):
            print('[REVISAR] No se pudo contactar con Discord desde este equipo.'); return 2
    if '--tmdb' in sys.argv:
        import requests
        tmdb = os.getenv('TMDB_TOKEN')
        if not tmdb:
            print('[CONFIGURAR] Falta TMDB_TOKEN'); return 2
        try:
            response = requests.get('https://api.themoviedb.org/3/movie/11', params={'language':'es-MX'}, headers={'Authorization':'Bearer '+tmdb}, timeout=12, allow_redirects=False)
            if response.status_code != 200 or response.json().get('id') != 11:
                print('[REVISAR] TMDB respondió HTTP '+str(response.status_code)); return 2
            print('[OK] TMDB devolvió una ficha de película con el token configurado')
        except (requests.RequestException, ValueError):
            print('[REVISAR] No se pudo consultar TMDB.'); return 2
    import imageio_ffmpeg, subprocess
    result=subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-hide_banner','-loglevel','error','-f','lavfi','-i','sine=frequency=440:duration=0.1','-ar','48000','-ac','2','-f','s16le','pipe:1'], capture_output=True, timeout=15)
    if result.returncode or len(result.stdout)!=19200:
        print('[FALLO] FFmpeg no generó audio PCM. Ejecuta instalar.bat.'); return 1
    print('[OK] FFmpeg generó audio PCM estéreo a 48 kHz')
    for key in ('STEAM_API_KEY','TMDB_TOKEN','PLAYNITE_EXPORT_PATH','PLAYNITE_DISCORD_USER_ID'):
        print(('[CONFIGURADO] ' if os.getenv(key) else '[OPCIONAL] ')+key)
    if os.getenv('PLAYNITE_EXPORT_PATH'):
        print('[OK] Exportación Playnite existe' if Path(os.environ['PLAYNITE_EXPORT_PATH']).is_file() else '[REVISAR] Exporta primero desde Playnite')
    print('Sala web: '+('activada en configuración' if os.getenv('EMI_WEB_ENABLED')=='1' else 'desactivada'))
    print('Prueba de comandos: .venv\\Scripts\\python.exe verify_commands.py')
    print('Pruebas: .venv\\Scripts\\python.exe -m unittest test_emineko test_complete -v')
    print('Guía: PASO_A_PASO.md')
    return 0
if __name__=='__main__': raise SystemExit(main())
