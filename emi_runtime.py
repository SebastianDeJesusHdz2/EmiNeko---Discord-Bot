"""Backup SQLite consistente, registro del arranque y bloqueo de segunda instancia."""
from pathlib import Path
import contextlib
import datetime as dt
import errno
import os
import sqlite3

ROOT=Path(__file__).resolve().parent

def backup(path):
    source=Path(path).resolve()
    if not source.exists(): return None
    target=ROOT/'backups'; target.mkdir(exist_ok=True)
    dest=target/('emineko-'+dt.datetime.now(dt.timezone.utc).strftime('%Y%m%d-%H%M%S-%f')+'.db')
    with contextlib.closing(sqlite3.connect(str(source))) as src, contextlib.closing(sqlite3.connect(str(dest))) as out:
        src.backup(out)
    # Only delete files created by this backup routine in the resolved backup directory.
    for old in sorted(target.glob('emineko-*.db'),key=lambda p:p.stat().st_mtime,reverse=True)[14:]:
        if old.resolve().parent==target.resolve(): old.unlink()
    return dest

@contextlib.contextmanager
def instance_lock():
    path = ROOT / 'data' / 'instance.lock'
    try:
        path.parent.mkdir(exist_ok=True)
        handle = path.open('a+b')
    except OSError as exc:
        raise RuntimeError(f'No se pudo abrir {path}. Comprueba los permisos de la carpeta data.') from exc
    with handle:
        # Windows enforces byte-range locks even on reads. Lock byte 0 directly,
        # including when the range extends past the end of an empty file.
        handle.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            if exc.errno in (errno.EACCES, errno.EAGAIN, errno.EDEADLK):
                raise RuntimeError('EmiNeko ya está en ejecución. Para reiniciarlo, pulsa Ctrl+C en la consola activa y vuelve a abrir iniciar_bot.bat.') from None
            raise RuntimeError(f'No se pudo bloquear {path}: {exc.strerror}') from exc
        yield
        # Closing the handle releases the lock, also after an exception.

if __name__=='__main__':
    from dotenv import load_dotenv
    load_dotenv(ROOT/'.env')
    print(backup(os.getenv('BOT_DB_PATH',str(ROOT/'otakubot_data.db'))) or 'No hay base todavía.')
