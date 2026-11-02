"""Cine, fotografía, memoria, bibliotecas conectadas y alertas."""
import asyncio
import datetime as dt
import io
import json
import os
import random
import re
import time
import uuid
from pathlib import Path
from urllib.parse import quote
import discord
from discord.ext import commands,tasks
import logging
from vincular_playnite import Sync, settings, payload
from emi_domain import Domain
from emi_services import Services,ServiceError,ROOT,photo_bytes
from emi_community import Confirm

DATA=ROOT/'data'

class Media(commands.Cog):
    def __init__(self,bot):
        self.bot=bot; self.store=Domain(bot.db.db_path); self.services=Services(bot.api.get_session)
        self.bridge=Sync(self.store)
        self.bridge_lock=asyncio.Lock()
        self.watch.start()
    async def cog_unload(self): self.watch.cancel()
    async def cog_check(self,ctx):
        if not ctx.interaction:
            raise commands.CheckFailure('Usa el comando / para mantener privados tus datos y archivos.')
        return True
    async def cog_command_error(self,ctx,error):
        original=getattr(error,'original',error)
        if isinstance(original,ValueError):
            ctx.emi_handled=True
            await ctx.send(str(original)[:1900],ephemeral=True)
    async def text(self,ctx,title,text):
        if len(text)<=3800:
            await ctx.send(embed=discord.Embed(title=title,description=text or 'Sin resultados.',color=0xD98EBB),ephemeral=True)
        else: await ctx.send(title,file=discord.File(io.BytesIO(text.encode()),filename='emineko.txt'),ephemeral=True)
    @commands.hybrid_command(name='buscar_cine',description='Busca películas o series en TMDB y guárdalas en tu lista.')
    async def buscar_cine(self,ctx,busqueda:str='',tipo:str='pelicula',guardar:int=0):
        if tipo not in ('pelicula','serie'): raise ValueError('Tipo: pelicula o serie.')
        await ctx.defer(ephemeral=True)
        media='movie' if tipo=='pelicula' else 'tv'
        if guardar:
            result=await self.services.tmdb(f'{media}/{guardar}')
            ident=self.store.add(ctx.author.id,0,'cine',result.get('title') or result.get('name'),{'tmdb_id':guardar,'tipo':media,'estado':'pendiente','detalle':'pendiente'})
            await ctx.send(f'Guardado #{ident} en /cine.',ephemeral=True); return
        if not busqueda: raise ValueError('Indica busqueda o guardar con el ID de TMDB.')
        data=await self.services.tmdb(f'search/{media}',{'query':busqueda[:200],'include_adult':'false'})
        lines=[f"**{r.get('title') or r.get('name')}** · ID {r['id']} · {r.get('release_date') or r.get('first_air_date','')}\n{r.get('overview','')[:250]}\nhttps://www.themoviedb.org/{media}/{r['id']}" for r in data.get('results',[])[:20]]
        await self.bot.emi.panel(ctx,'TMDB · '+tipo,lines,True)

    @commands.hybrid_command(name='dondever',description='Disponibilidad regional de película/serie según TMDB y JustWatch.')
    async def dondever(self,ctx,identificador:int,tipo:str='pelicula',pais:str='MX'):
        if tipo not in ('pelicula','serie') or len(pais)!=2 or not pais.isalpha(): raise ValueError('Tipo pelicula/serie y país de dos letras, p. ej. MX.')
        await ctx.defer(ephemeral=True)
        media='movie' if tipo=='pelicula' else 'tv'
        data=await self.services.tmdb(f'{media}/{identificador}/watch/providers')
        region=data.get('results',{}).get(pais.upper(),{})
        lines=[]
        for key,label in [('flatrate','Suscripción'),('rent','Alquiler'),('buy','Compra'),('free','Gratis'),('ads','Con anuncios')]:
            if region.get(key): lines.append(label+': '+', '.join(x['provider_name'] for x in region[key]))
        if region.get('link'): lines.append('[Consultar disponibilidad]('+region['link']+')')
        await self.text(ctx,f'Dónde ver · {pais.upper()}', '\n'.join(lines or ['No hay datos para esa región; no significa que no esté disponible.'])+'\nFuente: JustWatch mediante TMDB. Consulta: '+dt.datetime.now(dt.timezone.utc).isoformat())

    @commands.hybrid_command(name='quevemos',description='Elige hasta tres títulos pendientes de tu lista.')
    async def quevemos(self,ctx):
        rows=[r for r in self.store.list(ctx.author.id,0,'cine') if json.loads(r['data']).get('estado','pendiente') not in ('visto','terminado') and not json.loads(r['data']).get('detalle','').lower().startswith(('visto','terminado'))]
        await self.bot.emi.panel(ctx,'¿Qué vemos?',[r['title'] for r in random.sample(rows,min(3,len(rows)))],True)

    @commands.hybrid_command(name='alertas',description='Avisos privados de precios USD y cambios de fecha de estreno.')
    async def alertas(self,ctx,accion:str='ver',tipo:str='precio',objetivo:str='',limite:float=0.0,identificador:int=0):
        if accion=='buscar':
            await ctx.defer(ephemeral=True)
            data=await self.services.json('https://www.cheapshark.com/api/1.0/games',params={'title':objetivo[:100],'limit':20})
            await self.bot.emi.panel(ctx,'CheapShark · IDs para alertas',[f"{r['external']} · gameID {r['gameID']} · desde {r['cheapest']} USD" for r in data],True); return
        if accion=='crear':
            if tipo not in ('precio','pelicula','serie') or not objetivo.isdigit(): raise ValueError('Tipo precio/pelicula/serie y objetivo numérico: gameID CheapShark o ID TMDB.')
            if tipo=='precio' and not 0<=limite<=10000: raise ValueError('Límite entre 0 y 10000 USD.')
            with self.store.connect() as db:
                if db.execute('SELECT COUNT(*) FROM emi_alerts WHERE owner=?',(ctx.author.id,)).fetchone()[0]>=30: raise ValueError('Máximo 30 alertas por usuario.')
                ident=db.execute('INSERT INTO emi_alerts(owner,kind,target,threshold) VALUES(?,?,?,?)',(ctx.author.id,tipo,objetivo,limite)).lastrowid
            await ctx.send(f'Alerta #{ident} creada. Comprobación cada hora; permite mensajes directos. Los precios se expresan en USD.',ephemeral=True); return
        with self.store.connect() as db:
            if accion=='borrar': db.execute('DELETE FROM emi_alerts WHERE id=? AND owner=?',(identificador,ctx.author.id))
            rows=db.execute('SELECT * FROM emi_alerts WHERE owner=? ORDER BY id',(ctx.author.id,)).fetchall()
        await self.bot.emi.panel(ctx,'Alertas',[f"#{r['id']} · {r['kind']} ID {r['target']} · límite {r['threshold']} USD\nÚltima comprobación: {r['checked'] and dt.datetime.fromtimestamp(r['checked'],dt.timezone.utc).isoformat()}\n{r['error']}" for r in rows],True)

    @commands.hybrid_command(name='importar_juegos',description='Importa un JSON de Playnite/EmiNeko sin duplicar registros.')
    async def importar_juegos(self,ctx,archivo:discord.Attachment):
        if archivo.size>8_000_000: raise ValueError('Archivo máximo: 8 MB.')
        await ctx.defer(ephemeral=True)
        try: games=payload(await archivo.read())
        except (ValueError,UnicodeError): raise ValueError('Se requiere JSON UTF-8 válido.')
        count=self.store.import_games(ctx.author.id,games)
        await ctx.send(f'Importados/actualizados {count} juegos. Consulta /biblioteca.',ephemeral=True)

    @commands.hybrid_command(name='quejuego',description='Recomienda desde tus juegos por plataforma, género y estado.')
    async def quejuego(self,ctx,plataforma:str='',genero:str='',estado:str='pendiente'):
        rows=self.store.list(ctx.author.id,0,'biblioteca'); matched=[]
        for row in rows:
            data=json.loads(row['data']); source=str(data.get('source',data.get('detalle','')))
            if plataforma and plataforma.casefold() not in source.casefold(): continue
            if genero and genero.casefold() not in json.dumps(data.get('genres',[]),ensure_ascii=False).casefold(): continue
            if estado and estado.casefold() not in str(data.get('estado',data.get('detalle','pendiente'))).casefold(): continue
            matched.append(row)
        await self.bot.emi.panel(ctx,'De tu biblioteca',[f"#{r['id']} {r['title']} · {json.loads(r['data']).get('source','')}" for r in random.sample(matched,min(5,len(matched)))],True)

    @commands.hybrid_command(name='foto',description='Guarda y compara fotografías privadas o consulta su ficha EXIF.')
    async def foto(self,ctx,accion:str='ver',archivo:discord.Attachment=None,titulo:str='Fotografía',identificador:int=0,otra:int=0):
        folder=DATA/'photos'
        if accion not in ('ver','guardar','exif','abrir','comparar','borrar'):
            raise ValueError('Acciones: ver, guardar, exif, abrir, comparar y borrar.')
        if accion in ('guardar','exif'):
            if not archivo or archivo.size>12_000_000: raise ValueError('Adjunta JPEG/PNG/WebP de hasta 12 MB.')
            await ctx.defer(ephemeral=True)
            clean,metadata=await asyncio.to_thread(photo_bytes,await archivo.read())
            if accion=='guardar':
                folder.mkdir(parents=True,exist_ok=True)
                filename=uuid.uuid4().hex+'.jpg'; (folder/filename).write_bytes(clean)
                try:
                    with self.store.connect() as db: ident=db.execute('INSERT INTO emi_photos(owner,title,filename,metadata) VALUES(?,?,?,?)',(ctx.author.id,titulo[:180],filename,json.dumps(metadata))).lastrowid
                except Exception:
                    (folder/filename).unlink(missing_ok=True); raise
                await ctx.send(f'Foto #{ident} guardada sin GPS ni otros EXIF incrustados. /foto accion:abrir identificador:{ident}',ephemeral=True)
            else:
                await self.text(ctx,'Ficha fotográfica',json.dumps(metadata,ensure_ascii=False,indent=2))
            return
        with self.store.connect() as db:
            row=db.execute('SELECT * FROM emi_photos WHERE id=? AND owner=?',(identificador,ctx.author.id)).fetchone()
            if accion=='borrar':
                if not row: raise ValueError('Foto no encontrada.')
                db.execute('DELETE FROM emi_photos WHERE id=?',(identificador,))
                (folder/row['filename']).unlink(missing_ok=True)
                db.commit()
                await ctx.send('Foto eliminada.',ephemeral=True); return
            if accion in ('abrir','comparar'):
                if not row: raise ValueError('Foto no encontrada.')
                selected=[row]
                if accion=='comparar':
                    second=db.execute('SELECT * FROM emi_photos WHERE id=? AND owner=?',(otra,ctx.author.id)).fetchone()
                    if not second: raise ValueError('Segunda foto no encontrada.')
                    selected.append(second)
                await ctx.send(files=[discord.File(folder/r['filename'],filename=f"foto-{r['id']}.jpg") for r in selected],ephemeral=True); return
            rows=db.execute('SELECT * FROM emi_photos WHERE owner=? ORDER BY id DESC',(ctx.author.id,)).fetchall()
        await self.bot.emi.panel(ctx,'Galería privada',[f"#{r['id']} · {r['title']}\n{r['metadata']}" for r in rows],True)

    @commands.hybrid_command(name='preguntar',description='Busca palabras en tus registros privados desde este equipo.')
    async def preguntar(self,ctx,pregunta:str):
        from unicodedata import normalize, combining
        def words(value):
            plain = ''.join(ch for ch in normalize('NFD',value.casefold()) if not combining(ch))
            return set(re.findall(r'\w+',plain))
        terms = words(pregunta) - set('que de del el la los las en mi mis un una y tengo hay'.split())
        if not terms:
            raise ValueError('Indica qué palabra o título quieres buscar.')
        await ctx.defer(ephemeral=True)
        matches = []
        with self.store.connect() as db:
            for row in db.execute('SELECT id,title,kind,data FROM emi_items WHERE owner=? ORDER BY id DESC',(ctx.author.id,)):
                detail = str(json.loads(row['data']).get('detalle',''))
                score = len(terms & words(detail)) + 2 * len(terms & words(row['title']+' '+row['kind']))
                if score:
                    matches.append((score,f"#{row['id']} · {row['title']} ({row['kind']})\n{detail[:240]}"))
        matches.sort(key=lambda hit:hit[0],reverse=True)
        await self.bot.emi.panel(ctx,'Coincidencias en tu memoria',[line for _,line in matches[:25]] or ['No encontré registros con esas palabras.'],True)

    @commands.hybrid_command(name='resumen',description='Resume una sesión de texto autorizada o tus notas de la semana.')
    async def resumen(self,ctx,sesion:int=0):
        await ctx.defer(ephemeral=True)
        with self.store.connect() as db:
            if sesion:
                if not ctx.guild: raise ValueError('Consulta la sesión desde su servidor.')
                row=db.execute('SELECT * FROM emi_sessions WHERE id=? AND guild=?',(sesion,ctx.guild.id)).fetchone()
                consent=db.execute('SELECT 1 FROM emi_consent WHERE session=? AND user=?',(sesion,ctx.author.id)).fetchone()
                if not row or not consent: raise ValueError('Necesitas haber aceptado participar en esta sesión.')
                channel=ctx.guild.get_channel(row['channel'])
                if not channel or not channel.permissions_for(ctx.author).view_channel: raise ValueError('Ya no tienes acceso al canal de esa sesión.')
                rows=[dict(r) for r in db.execute('SELECT user,content,created FROM emi_messages WHERE session=? ORDER BY created DESC LIMIT 300',(sesion,))]
            else:
                rows=[dict(r) for r in db.execute('SELECT id,title,data FROM emi_items WHERE owner=? AND created>=? ORDER BY created DESC LIMIT 100',(ctx.author.id,time.time()-7*86400))]
        if not rows: raise ValueError('No hay registros para resumir.')
        if sesion:
            participants=len({row['user'] for row in rows})
            lines=[f"{len(rows)} mensajes recientes de {participants} participantes."]
            lines.extend(f"<@{row['user']}> · {row['content'][:220]}" for row in reversed(rows[:15]))
        else:
            lines=[f"{len(rows)} registros recientes en la semana."]
            for row in rows[:15]:
                detail=json.loads(row['data']).get('detalle','')
                lines.append(f"#{row['id']} · {row['title']}\n{str(detail)[:220]}")
        await self.bot.emi.panel(ctx,'Resumen local · últimas entradas',lines,True)

    @commands.hybrid_command(name='datos',description='Exporta o elimina tu memoria, fotos, avisos y mensajes registrados.')
    async def datos(self,ctx,accion:str='exportar'):
        user=ctx.author.id
        if accion=='exportar':
            with self.store.connect() as db:
                tables={'items':('emi_items','owner'),'recordatorios':('emi_reminders','owner'),'fotos':('emi_photos','owner'),
                    'mensajes':('emi_messages','user'),'alertas':('emi_alerts','owner'),'cartas':('cards','owner_id'),'perfil':('users','user_id'),
                    'arena':('emi_arena','user'),'movimientos':('emi_ledger','user'),'consentimientos':('emi_consent','user')}
                data={name:[dict(r) for r in db.execute(f'SELECT * FROM {table} WHERE {column}=?',(user,))] for name,(table,column) in tables.items()}
                data['organizados']=[dict(r) for r in db.execute('SELECT * FROM emi_items WHERE owner=0 AND json_extract(data,\'$.autor\')=?',(user,))]
            await ctx.send(file=discord.File(io.BytesIO(json.dumps(data,ensure_ascii=False,indent=2).encode()),filename='emineko-datos.json'),ephemeral=True); return
        if accion!='borrar': raise ValueError('Acciones: exportar, borrar.')
        async def forget():
            with self.store.connect() as db:
                photos=db.execute('SELECT filename FROM emi_photos WHERE owner=?',(user,)).fetchall()
                for table,column in [('emi_photos','owner'),('emi_messages','user'),('emi_consent','user'),('emi_alerts','owner'),('emi_reminders','owner'),('emi_votes','user'),('emi_attendees','user')]:
                    db.execute(f'DELETE FROM {table} WHERE {column}=?',(user,))
                db.execute('DELETE FROM emi_items WHERE owner=? AND kind NOT IN (\'mision\',\'expedicion\')',(user,))
                db.execute("DELETE FROM emi_items WHERE owner=0 AND json_extract(data,'$.autor')=?",(user,))
                db.execute('UPDATE emi_sessions SET ended=? WHERE owner=? AND ended=0',(time.time(),user))
                db.execute('UPDATE emi_events SET closed=1 WHERE owner=?',(user,))
            for photo in photos: (DATA/'photos'/photo['filename']).unlink(missing_ok=True)
            (ROOT/'.secrets'/f'youtube-{user}.json').unlink(missing_ok=True)
            return 'Memoria, fotos, avisos y votos eliminados. Se conserva el progreso/economía TCG para evitar duplicar premios. Las copias de seguridad antiguas expiran según la retención del administrador.'
        await ctx.send('¿Eliminar tu memoria y archivos guardados? Esta acción no se puede deshacer desde Discord. El TCG se conserva.',view=Confirm(user,forget),ephemeral=True)

    @commands.hybrid_command(name='creditos',description='Fuentes, licencias y atribuciones de EmiNeko.')
    async def creditos(self,ctx):
        embed=discord.Embed(title='EmiNeko · Créditos',description='TMDB: This product uses the TMDB API but is not endorsed or certified by TMDB.\nDisponibilidad regional: JustWatch mediante TMDB.\nAnime: Jikan/MyAnimeList y AniList.\nPrecios USD: CheapShark.\nVideos: YouTube.\nBibliotecas conectadas: Playnite y sus integraciones.',color=0xD98EBB)
        logo=ROOT/'assets'/'tmdb.png'
        if logo.exists():
            embed.set_thumbnail(url='attachment://tmdb.png')
            await ctx.send(embed=embed,file=discord.File(logo,filename='tmdb.png'),ephemeral=True); return
        await ctx.send(embed=embed,ephemeral=True)

    async def sync_bridge(self, config):
        async with self.bridge_lock:
            return await asyncio.to_thread(self.bridge.run, config)

    @tasks.loop(minutes=5)
    async def watch(self):
        try:
            config = settings()
            if config.owner is not None:
                await self.sync_bridge(config)
        except (ValueError, OSError, TypeError) as exc:
            logging.getLogger(__name__).warning('Playnite: %s', exc)
        with self.store.connect() as db: rows=db.execute('SELECT * FROM emi_alerts WHERE checked<? ORDER BY checked LIMIT 30',(time.time()-3600,)).fetchall()
        for row in rows:
            try:
                if row['kind']=='precio':
                    title,price,deal=await self.services.price(row['target'])
                    state=str(price) if price<=row['threshold'] else 'above'
                    notify=state!='above' and state!=row['state']
                    message=f'🎮 {title}: {price:.2f} USD (límite {row["threshold"]:.2f}). https://www.cheapshark.com/redirect?dealID={quote(deal)}'
                else:
                    kind='movie' if row['kind']=='pelicula' else 'tv'
                    data=await self.services.tmdb(f'{kind}/{row["target"]}')
                    state=(data.get('release_date') or '') if kind=='movie' else json.dumps(data.get('next_episode_to_air') or data.get('last_episode_to_air') or data.get('first_air_date'),sort_keys=True)
                    notify=bool(row['state']) and state!=row['state']
                    message=f'🎬 Cambió la fecha/información de estreno de {data.get("title") or data.get("name")}. https://www.themoviedb.org/{kind}/{row["target"]}'
                if notify:
                    user=self.bot.get_user(row['owner']) or await self.bot.fetch_user(row['owner'])
                    await user.send(message,allowed_mentions=discord.AllowedMentions.none())
                with self.store.connect() as db: db.execute('UPDATE emi_alerts SET state=?,checked=?,error=\'\' WHERE id=?',(state,time.time(),row['id']))
            except (ValueError,discord.HTTPException,KeyError,TypeError) as exc:
                with self.store.connect() as db: db.execute('UPDATE emi_alerts SET checked=?,error=? WHERE id=?',(time.time(),('No se pudo consultar o entregar. Revisa configuración y mensajes privados.')[:200],row['id']))
    @watch.before_loop
    async def before_watch(self): await self.bot.wait_until_ready()

async def setup(bot): await bot.add_cog(Media(bot))

