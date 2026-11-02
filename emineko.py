"""Módulos persistentes de EmiNeko: biblioteca, comunidad, medios y memoria."""
import asyncio
import datetime as dt
import io
import json
import os
import random
import time
from urllib.parse import urlparse
import discord
from discord.ext import commands, tasks
from emi_store import Store

HELP = {
 'biblioteca': 'Tu biblioteca personal. agregar: título + detalle (plataforma). estado: ID + detalle (pendiente/jugando/terminado). ver, recomendar, borrar.',
 'cine': 'Películas, series y anime. agregar: título + detalle. estado: ID + detalle (episodio/progreso/reseña). ver, recomendar, borrar.',
 'fotografia': 'Bitácora de fotografía. agregar: título + detalle (equipo, técnica, referencia o enlace). estado: ID + detalle. ver, reto, borrar.',
 'memoria': 'Notas y preferencias privadas. agregar: título + detalle. buscar: título. ver, borrar: ID, exportar.',
 'tareas': 'Pendientes personales. agregar: título + detalle. estado: ID + detalle (hecho/pendiente). ver, borrar.',
 'reunion': 'Eventos del servidor. agregar: título + detalle (fecha ISO con zona, agenda). ver, unirme: ID, estado: ID + acuerdos o agenda, borrar: ID.',
 'partida': 'Convocatorias del servidor. agregar: juego + detalle (horario, plazas, plataforma). ver, unirme: ID, estado: ID + detalle, borrar: ID.',
}

