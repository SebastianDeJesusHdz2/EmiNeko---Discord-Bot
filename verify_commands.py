"""Valida todas las extensiones sin iniciar sesión ni usar APIs externas."""
import asyncio
import os
from pathlib import Path
os.environ['BOT_DB_PATH']=str(Path(__file__).resolve().parent/'.emi-verify.db')
os.environ['EMI_WEB_ENABLED']='0'
import bot

class Author: id=987654321
class Context:
    author=Author()
    async def send(self,*args,**kwargs): pass

async def main():
    await bot.bot._async_setup_hook()
    for extension in ('emineko','emi_community','emi_media','emi_audio','emi_rooms','emi_dashboard'):
        await bot.bot.load_extension(extension)
    for command in bot.bot.tree.get_commands(): command.to_dict(bot.bot.tree)
    names={c.name for c in bot.bot.tree.get_commands()}
    assert {'tirar','tienda','comprar','coleccion','audio','pausa','reanudar','raid','encuesta','sala','sesion','preguntar','play','cola','youtube'} <= names
    library = bot.bot.tree.get_command('biblioteca')
    assert next(p.default for p in library.parameters if p.name=='accion') == 'ver'
    assert not names.intersection({'playlist','youtube_lista'})
    assert len(names)<=100
    print(f'{len(bot.bot.commands)} comandos y esquemas slash válidos')
    cog=bot.bot.emi
    with cog.store.connect() as db:
        db.execute('DELETE FROM emi_items WHERE owner=?',(Author.id,))
        db.execute('DELETE FROM users WHERE user_id=?',(Author.id,))
    ctx=Context()
    await cog.misiones.callback(cog,ctx,'ver')
    with cog.store.connect() as db: db.execute('UPDATE users SET wins=3 WHERE user_id=?',(ctx.author.id,))
    await cog.misiones.callback(cog,ctx,'reclamar'); await cog.misiones.callback(cog,ctx,'reclamar')
    assert bot.bot.db.ensure_user(ctx.author.id)['coins']==650
    print('Recompensa única de misión: OK')
    # Generate reference straight from the registered command signatures.
    lines=['# Comandos de EmiNeko','',f'Total: {len(bot.bot.commands)} comandos. Usa `/inicio` para navegar.','']
    for command in sorted(bot.bot.commands,key=lambda c:c.name):
        lines.extend([f'## /{command.name}',command.description or command.help or '',f'Prefijo: `!{command.name} {command.signature}`',''])
    Path(__file__).with_name('COMANDOS.md').write_text('\n'.join(lines),encoding='utf-8')
    for extension in list(bot.bot.extensions): await bot.bot.unload_extension(extension)
    await bot.bot.api.close()
    print('Descarga de extensiones: OK')
if __name__=='__main__': asyncio.run(main())
