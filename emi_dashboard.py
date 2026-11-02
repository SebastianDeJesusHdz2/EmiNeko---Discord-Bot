"""Panel navegable y ayudas con ejemplos reales."""
import discord
from discord.ext import commands

SECTIONS={
 'inicio':('🐾 EmiNeko','Elige una categoría para ver qué puedes hacer. Los módulos personales usan respuestas privadas.\nConfigura conexiones con PASO_A_PASO.md. /estado muestra lo que está activo.'),
 'cartas':('🎴 Cartas y progreso','/tienda → compra con botones\n/coleccion · /carta · /equipar · /mazo · /bloquear · /favorita\n/misiones · /expedicion · /album_anime · /logros · /cosmeticos\n/raid accion:atacar → jefe del servidor\n/arena → clasificación mensual · /mercado → cartas de otros jugadores'),
 'juegos':('🎮 Tu biblioteca','/steam steamid:TU_ID → importar biblioteca visible\n/importar_juegos archivo:JSON → Playnite, GOG, Xbox\n/quejuego plataforma:Steam estado:pendiente\n/encomun usuario:@amigo → con aceptación\n/equipo · /torneo · /partida · /evento'),
 'comunidad':('🗓️ Comunidad','/encuesta accion:crear pregunta:Qué jugamos opciones:A|B\n/votar encuesta:ID opcion:1\n/disponibilidad accion:crear horarios:Viernes 20h|Sábado 18h\n/evento accion:crear titulo:Partida fecha:2027-01-15T20:00:00-06:00\n/recordatorio · /recurrente · /agenda · /tareas\n/sesion → memoria de texto con consentimiento · /resumen'),
 'musica':('🎧 Audio y video','/play → audio en tu canal de voz\n/audio → botones de pausa/reanudar/saltar\n/audio accion:volumen valor:50\n/audio accion:repetir valor:cola\n/audio accion:ir valor:90\n/sala accion:crear url:URL_YOUTUBE → video en navegador'),
 'cine':('🎬 Cine y series','/buscar_cine busqueda:TITULO tipo:pelicula\n/buscar_cine guardar:ID tipo:pelicula\n/dondever identificador:ID pais:MX\n/cine accion:estado identificador:ID detalle:visto\n/quevemos → elige pendientes\n/alertas → precios y cambios de estreno'),
 'foto':('📷 Fotografía','/foto accion:guardar archivo:FOTO titulo:Retrato\n/foto accion:exif archivo:FOTO\n/foto accion:comparar identificador:ID otra:ID\n/fotografia → equipo, proyectos y retos\n/concurso → convocatoria y votación fotográfica'),
 'memoria':('🧠 Memoria y privacidad','/memoria accion:agregar titulo:Gustos detalle:Cooperativos\n/preguntar pregunta:cooperativos → buscar en tus registros\n/datos → exportar o borrar tu memoria\n/privacidad → alcance y controles\n/configurar · /estado · /creditos')}

class Dashboard(discord.ui.View):
    def __init__(self,user):
        super().__init__(timeout=300); self.user=user
        select=discord.ui.Select(placeholder='¿Qué quieres hacer?',options=[discord.SelectOption(label=value[0],value=key) for key,value in SECTIONS.items()])
        async def choose(i):
            if i.user.id!=self.user: await i.response.send_message('Abre tu propio /inicio.',ephemeral=True); return
            title,text=SECTIONS[select.values[0]]
            await i.response.edit_message(embed=discord.Embed(title=title,description=text,color=0xD98EBB),view=self)
        select.callback=choose; self.add_item(select)