class Pages(discord.ui.View):
    def __init__(self, user, title, lines):
        super().__init__(timeout=180)
        self.user, self.title, self.lines, self.page = user,title,lines or ['Sin registros todavía.'],0
    def embed(self):
        chunks=self.lines[self.page*8:(self.page+1)*8]
        e=discord.Embed(title=self.title,description='\n\n'.join(x[:450] for x in chunks),color=0xD98EBB)
        e.set_footer(text=f'Página {self.page+1}/{max(1,(len(self.lines)+7)//8)}')
        return e
    async def interaction_check(self,i):
        if i.user.id==self.user: return True
        await i.response.send_message('Abre tu propio panel para navegar.',ephemeral=True)
        return False
    @discord.ui.button(label='Anterior',emoji='◀️')
    async def previous(self,i,b):
        self.page=max(0,self.page-1)
        await i.response.edit_message(embed=self.embed(),view=self)
    @discord.ui.button(label='Siguiente',emoji='▶️')
    async def next(self,i,b):
        self.page=min((len(self.lines)-1)//8,self.page+1)
        await i.response.edit_message(embed=self.embed(),view=self)

def button_context(interaction, bot, command):
    from discord.ext.commands.view import StringView
    ctx = commands.Context(message=interaction.message, bot=bot, view=StringView(''), interaction=interaction, command=command)
    ctx.author = interaction.user
    return ctx

class Shop(discord.ui.View):
    def __init__(self,bot,user):
        super().__init__(timeout=120)
        self.bot,self.user=bot,user
        for code,label in [('pack_tiradas','5 tiradas · 220 🪙'),('sobre_sr','Sobre SR+ · 380 🪙'),('sobre_ssr','Sobre SSR+ · 850 🪙')]:
            button=discord.ui.Button(label=label,custom_id=code,style=discord.ButtonStyle.primary)
            async def buy(i, product=code):
                if i.user.id!=self.user:
                    await i.response.send_message('Abre /tienda para comprar con tu cuenta.',ephemeral=True)
                    return
                await i.response.defer(ephemeral=True,thinking=True)
                ctx=button_context(i,self.bot,self.bot.get_command('comprar'))
                async with self.bot.emi_purchase_lock:
                    await self.bot.get_command('comprar').callback(ctx,product)
            button.callback=buy
            self.add_item(button)

class Emi(commands.Cog):
    def __init__(self,bot):
        self.bot=bot
        self.store=Store(bot.db.db_path)
        self.notifications.start()
    async def cog_unload(self):
        self.notifications.cancel()
    async def panel(self,ctx,title,lines,private=False):
        view=Pages(ctx.author.id,title,lines)
        if private and not ctx.interaction:
            try: await ctx.author.send(embed=view.embed(),view=view)
            except discord.Forbidden: await ctx.send('Activa mensajes privados o usa el comando / para consultar en privado.')
        else:
            await ctx.send(embed=view.embed(),view=view,ephemeral=private)

    @tasks.loop(seconds=30)
    async def notifications(self):
        with self.store.connect() as db:
            rows=db.execute('SELECT * FROM emi_reminders WHERE sent=0 AND due<=? AND attempts<5',(time.time(),)).fetchall()
        for row in rows:
            try:
                channel=self.bot.get_channel(row['channel']) or await self.bot.fetch_channel(row['channel'])
                await channel.send(f"⏰ <@{row['owner']}> {row['body']}",allowed_mentions=discord.AllowedMentions(users=[discord.Object(row['owner'])],roles=False,everyone=False))
            except (discord.HTTPException,discord.Forbidden):
                with self.store.connect() as db:
                    db.execute('UPDATE emi_reminders SET attempts=attempts+1,due=? WHERE id=?',(time.time()+300,row['id']))
            else:
                with self.store.connect() as db:
                    repeat=row['repeat_seconds'] if 'repeat_seconds' in row.keys() else 0
                    if repeat:
                        next_due=row['due']+(int(max(0,time.time()-row['due'])//repeat)+1)*repeat
                        db.execute('UPDATE emi_reminders SET due=?,attempts=0 WHERE id=?',(next_due,row['id']))
                    else: db.execute('UPDATE emi_reminders SET sent=1 WHERE id=?',(row['id'],))
    @notifications.before_loop
    async def ready(self): await self.bot.wait_until_ready()

    @commands.hybrid_command(name='inicio',description='Panel principal y guía de EmiNeko.')
    async def inicio(self,ctx):
        from emi_dashboard import Dashboard, SECTIONS
        title, text = SECTIONS['inicio']
        if not ctx.interaction:
            await ctx.send('Usa /inicio para abrir el panel privado.'); return
        await ctx.send(embed=discord.Embed(title=title, description=text, color=0xD98EBB), view=Dashboard(ctx.author.id), ephemeral=True)

    @commands.hybrid_command(name='privacidad',description='Cómo se conserva y consulta tu memoria.')
    async def privacidad(self,ctx):
        await ctx.send('EmiNeko guarda tus registros explícitos. /sesion permite guardar texto únicamente de quienes aceptan participar; /sesion retirar elimina sus mensajes. No graba voz. Biblioteca, cine, fotos, tareas y notas son privadas por defecto. Reuniones, partidas y encuestas son públicas en su servidor. Usa borrar en cada módulo y /memoria exportar para tus registros. Los administradores del equipo que aloja SQLite pueden acceder a la base. Los recordatorios se publican en el canal donde se crean.',ephemeral=True)

    @commands.hybrid_command(name='saldo',description='Consulta monedas, cristales y tiradas.')
    async def saldo(self,ctx):
        r=self.bot.db.ensure_user(ctx.author.id)
        await ctx.send(f"🪙 {r['coins']} monedas · 💎 {r['crystals']} cristales · 🎟️ {r['pulls_left']} tiradas. /tienda para comprar.",ephemeral=True)

    @commands.hybrid_command(name='perfil',description='Tu perfil de EmiNeko y progreso TCG.')
    async def perfil(self,ctx):
        r=self.bot.db.ensure_user(ctx.author.id)
        with self.store.connect() as db:
            cosmetic=db.execute('SELECT code FROM emi_cosmetics WHERE user=? AND equipped=1',(ctx.author.id,)).fetchone()
        from emi_community import COSMETICS
        badge=COSMETICS.get(cosmetic['code'],('',0))[0] if cosmetic else ''
        favorites=self.store.list(ctx.author.id,0,'favorita')
        favorite=favorites[0]['title'] if favorites else 'sin favorita'
        await self.panel(ctx,f'🐾 {ctx.author.display_name} {badge}',[f"Monedas: {r['coins']} · Tiradas: {r['pulls_left']}",f"Favorita: {favorite} · Cartas: {len(self.bot.db.get_user_cards(ctx.author.id))} · Victorias: {r['wins']} · Derrotas: {r['losses']}",f"Racha: {r['daily_streak']} · MAL: {r['mal_username'] or 'sin vincular'}"],True)

    @commands.hybrid_command(name='estado',description='Estado del bot y módulos configurados.')
    async def estado(self,ctx):
        import shutil
        checks = {'Steam': bool(os.getenv('STEAM_API_KEY')), 'TMDB': bool(os.getenv('TMDB_TOKEN')), 'Puente Playnite': bool(__import__('vincular_playnite').settings().owner and __import__('vincular_playnite').settings().path.is_file()), 'FFmpeg': bool(__import__('imageio_ffmpeg').get_ffmpeg_exe())}
        rooms=self.bot.get_cog('Rooms')
        checks['Sala web']=bool(rooms and rooms.runner)
        from pathlib import Path
        await ctx.send('🐾 EmiNeko · configuración (no prueba credenciales):\n'+'\n'.join(('✅ ' if value else '⬜ ')+name for name,value in checks.items())+'\nMemoria persistente activa. Consulta PASO_A_PASO.md para activar conexiones.',ephemeral=True)

    async def records(self,ctx,kind,action,title,detail,item_id):
        action=action.lower().strip()
        shared=kind in ('reunion','partida')
        if shared and not ctx.guild:
            await ctx.send('Este módulo necesita un servidor.'); return
        guild=ctx.guild.id if shared else 0
        owner=0 if shared else ctx.author.id
        if not shared and not ctx.interaction:
            await ctx.send('Usa /'+kind+' para mantener tus datos privados.'); return
        if action=='ayuda':
            await ctx.send(HELP[kind],ephemeral=True); return
        if action=='exportar' and kind=='memoria':
            with self.store.connect() as db:
                data=[dict(r) for r in db.execute('SELECT * FROM emi_items WHERE owner=?',(ctx.author.id,))]
            file=discord.File(io.BytesIO(json.dumps(data,ensure_ascii=False,indent=2).encode()),filename='emineko-mis-datos.json')
            if ctx.interaction: await ctx.send(file=file,ephemeral=True)
            else:
                try: await ctx.author.send(file=file)
                except discord.Forbidden: await ctx.send('Usa /memoria accion:exportar para descargar en privado.')
            return
        if action=='reto' and kind=='fotografia':
            await ctx.send(random.choice(['Fotografía un reflejo sin mostrar la cámara.','Cuenta una historia con tres sombras.','Busca una composición de un solo color.','Captura movimiento con un fondo estático.'])); return
        if action=='agregar':
            if not title or len(title)>180 or len(detail)>1500:
                await ctx.send('Escribe un título de hasta 180 caracteres y un detalle de hasta 1500.',ephemeral=True); return
            ident=self.store.add(owner,guild,kind,title,{'detalle':detail,'estado':'pendiente','autor':ctx.author.id,'participantes':[]})
            await ctx.send(f'Guardado #{ident}: {discord.utils.escape_markdown(title)}.',ephemeral=not shared); return
        notice = ''
        if kind == 'biblioteca' and action in ('ver','buscar'):
            from vincular_playnite import settings
            await ctx.defer(ephemeral=True)
            try:
                config = settings()
                if config.owner == owner:
                    await self.bot.get_cog('Media').sync_bridge(config)
            except (ValueError, OSError, TypeError) as exc:
                notice = f'No se pudo actualizar desde Playnite ({exc}). Se muestran los registros guardados.'
        rows=self.store.list(owner,guild,kind)
        if action in ('borrar','estado','unirme'):
            row=next((r for r in rows if r['id']==item_id),None)
            if not row: await ctx.send('ID no encontrado en este módulo.',ephemeral=True); return
            data=json.loads(row['data'])
            if shared and action!='unirme' and data['autor']!=ctx.author.id and not ctx.author.guild_permissions.manage_guild:
                await ctx.send('Solo el creador o un administrador puede modificarlo.',ephemeral=True); return
            if action=='borrar': self.store.delete(item_id,owner)
            else:
                if action=='unirme':
                    if not shared: await ctx.send('Usa unirme en reuniones o partidas.',ephemeral=True); return
                    data['participantes']=list(set(data.get('participantes',[])+[ctx.author.id]))
                else:
                    data['detalle']=detail[:1500]
                    if kind in ('cine','biblioteca','tareas'): data['estado']=detail.split('—')[0].strip().lower()
                self.store.update(item_id,owner,data)
            await ctx.send('Registro actualizado.',ephemeral=not shared); return
        if action=='buscar': rows=[r for r in rows if title.casefold() in (r['title']+r['data']).casefold()]
        elif action=='recomendar': rows=random.sample(rows,min(3,len(rows)))
        elif action!='ver': await ctx.send(HELP[kind],ephemeral=True); return
        if kind == 'biblioteca':
            if detail.strip():
                def platform(row):
                    data = json.loads(row['data'])
                    return str(data.get('source') or data.get('detalle') or '').casefold()
                rows = [row for row in rows if detail.strip().casefold() in platform(row)]
            lines = []
            for row in rows:
                data = json.loads(row['data'])
                source = data.get('source') or data.get('detalle') or 'Manual'
                lines.append(f"**#{row['id']} · {discord.utils.escape_markdown(row['title'])}** — {source}")
            if notice:
                lines.insert(0, notice)
            await self.panel(ctx, f'Biblioteca · {len(rows)} juegos', lines or ['Sin coincidencias. Para conectar Playnite ejecuta vincular_playnite.bat en el PC del bot. También puedes usar /importar_juegos con tu JSON.'],True)
            return
        await self.panel(ctx,kind.capitalize(),[f"**#{r['id']} · {discord.utils.escape_markdown(r['title'])}**\n{discord.utils.escape_markdown(json.loads(r['data']).get('detalle',''))}" + (f"\nParticipantes: {len(json.loads(r['data']).get('participantes',[]))}" if shared else '') for r in rows],not shared)

    @commands.hybrid_command(name='encuesta',description='Crear, consultar o cerrar una encuesta persistente.')
    @commands.guild_only()
    async def encuesta(self,ctx,accion:str='ayuda',pregunta:str='',opciones:str='',minutos:int=60,identificador:int=0):
        if accion=='crear':
            opts=[x.strip() for x in opciones.split('|') if x.strip()]
            if not pregunta or len(pregunta)>200 or not 2<=len(opts)<=10 or any(len(x)>100 for x in opts) or not 1<=minutos<=10080:
                await ctx.send('Pregunta: hasta 200 caracteres. Opciones: 2–10 separadas por | (100 caracteres cada una). Duración: 1–10080 minutos.'); return
            ident=self.store.add(ctx.author.id,ctx.guild.id,'encuesta',pregunta,{'options':opts,'ends':time.time()+60*minutos})
            await ctx.send(f'📊 Encuesta #{ident}: **{discord.utils.escape_markdown(pregunta)}**\n'+ '\n'.join(f'{i+1}. {o}' for i,o in enumerate(opts))+f'\nVota con /votar encuesta:{ident} opcion:1 · Cierre <t:{int(time.time()+60*minutos)}:R>'); return
        row=self.store.get(identificador)
        if accion not in ('resultados','cerrar') or not row or row['kind']!='encuesta' or row['guild']!=ctx.guild.id:
            await ctx.send('Usa /encuesta accion:crear pregunta:... opciones:A|B|C. Consulta con accion:resultados identificador:ID.'); return
        data=json.loads(row['data'])
        if accion=='cerrar':
            if ctx.author.id!=row['owner'] and not ctx.author.guild_permissions.manage_guild: await ctx.send('Solo el creador o un administrador puede cerrarla.'); return
            data['closed']=True
            self.store.update(row['id'],row['owner'],data)
        results=self.store.results(row['id'])
        await ctx.send(f"📊 {row['title']} · {'cerrada' if data.get('closed') or time.time()>=data['ends'] else 'abierta'}\n"+'\n'.join(f'{i+1}. {o}: {results.get(i+1,0)} votos' for i,o in enumerate(data['options'])))

    @commands.hybrid_command(name='votar',description='Vota o cambia tu voto en una encuesta.')
    @commands.guild_only()
    async def votar(self,ctx,encuesta:int,opcion:int):
        try: self.store.vote(encuesta,ctx.author.id,opcion,ctx.guild.id)
        except ValueError as exc: await ctx.send(str(exc),ephemeral=True)
        else: await ctx.send('Voto guardado.',ephemeral=True)

    @commands.hybrid_command(name='recordatorio',description='Aviso persistente en este canal dentro de N minutos.')
    async def recordatorio(self,ctx,minutos:int,texto:str,fecha:str=''):
        if not 1<=minutos<=525600 or not 1<=len(texto)<=1000:
            await ctx.send('Usa entre 1 y 525600 minutos y texto de hasta 1000 caracteres.',ephemeral=True); return
        due=time.time()+minutos*60
        if fecha:
            try:
                from zoneinfo import ZoneInfo
                date=dt.datetime.fromisoformat(fecha)
                if date.tzinfo is None:
                    configs=self.store.list(0,ctx.guild.id if ctx.guild else 0,'config')
                    zone=next((json.loads(r['data'])['value'] for r in configs if r['title']=='zona_horaria'),'America/Mexico_City')
                    date=date.replace(tzinfo=ZoneInfo(zone))
                due=date.timestamp()
                if due<=time.time(): raise ValueError()
            except (ValueError,KeyError):
                await ctx.send('Fecha inválida o pasada. Usa 2027-01-15T20:00:00-06:00.',ephemeral=True); return
        ident=self.store.remind(ctx.author.id,ctx.channel.id,texto,due)
        await ctx.send(f'⏰ Recordatorio #{ident} creado para <t:{int(due)}:F> en este canal.',ephemeral=True)

    @commands.hybrid_command(name='agenda',description='Consulta o cancela tus recordatorios.')
    async def agenda(self,ctx,cancelar:int=0):
        with self.store.connect() as db:
            if cancelar: db.execute('DELETE FROM emi_reminders WHERE id=? AND owner=?',(cancelar,ctx.author.id))
            rows=db.execute('SELECT * FROM emi_reminders WHERE owner=? AND sent=0 ORDER BY due',(ctx.author.id,)).fetchall()
        await self.panel(ctx,'Recordatorios',[f"#{r['id']} · <t:{int(r['due'])}:F> · {r['body']}"+(' · Falló el envío; vuelve a crearlo en un canal accesible.' if r['attempts']>=5 else '') for r in rows],True)

    @commands.hybrid_command(name='equipo',description='Reparte nombres en equipos aleatorios.')
    async def equipo(self,ctx,nombres:str,equipos:int=2):
        people=list(dict.fromkeys(x.strip() for x in nombres.split('|') if x.strip()))
        if not 2<=equipos<=len(people)<=40: await ctx.send('Separa 2–40 nombres con |; equipos entre 2 y el número de jugadores.'); return
        random.shuffle(people)
        await ctx.send('\n'.join(f"Equipo {i+1}: {', '.join(people[i::equipos])}" for i in range(equipos))[:1900])

    @commands.hybrid_command(name='steam',description='Importa biblioteca visible de Steam con SteamID64.')
    async def steam(self,ctx,steamid:str):
        key=os.getenv('STEAM_API_KEY')
        if not key: await ctx.send('Configura STEAM_API_KEY en .env. Mientras tanto usa /biblioteca agregar.',ephemeral=True); return
        if not steamid.isdigit() or len(steamid)!=17: await ctx.send('Indica tu SteamID64 de 17 dígitos.',ephemeral=True); return
        await ctx.defer(ephemeral=True)
        session=await self.bot.api.get_session()
        try:
            async with session.get('https://api.steampowered.com/IPlayerService/GetOwnedGames/v1/',params={'key':key,'steamid':steamid,'include_appinfo':1,'format':'json'}) as response:
                if response.status!=200: raise ValueError()
                data=await response.json()
        except Exception: await ctx.send('Steam no respondió correctamente. No se modificó tu biblioteca.'); return
        games=data.get('response',{}).get('games')
        if games is None: await ctx.send('Biblioteca no accesible. Comprueba la visibilidad de los detalles de juegos.'); return
        existing={json.loads(r['data']).get('appid'):r for r in self.store.list(ctx.author.id,0,'biblioteca')}
        for game in games:
            payload={'estado':'pendiente','source':'Steam','detalle':'Steam','appid':game['appid'],'minutos':game.get('playtime_forever',0),'autor':ctx.author.id}
            if game['appid'] in existing:
                row=existing[game['appid']]
                old=json.loads(row['data']); old.update({'minutos':payload['minutos']})
                self.store.update(row['id'],ctx.author.id,old)
            else: self.store.add(ctx.author.id,0,'biblioteca',game.get('name',str(game['appid'])),payload)
        await ctx.send(f'Sincronizados {len(games)} juegos visibles. /biblioteca accion:ver. No se eliminaron registros manuales.')

    @commands.hybrid_command(name='encomun',description='Comparte tus coincidencias con la biblioteca de otro usuario con su consentimiento.')
    @commands.guild_only()
    async def encomun(self,ctx,usuario:discord.Member):
        if usuario.bot: await ctx.send('Elige a una persona.'); return
        view=discord.ui.View(timeout=120)
        button=discord.ui.Button(label='Compartir coincidencias',style=discord.ButtonStyle.success)
        async def accept(i):
            if i.user.id!=usuario.id: await i.response.send_message('Solo la persona invitada puede aceptar.',ephemeral=True); return
            a={r['title'].casefold():r['title'] for r in self.store.list(ctx.author.id,0,'biblioteca')}
            b={r['title'].casefold() for r in self.store.list(usuario.id,0,'biblioteca')}
            common=[a[k] for k in a.keys() & b]
            button.disabled=True
            await i.response.edit_message(content='Juegos en común (verifica plataforma y juego cruzado):\n'+(', '.join(common)[:1700] or 'Ninguno registrado.'),view=view)
            view.stop()
        button.callback=accept; view.add_item(button)
        await ctx.send(f'{usuario.mention}, ¿compartes los juegos que coinciden con {ctx.author.display_name}?',view=view)

    @commands.hybrid_command(name='misiones',description='Misión diaria de victorias con recompensa única.')
    async def misiones(self,ctx,accion:str='ver'):
        user=self.bot.db.ensure_user(ctx.author.id)
        today=dt.datetime.now(dt.timezone.utc).date().isoformat()
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute("SELECT * FROM emi_items WHERE owner=? AND kind='mision' AND title=?",(ctx.author.id,today)).fetchone()
            if not row:
                data={'baseline':user['wins'],'claimed':False}
                db.execute('INSERT INTO emi_items(owner,guild,kind,title,data,created) VALUES(?,?,?,?,?,?)',(ctx.author.id,0,'mision',today,json.dumps(data),time.time()))
            else: data=json.loads(row['data'])
            progress=max(0,user['wins']-data['baseline'])
            message=f'Misión de hoy (UTC): gana 3 batallas. Progreso {min(3,progress)}/3. Premio: 150 monedas. Usa /misiones accion:reclamar.'
            if accion=='reclamar':
                if data['claimed']: message='Ya reclamaste esta misión.'
                elif progress<3: message='Aún faltan victorias para completar la misión.'
                else:
                    data['claimed']=True
                    db.execute("UPDATE emi_items SET data=? WHERE owner=? AND kind='mision' AND title=?",(json.dumps(data),ctx.author.id,today))
                    db.execute('UPDATE users SET coins=coins+150 WHERE user_id=?',(ctx.author.id,))
                    message='Misión completada: +150 monedas.'
        await ctx.send(message,ephemeral=True)

    @commands.hybrid_command(name='expedicion',description='Envía tu mazo y reclama una recompensa después de dos horas.')
    async def expedicion(self,ctx,accion:str='ver'):
        self.bot.db.ensure_user(ctx.author.id)
        deck=self.bot.db.get_user_deck(ctx.author.id)
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute("SELECT * FROM emi_items WHERE owner=? AND kind='expedicion' ORDER BY id DESC LIMIT 1",(ctx.author.id,)).fetchone()
            data=json.loads(row['data']) if row else None
            if accion=='enviar':
                if data and not data.get('claimed'): message='Ya tienes una expedición pendiente. Consulta /expedicion.'
                elif not deck: message='Consigue cartas y equipa un mazo primero.'
                else:
                    data={'end':time.time()+7200,'reward':100+25*len({c['element'] for c in deck}),'claimed':False,'cards':[c['card_id'] for c in deck]}
                    db.execute('INSERT INTO emi_items(owner,guild,kind,title,data,created) VALUES(?,?,?,?,?,?)',(ctx.author.id,0,'expedicion','Exploración',json.dumps(data),time.time()))
                    message=f"Expedición enviada. Regresa <t:{int(data['end'])}:R>. Tu mazo sigue disponible para jugar."
            elif accion=='reclamar':
                if not data or data.get('claimed'): message='No hay recompensa pendiente.'
                elif time.time()<data['end']: message='La expedición sigue en curso.'
                else:
                    data['claimed']=True
                    db.execute('UPDATE emi_items SET data=? WHERE id=?',(json.dumps(data),row['id']))
                    db.execute('UPDATE users SET coins=coins+? WHERE user_id=?',(data['reward'],ctx.author.id))
                    message=f"Expedición completada: +{data['reward']} monedas."
            else:
                message=f"Regresa <t:{int(data['end'])}:R>; recompensa {data['reward']} monedas." if data and not data.get('claimed') else 'Usa /expedicion accion:enviar. Dura dos horas y premia variedad elemental.'
        await ctx.send(message,ephemeral=True)

    @commands.hybrid_command(name='mazo',description='Guarda, lista y carga equipos de hasta tres cartas.')
    async def mazo(self,ctx,accion:str='ver',nombre:str='',cartas:str=''):
        rows=self.store.list(ctx.author.id,0,'mazo')
        if accion=='guardar':
            try: ids=[int(x.strip()) for x in cartas.split(',')]
            except ValueError: await ctx.send('Separa los IDs con comas.',ephemeral=True); return
            if not nombre or not 1<=len(ids)<=3 or len(set(ids))!=len(ids): await ctx.send('Indica nombre y 1–3 cartas distintas.',ephemeral=True); return
            if any(not (c:=self.bot.db.get_card(i)) or c['owner_id']!=ctx.author.id for i in ids): await ctx.send('Todas las cartas deben pertenecerte.',ephemeral=True); return
            old=next((r for r in rows if r['title']==nombre),None)
            if old: self.store.update(old['id'],ctx.author.id,{'ids':ids})
            else: self.store.add(ctx.author.id,0,'mazo',nombre,{'ids':ids})
            await ctx.send('Mazo guardado.',ephemeral=True)
        elif accion=='cargar':
            row=next((r for r in rows if r['title']==nombre),None)
            if not row: await ctx.send('No existe ese mazo.',ephemeral=True); return
            ok,msg=self.bot.db.set_user_deck(ctx.author.id,json.loads(row['data'])['ids'])
            await ctx.send(msg,ephemeral=True)
        else: await self.panel(ctx,'Mazos guardados',[f"{r['title']}: {json.loads(r['data'])['ids']}" for r in rows],True)

    @commands.hybrid_command(name='album',description='Consulta tu colección agrupada por anime.')
    async def album(self,ctx):
        counts={}
        for card in self.bot.db.get_user_cards(ctx.author.id): counts[card['anime']]=counts.get(card['anime'],0)+1
        await self.panel(ctx,'Álbum de cartas',[f'{name}: {count} cartas' for name,count in sorted(counts.items())],True)

    @commands.hybrid_command(name='bloquear',description='Protege una carta frente a venta e intercambio; repetir desbloquea.')
    async def bloquear(self,ctx,carta:int):
        card=self.bot.db.get_card(carta)
        if not card or card['owner_id']!=ctx.author.id: await ctx.send('Esa carta no te pertenece.',ephemeral=True); return
        with self.store.connect() as db:
            if db.execute('SELECT 1 FROM emi_market WHERE card=? AND active=1',(carta,)).fetchone():
                await ctx.send('Retira el anuncio del mercado antes de desbloquear.',ephemeral=True); return
            row=db.execute('SELECT 1 FROM emi_protected WHERE card=?',(carta,)).fetchone()
            if row: db.execute('DELETE FROM emi_protected WHERE card=?',(carta,))
            else: db.execute('INSERT INTO emi_protected VALUES(?)',(carta,))
        await ctx.send('Carta desbloqueada.' if row else 'Carta protegida.',ephemeral=True)

    @commands.hybrid_command(name='probabilidades',description='Consulta las probabilidades de rareza del gacha.')
    async def probabilidades(self,ctx):
        import importlib
        module=importlib.import_module(self.bot.__class__.__module__)
        config=module.RARITY_CONFIG
        total=sum(x['weight'] for x in config.values())
        text='Base: '+', '.join(f"{k}: {v['weight']/total*100:.1f}%" for k,v in config.items())
        text+='\nMás de 80,000 favoritos: N 8%, R 18%, SR 32%, SSR 27%, UR 15%.\nEntre 30,001 y 80,000: N 5%, R 14%, SR 28%, SSR 33%, UR 20%.\nLos sobres SR+/SSR+ elevan resultados inferiores al mínimo. No hay garantía acumulativa por número de tiradas.'
        await ctx.send(text,ephemeral=True)

    @commands.hybrid_command(name='configurar',description='Configura la zona horaria y el rol DJ del servidor.')
    @commands.guild_only()
    @commands.has_guild_permissions(manage_guild=True)
    async def configurar(self,ctx,clave:str='ver',valor:str=''):
        rows=self.store.list(0,ctx.guild.id,'config')
        if clave=='ver':
            await self.panel(ctx,'Configuración',[f"{r['title']}: {json.loads(r['data']).get('value')}" for r in rows]+['Claves: zona_horaria (p. ej. America/Mexico_City), rol_dj (ID del rol).'],True); return
        if clave not in ('zona_horaria','rol_dj'): await ctx.send('Clave no válida.',ephemeral=True); return
        if clave=='zona_horaria':
            from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
            try: ZoneInfo(valor)
            except ZoneInfoNotFoundError: await ctx.send('Zona no reconocida. Instala tzdata en Windows.',ephemeral=True); return
        elif not valor.isdigit() or not ctx.guild.get_role(int(valor)):
            await ctx.send('Indica el ID de un rol del servidor.',ephemeral=True); return
        row=next((r for r in rows if r['title']==clave),None)
        if row: self.store.update(row['id'],0,{'value':valor})
        else: self.store.add(0,ctx.guild.id,'config',clave,{'value':valor})
        await ctx.send('Configuración guardada.',ephemeral=True)

    @commands.hybrid_command(name='ahora',description='Muestra el audio actual; no controla videos del navegador.')
    @commands.guild_only()
    async def ahora(self,ctx):
        track=self.bot.get_music_queue(ctx.guild.id).current
        await ctx.send(f"🎵 {track['title']}\n/pausa · /reanudar · /saltar · /salir" if track else 'No hay audio reproduciéndose.')

    @commands.hybrid_command(name='mezclar',description='Mezcla la cola de audio.')
    @commands.guild_only()
    async def mezclar(self,ctx):
        if not same_voice(ctx): await ctx.send('Debes estar en el mismo canal de voz.'); return
        random.shuffle(self.bot.get_music_queue(ctx.guild.id).queue)
        from emi_audio import persist
        persist(self.bot,ctx.guild.id)
        await ctx.send('Cola mezclada.')

    @commands.hybrid_command(name='quitar',description='Quita una pista pendiente de la cola.')
    @commands.guild_only()
    async def quitar(self,ctx,posicion:int):
        if not same_voice(ctx): await ctx.send('Debes estar en el mismo canal de voz.'); return
        queue=self.bot.get_music_queue(ctx.guild.id).queue
        if not 1<=posicion<=len(queue): await ctx.send('Posición fuera de rango.'); return
        queue.pop(posicion-1)
        from emi_audio import persist
        persist(self.bot,ctx.guild.id)
        await ctx.send('Pista retirada.')

def same_voice(ctx):
    return ctx.guild and ctx.voice_client and getattr(ctx.author,'voice',None) and ctx.author.voice.channel==ctx.voice_client.channel

def youtube_url(url):
    parsed=urlparse(url)
    return parsed.scheme=='https' and parsed.hostname in ('youtube.com','www.youtube.com','m.youtube.com','youtu.be') and not parsed.username

async def setup(bot):
    bot.emi_purchase_lock=asyncio.Lock()
    cog=Emi(bot)
    await bot.add_cog(cog)
    bot.emi=cog
    for kind in HELP:
        def factory(k):
            async def callback(ctx,accion:str=('ver' if k=='biblioteca' else 'ayuda'),titulo:str='',detalle:str='',identificador:int=0):
                await cog.records(ctx,k,accion,titulo,detalle,identificador)
            callback.__name__='emi_'+k
            return callback
        bot.add_command(commands.hybrid_command(name=kind,description=HELP[kind][:95])(factory(kind)))
    @bot.check
    async def guards(ctx):
        voice={'play','cola','saltar','pausa','reanudar','salir'}
        if ctx.command.name in voice:
            if not ctx.guild: raise commands.CheckFailure('Este comando necesita un servidor.')
            if ctx.command.name!='cola' and ctx.voice_client and not same_voice(ctx):
                raise commands.CheckFailure('Únete al mismo canal de voz que EmiNeko.')
        if ctx.guild and ctx.command.name in ('saltar','pausa','reanudar','salir','mezclar','quitar','audio'):
            configs=cog.store.list(0,ctx.guild.id,'config')
            dj=next((json.loads(r['data'])['value'] for r in configs if r['title']=='rol_dj'),None)
            if dj and not ctx.author.guild_permissions.manage_guild and int(dj) not in [r.id for r in ctx.author.roles]:
                raise commands.CheckFailure('Este control requiere el rol DJ configurado.')
        if ctx.command.name in ('trivia','batalla'):
            seconds={'raid':3600,'trivia':60,'batalla':30}[ctx.command.name]
            wait=cog.store.acquire(ctx.author.id,ctx.command.name,seconds)
            if wait: raise commands.CheckFailure(f'Espera {wait} segundos antes de repetir este comando.')
        return True
    async def errors(ctx,error):
        if getattr(ctx, 'emi_handled', False): return
        if isinstance(error,commands.CommandNotFound): return
        if isinstance(error,(commands.UserInputError,commands.CheckFailure)):
            await ctx.send(f'⚠️ {error}\nUsa /inicio para ver la guía.',ephemeral=True)
        else:
            import logging
            logging.getLogger('EmiNeko').error('Error en comando %s',ctx.command,exc_info=(type(error),error,error.__traceback__))
            await ctx.send('No pude completar la operación. Consulta /estado o vuelve a intentarlo.',ephemeral=True)
    bot.add_listener(errors,'on_command_error')
