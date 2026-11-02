from pathlib import Path
import logging
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv
from emi_runtime import instance_lock,backup,ROOT
import os

def main():
    load_dotenv(ROOT/'.env')
    os.chdir(ROOT)
    with instance_lock():
        backup(os.getenv('BOT_DB_PATH','otakubot_data.db'))
        logs=ROOT/'logs';logs.mkdir(exist_ok=True)
        handler=RotatingFileHandler(logs/'emineko.log',maxBytes=2_000_000,backupCount=3,encoding='utf-8')
        handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(name)s %(message)s'))
        import bot
        logging.getLogger().addHandler(handler)
        if not bot.DISCORD_TOKEN or bot.DISCORD_TOKEN in ('TU_TOKEN_DE_DISCORD_AQUI','PEGA_TU_TOKEN_AQUI'):
            raise SystemExit('Configura DISCORD_TOKEN en .env. Consulta PASO_A_PASO.md.')
        bot.bot.run(bot.DISCORD_TOKEN)
if __name__=='__main__':
    try: main()
    except RuntimeError as exc: raise SystemExit(str(exc))
