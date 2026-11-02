"""Vincula una exportación local de Playnite a una biblioteca privada de EmiNeko."""
import argparse
from collections import Counter
from dataclasses import dataclass
import json
import os
from pathlib import Path
from dotenv import dotenv_values, set_key
from emi_domain import Domain

ROOT = Path(__file__).resolve().parent
LIMIT = 16_000_000

@dataclass(frozen=True)
class Config:
    path: Path
    owner: int | None

def settings():
    values = dotenv_values(ROOT / '.env', interpolate=False)
    def value(key):
        return str(values.get(key) or os.getenv(key, '')).strip()
    path = ROOT / (value('PLAYNITE_EXPORT_PATH') or 'data/playnite.json')
    owner = value('PLAYNITE_DISCORD_USER_ID')
    return Config(path, discord_id(owner) if owner else None)

def discord_id(value):
    if not value.isascii() or not value.isdecimal() or not 16 <= len(value) <= 19 or not 0 < int(value) < 2**63:
        raise ValueError('Usa el ID numérico de usuario de Discord, no el nombre ni el ID del servidor.')
    return int(value)

def payload(raw):
    data = json.loads(raw.decode('utf-8-sig'))
    games = data.get('games') if isinstance(data, dict) else data
    if not isinstance(games, list):
        raise ValueError('La exportación debe contener una lista games.')
    return games

class Sync:
    def __init__(self, store):
        self.store = store
        self.last = None

    def run(self, config):
        if config.owner is None:
            raise ValueError('Ejecuta vincular_playnite.bat en el PC del bot con tu ID de usuario.')
        with config.path.open('rb') as file:
            stat = os.fstat(file.fileno())
            signature = (config.owner, config.path, stat.st_mtime_ns, stat.st_size)
            if signature == self.last:
                return
            if stat.st_size > LIMIT:
                raise ValueError('La exportación supera el límite de 16 MB.')
            games = payload(file.read(LIMIT+1))
        self.store.import_games(config.owner, games)
        self.last = signature
        return Counter(str(g.get('source') or 'Manual') for g in games)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--usuario', help='ID de usuario de Discord')
    args = parser.parse_args()
    owner = discord_id((args.usuario or input('Tu ID de usuario de Discord: ')).strip())
    config = Config(settings().path, owner)
    values = dotenv_values(ROOT / '.env')
    database = ROOT / (values.get('BOT_DB_PATH') or 'otakubot_data.db')
    counts = Sync(Domain(str(database))).run(config)
    set_key(str(ROOT / '.env'), 'PLAYNITE_DISCORD_USER_ID', str(owner),quote_mode='never')
    print(f'{sum(counts.values())} juegos procesados. ' + ', '.join(f'{k}: {v}' for k,v in sorted(counts.items())))
    print('Vinculación guardada. Abre /biblioteca en tu cuenta de Discord.')
if __name__=='__main__':
    try: main()
    except (ValueError,OSError) as exc: raise SystemExit(f'No se completó la vinculación: {exc}')