class Extras(commands.Cog):
    def __init__(self,bot): self.bot=bot
    @commands.hybrid_command(name='favorita',description='Destaca una carta de tu colección en tu perfil.')
    async def favorita(self,ctx,carta:int):
        card=self.bot.db.get_card(carta)
        if not card or card['owner_id']!=ctx.author.id: await ctx.send('Esa carta no te pertenece.',ephemeral=True); return
        store=self.bot.emi.store
        with store.connect() as db:
            db.execute("DELETE FROM emi_items WHERE owner=? AND kind='favorita'",(ctx.author.id,))
        store.add(ctx.author.id,0,'favorita',card['name'],{'card':carta})
        await ctx.send('Carta favorita actualizada.',ephemeral=True)
    @commands.hybrid_command(name='album_anime',description='Consulta personajes faltantes de un anime según el catálogo de Jikan.')
    async def album_anime(self,ctx,anime_id:int):
        await ctx.defer(ephemeral=True)
        data=await self.bot.api.fetch_json(f'https://api.jikan.moe/v4/anime/{anime_id}/characters')
        if not data or not data.get('data'): await ctx.send('No se pudo obtener el catálogo de personajes.',ephemeral=True); return
        owned={c['mal_char_id'] for c in self.bot.db.get_user_cards(ctx.author.id)}
        entries={r['character']['mal_id']:r['character']['name'] for r in data['data']}
        lines=[('✅ ' if ident in owned else '⬜ ')+name for ident,name in entries.items()]
        if entries.keys()<=owned:
            with self.bot.emi.store.connect() as db:
                if db.execute('INSERT OR IGNORE INTO emi_badges VALUES(?,?)',(ctx.author.id,f'album:{anime_id}')).rowcount:
                    db.execute('UPDATE users SET crystals=crystals+50 WHERE user_id=?',(ctx.author.id,))
            lines.insert(0,'Álbum completo según el catálogo actual: insignia y 50 cristales una sola vez.')
        await self.bot.emi.panel(ctx,f'Álbum MAL #{anime_id} · {len(entries.keys() & owned)}/{len(entries)}',lines,True)
    @commands.hybrid_command(name='concurso',description='Concurso fotográfico con plazo, participantes y votos persistentes.')
    @commands.guild_only()
    async def concurso(self,ctx,accion:str='ver',titulo:str='',horas:int=24,identificador:int=0,foto:int=0):
        import json,time
        store=self.bot.emi.store
        if accion=='crear':
            if not titulo or not 1<=horas<=720: await ctx.send('Título y plazo de 1–720 horas.'); return
            ident=store.add(ctx.author.id,ctx.guild.id,'concurso',titulo[:180],{'ends':time.time()+horas*3600,'entries':{},'votes':{},'closed':False})
            await ctx.send(f'Concurso #{ident}: {titulo[:180]}. Inscribe una foto privada con /concurso accion:participar identificador:{ident} foto:ID. Esto comparte la foto con el servidor.'); return
        with store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute("SELECT * FROM emi_items WHERE id=? AND guild=? AND kind='concurso'",(identificador,ctx.guild.id)).fetchone()
            if not row: await ctx.send('Concurso no encontrado.'); return
            data=json.loads(row['data'])
            if accion in ('participar','votar') and (data['closed'] or time.time()>=data['ends']): await ctx.send('Concurso cerrado.'); return
            if accion=='participar':
                image=db.execute('SELECT * FROM emi_photos WHERE id=? AND owner=?',(foto,ctx.author.id)).fetchone()
                if not image: await ctx.send('Esa foto no te pertenece.'); return
                data['entries'][str(ctx.author.id)]=foto
            elif accion=='votar':
                if foto not in data['entries'].values(): await ctx.send('Foto no inscrita.'); return
                data['votes'][str(ctx.author.id)]=foto
            elif accion=='cerrar':
                if row['owner']!=ctx.author.id and not ctx.author.guild_permissions.manage_guild: await ctx.send('Solo el organizador puede cerrar.'); return
                data['closed']=True
            db.execute('UPDATE emi_items SET data=? WHERE id=?',(__import__('json').dumps(data),identificador))
            images=[dict(r) for r in db.execute('SELECT * FROM emi_photos WHERE id IN ('+(','.join('?' for _ in data['entries']) or 'NULL')+')',tuple(data['entries'].values()))]
        if accion=='abrir':
            from emi_media import DATA
            image=next((r for r in images if r['id']==foto),None)
            if not image: await ctx.send('Foto no disponible.'); return
            await ctx.send(file=discord.File(DATA/'photos'/image['filename'],filename=f'concurso-{foto}.jpg')); return
        counts={r['id']:sum(v==r['id'] for v in data['votes'].values()) for r in images}
        lines=[f"Foto #{r['id']} · {r['title']} · {counts[r['id']]} votos" for r in sorted(images,key=lambda r:counts[r['id']],reverse=True)]
        await self.bot.emi.panel(ctx,f"{row['title']} · {'cerrado' if data['closed'] or time.time()>=data['ends'] else 'abierto'}",lines)
async def setup(bot): await bot.add_cog(Extras(bot))
