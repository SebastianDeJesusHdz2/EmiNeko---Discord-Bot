"""Sala de video YouTube: control desde Discord, reproducción en navegador."""
import os
import secrets
import time
from pathlib import Path
from aiohttp import web
from discord.ext import commands
from emi_domain import Domain
from emi_services import video_id

ROOT=Path(__file__).resolve().parent

class Rooms(commands.Cog):
    def __init__(self,bot): self.bot=bot; self.store=Domain(bot.db.db_path); self.runner=None; self.failure=''
    async def cog_load(self):
        if os.getenv('EMI_WEB_ENABLED','0')!='1': return
        app=web.Application(client_max_size=1024)
        app.router.add_get('/',self.page); app.router.add_get('/api/state',self.state)
        self.runner=web.AppRunner(app,access_log=None)
        await self.runner.setup()
        try: await web.TCPSite(self.runner,os.getenv('EMI_WEB_HOST','127.0.0.1'),int(os.getenv('EMI_WEB_PORT','8765'))).start()
        except (OSError,ValueError):
            self.failure='No se pudo abrir el puerto web. Revisa EMI_WEB_HOST/PORT.'
            await self.runner.cleanup(); self.runner=None
    async def cog_unload(self):
        if self.runner: await self.runner.cleanup()
    async def page(self,request):
        return web.Response(text=(ROOT/'sala.html').read_text(encoding='utf-8'),content_type='text/html',headers={'Cache-Control':'no-store','Referrer-Policy':'strict-origin-when-cross-origin','X-Content-Type-Options':'nosniff'})
    async def state(self,request):
        token=request.headers.get('Authorization','').removeprefix('Bearer ')
        if len(token)<30: raise web.HTTPUnauthorized()
        with self.store.connect() as db: row=db.execute('SELECT * FROM emi_rooms WHERE token=? AND expires>?',(token,time.time())).fetchone()
        if not row: raise web.HTTPNotFound()
        elapsed=time.time()-row['updated'] if row['playing'] else 0
        return web.json_response({'video':row['video'],'position':row['position']+max(0,elapsed),'playing':bool(row['playing']),'expires':row['expires']},headers={'Cache-Control':'no-store'})
    @commands.hybrid_command(name='sala',description='Crea y controla una sala de video sincronizado de YouTube.')
    @commands.guild_only()
    async def sala(self,ctx,accion:str='enlace',url:str='',segundos:int=0):
        if not ctx.interaction: await ctx.send('Usa /sala para no publicar enlaces privados.'); return
        if not self.runner:
            await ctx.send(self.failure or 'Activa EMI_WEB_ENABLED=1 y configura EMI_WEB_PUBLIC_URL. Consulta PASO_A_PASO.md.',ephemeral=True); return
        with self.store.connect() as db:
            row=db.execute('SELECT * FROM emi_rooms WHERE owner=? AND guild=? AND expires>? ORDER BY expires DESC LIMIT 1',(ctx.author.id,ctx.guild.id,time.time())).fetchone()
            if accion=='crear':
                vid=video_id(url)
                if not vid: await ctx.send('Indica una URL HTTPS de video de YouTube.',ephemeral=True); return
                token=secrets.token_urlsafe(32)
                if row: db.execute('DELETE FROM emi_rooms WHERE token=?',(row['token'],))
                db.execute('INSERT INTO emi_rooms VALUES(?,?,?,?,?,?,?,?)',(token,ctx.author.id,ctx.guild.id,vid,0,0,time.time(),time.time()+86400))
                row=db.execute('SELECT * FROM emi_rooms WHERE token=?',(token,)).fetchone()
            if not row: await ctx.send('Crea una sala con accion:crear url:URL. Dura 24 horas.',ephemeral=True); return
            position=row['position']+(time.time()-row['updated'] if row['playing'] else 0)
            if accion in ('pausa','reanudar','ir'):
                if accion=='ir' and not 0<=segundos<=86400: await ctx.send('Posición de 0–86400 segundos.',ephemeral=True); return
                db.execute('UPDATE emi_rooms SET position=?,playing=?,updated=? WHERE token=?',(segundos if accion=='ir' else position,0 if accion=='pausa' else 1 if accion=='reanudar' else row['playing'],time.time(),row['token']))
            elif accion=='cerrar':
                db.execute('DELETE FROM emi_rooms WHERE token=?',(row['token'],)); await ctx.send('Sala cerrada; enlace invalidado.',ephemeral=True); return
            elif accion not in ('crear','enlace'): await ctx.send('Acciones: crear, enlace, pausa, reanudar, ir, cerrar.',ephemeral=True); return
        base=os.getenv('EMI_WEB_PUBLIC_URL','http://127.0.0.1:8765').rstrip('/')
        await ctx.send(f'Sala: {base}/#{row["token"]}\nComparte este enlace solo con los participantes. Control desde /sala pausa, reanudar o ir. Cada navegador debe pulsar Entrar para permitir reproducción. El enlace vence en 24 horas.',ephemeral=True)
async def setup(bot): await bot.add_cog(Rooms(bot))
