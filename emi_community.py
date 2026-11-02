"""Comandos de comunidad, progreso y administración."""
import asyncio
import datetime as dt
import io
import json
import os
import random
import time
from pathlib import Path
from zoneinfo import ZoneInfo
import discord
from discord.ext import commands
from emi_domain import Domain

COSMETICS={'sakura':('🌸 Guardiana Sakura',150), 'neko':('🐾 Compañero Neko',75), 'luna':('🌙 Viajero Lunar',100)}

class Confirm(discord.ui.View):
    def __init__(self,user,callback):
        super().__init__(timeout=90); self.user=user; self.callback=callback; self.used=False
    @discord.ui.button(label='Confirmar',style=discord.ButtonStyle.success)
    async def accept(self,i,b):
        if i.user.id!=self.user: await i.response.send_message('No es tu confirmación.',ephemeral=True); return
        if self.used: await i.response.send_message('Ya fue procesada.',ephemeral=True); return
        self.used=True; b.disabled=True
        await i.response.defer(ephemeral=True)
        try: result=await self.callback()
        except ValueError as exc: result=str(exc)
        await i.edit_original_response(view=self)
        await i.followup.send(result[:1900],ephemeral=True)
        self.stop()

class Community(commands.Cog):
    def __init__(self,bot): self.bot=bot; self.store=Domain(bot.db.db_path)
    async def cog_command_error(self,ctx,error):
        original=getattr(error,'original',error)
        if isinstance(original,ValueError):
            ctx.emi_handled=True
            await ctx.send(str(original)[:1900],ephemeral=True)
    def timestamp(self,ctx,value):
        parsed=dt.datetime.fromisoformat(value)
        if not parsed.tzinfo:
            configs=self.store.list(0,ctx.guild.id,'config')
            zone=next((json.loads(r['data'])['value'] for r in configs if r['title']=='zona_horaria'),'America/Mexico_City')
            parsed=parsed.replace(tzinfo=ZoneInfo(zone))
        return parsed.timestamp()

    @commands.hybrid_command(name='evento',description='Reunión, partida o cineclub con plazas, lista de espera y recordatorio.')
    @commands.guild_only()
    async def evento(self,ctx,accion:str='ver',titulo:str='',fecha:str='',plazas:int=8,detalle:str='',identificador:int=0):
        if accion=='crear':
            try: due=self.timestamp(ctx,fecha)
            except (ValueError,KeyError): raise ValueError('Usa fecha ISO: 2027-01-15T20:00:00-06:00.')
            ident=self.store.event(ctx.guild.id,ctx.author.id,ctx.channel.id,titulo,detalle,due,plazas)
            await ctx.send(f'Evento #{ident} creado. Aviso 10 minutos antes. /evento accion:unirme identificador:{ident}'); return
        if accion in ('unirme','salir'):
            await ctx.send(self.store.join_event(identificador,ctx.author.id,ctx.guild.id,accion=='salir'),ephemeral=True); return
        with self.store.connect() as db:
            if accion in ('cancelar','acuerdos'):
                row=db.execute('SELECT * FROM emi_events WHERE id=? AND guild=?',(identificador,ctx.guild.id)).fetchone()
                if not row or (row['owner']!=ctx.author.id and not ctx.author.guild_permissions.manage_guild): raise ValueError('Solo el organizador o administrador puede modificarlo.')
                if accion=='cancelar':
                    db.execute('UPDATE emi_events SET closed=1 WHERE id=?',(identificador,))
                    db.execute('DELETE FROM emi_reminders WHERE body=? AND channel=?',(f"Evento #{identificador}: {row['title']}",row['channel']))
                else: db.execute('UPDATE emi_events SET body=? WHERE id=?',(detalle[:1500],identificador))
            rows=db.execute('SELECT * FROM emi_events WHERE guild=? AND closed=0 ORDER BY due',(ctx.guild.id,)).fetchall()
            lines=[]
            for row in rows:
                attendees=[f'<@{x[0]}>' for x in db.execute('SELECT user FROM emi_attendees WHERE event=? ORDER BY joined,user',(row['id'],))]
                lines.append(f"**#{row['id']} {row['title']}** · <t:{int(row['due'])}:F>\n{row['body']}\nPlazas: {', '.join(attendees[:row['slots']])} · Espera: {max(0,len(attendees)-row['slots'])}")
        await self.bot.emi.panel(ctx,'Eventos',lines or ['Crear: /evento accion:crear titulo:... fecha:... plazas:8'])

    @commands.hybrid_command(name='disponibilidad',description='Vota varios horarios; resultados persistentes.')
    @commands.guild_only()
    async def disponibilidad(self,ctx,accion:str='ver',horarios:str='',identificador:int=0,opciones:str=''):
        if accion=='crear':
            values=[v.strip() for v in horarios.split('|') if v.strip()]
            if not 2<=len(values)<=15 or any(len(v)>80 for v in values): raise ValueError('Indica 2–15 horarios separados por |, hasta 80 caracteres cada uno.')
            ident=self.store.add(ctx.author.id,ctx.guild.id,'horarios','Disponibilidad',{'options':values,'votes':{}})
            await ctx.send(f'Consulta #{ident}. /disponibilidad accion:votar identificador:{ident} opciones:1,3'); return
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute("SELECT * FROM emi_items WHERE id=? AND guild=? AND kind='horarios'",(identificador,ctx.guild.id)).fetchone()
            if not row: raise ValueError('Crea o indica un ID de disponibilidad.')
            data=json.loads(row['data'])
            if accion=='votar':
                selected=sorted({int(x) for x in opciones.split(',')})
                if any(x<1 or x>len(data['options']) for x in selected): raise ValueError('Opción fuera de rango.')
                data['votes'][str(ctx.author.id)]=selected
                db.execute('UPDATE emi_items SET data=? WHERE id=?',(json.dumps(data),identificador))
        await ctx.send('\n'.join(f"{i}. {label}: {sum(i in v for v in data['votes'].values())} disponibles" for i,label in enumerate(data['options'],1)))

    @commands.hybrid_command(name='recurrente',description='Crea un recordatorio periódico en este canal.')
    @commands.guild_only()
    async def recurrente(self,ctx,texto:str,horas:int=24):
        if not 1<=horas<=8760 or not 1<=len(texto)<=1000: raise ValueError('Intervalo de 1–8760 horas; texto hasta 1000 caracteres.')
        ident=self.store.remind(ctx.author.id,ctx.channel.id,texto,time.time()+horas*3600)
        with self.store.connect() as db: db.execute('UPDATE emi_reminders SET repeat_seconds=? WHERE id=?',(horas*3600,ident))
        await ctx.send(f'Recurrente #{ident}: cada {horas} horas. /agenda cancelar:{ident} para detenerlo.',ephemeral=True)

    @commands.hybrid_command(name='mercado',description='Compra y vende cartas con intercambio atómico y confirmación.')
    async def mercado(self,ctx,accion:str='ver',carta:int=0,precio:int=0,identificador:int=0):
        self.bot.db.ensure_user(ctx.author.id)
        if accion=='vender':
            ident=self.store.list_card(ctx.author.id,carta,precio)
            await ctx.send(f'Anuncio #{ident} publicado por {precio} monedas. Carta bloqueada hasta venta o cancelación.'); return
        if accion=='cancelar':
            self.store.buy_card(ctx.author.id,identificador,cancel=True); await ctx.send('Anuncio cancelado.'); return
        if accion=='comprar':
            with self.store.connect() as db: row=db.execute('SELECT m.*,c.name FROM emi_market m JOIN cards c ON m.card=c.card_id WHERE m.id=? AND active=1',(identificador,)).fetchone()
            if not row: raise ValueError('Anuncio no disponible.')
            async def buy():
                self.store.buy_card(ctx.author.id,identificador)
                return 'Compra completada; carta transferida y pago registrado.'
            await ctx.send(f"¿Comprar {row['name']} por {row['price']} monedas?",view=Confirm(ctx.author.id,buy),ephemeral=True); return
        with self.store.connect() as db: rows=db.execute('SELECT m.*,c.name,c.rarity FROM emi_market m JOIN cards c ON m.card=c.card_id WHERE active=1 ORDER BY m.id DESC LIMIT 200').fetchall()
        await self.bot.emi.panel(ctx,'Mercado',[f"#{r['id']} · [{r['rarity']}] {r['name']} · {r['price']} monedas" for r in rows])

    @commands.hybrid_command(name='raid',description='Jefe cooperativo diario por servidor con tres fases y premios colectivos.')
    @commands.guild_only()
    async def raid(self,ctx,accion:str='ver'):
        if accion not in ('ver','atacar','reclamar'): raise ValueError('Acciones: ver, atacar, reclamar.')
        self.bot.db.ensure_user(ctx.author.id)
        deck=self.bot.db.get_user_deck(ctx.author.id)
        power=sum(c['atk']*2+c['spd'] for c in deck)
        await ctx.send(self.store.raid(ctx.guild.id,ctx.author.id,accion,power))

    @commands.hybrid_command(name='arena',description='Duelo automático con niveles normalizados y clasificación mensual.')
    @commands.guild_only()
    async def arena(self,ctx,oponente:discord.Member=None):
        season=dt.datetime.now(dt.timezone.utc).strftime('%Y-%m')
        if not oponente:
            with self.store.connect() as db: rows=db.execute('SELECT * FROM emi_arena WHERE season=? ORDER BY rating DESC LIMIT 20',(season,)).fetchall()
            await self.bot.emi.panel(ctx,'Arena '+season,[f"<@{r['user']}> · {r['rating']} puntos · {r['wins']}V/{r['losses']}D" for r in rows]); return
        if oponente.bot or oponente.id==ctx.author.id: raise ValueError('Elige a otra persona.')
        decks=[self.bot.db.get_user_deck(u) for u in (ctx.author.id,oponente.id)]
        if any(len(d)!=3 for d in decks): raise ValueError('Ambos necesitan un mazo de tres cartas.')
        async def battle():
            pair='arena:'+':'.join(map(str,sorted((ctx.author.id,oponente.id))))
            if self.store.acquire(0,pair,3600): raise ValueError('Esta pareja puede disputar un duelo de arena por hora.')
            # Every card has identical base stats; elemental matchups and turn rolls decide results.
            module=__import__(self.bot.__class__.__module__)
            points=[0,0]
            for a,b in zip(*decks):
                av=module.has_elemental_advantage(a['element'],b['element'])
                bv=module.has_elemental_advantage(b['element'],a['element'])
                points[0 if random.random()<(.65 if av else .35 if bv else .5) else 1]+=1
            winner,loser=(ctx.author.id,oponente.id) if points[0]>points[1] else (oponente.id,ctx.author.id)
            delta=self.store.arena_result(winner,loser)
            return f'Arena normalizada: {points[0]}–{points[1]}. Ganador <@{winner}> (+{delta}). Resultado guardado en temporada {season}.'
        await ctx.send(f'{oponente.display_name}, confirma el duelo de arena de {ctx.author.display_name}.',view=Confirm(oponente.id,battle))

    @commands.hybrid_command(name='torneo',description='Cuadro de eliminación directa persistente.')
    @commands.guild_only()
    async def torneo(self,ctx,accion:str='ver',titulo:str='',participantes:str='',identificador:int=0,partida:int=0,ganador:str=''):
        if accion=='crear':
            people=[x.strip()[:80] for x in participantes.split('|') if x.strip()]
            ident=self.store.tournament(ctx.guild.id,ctx.author.id,titulo[:180] or 'Torneo',people)
            await ctx.send(f'Torneo #{ident}. Consulta /torneo identificador:{ident}'); return
        if accion=='resultado': self.store.tournament_win(identificador,ctx.guild.id,ctx.author.id,partida,ganador,ctx.author.guild_permissions.manage_guild)
        with self.store.connect() as db: row=db.execute('SELECT * FROM emi_tournaments WHERE id=? AND guild=?',(identificador,ctx.guild.id)).fetchone()
        if not row: raise ValueError('Indica un torneo o créalo con accion:crear participantes:Ana|Luis|Eva.')
        data=json.loads(row['data'])
        lines=[f"Campeón: {data['champion']}"] if data['champion'] else [f"{i+1}. {a} vs {b or 'pase libre'} · Ganador: {data['winners'].get(str(i),'pendiente')}" for i,(a,b) in enumerate(data['matches'])]
        await self.bot.emi.panel(ctx,f"{row['title']} · ronda {data['round']}",lines)

    @commands.hybrid_command(name='logros',description='Insignias automáticas y recompensas únicas en cristales.')
    async def logros(self,ctx):
        user=self.bot.db.ensure_user(ctx.author.id); cards=self.bot.db.get_user_cards(ctx.author.id)
        goals={'coleccionista':len(cards)>=10,'veterano':user['wins']>=10,'constante':user['daily_streak']>=7,'leyenda':any(c['rarity']=='UR' for c in cards)}
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            for code,done in goals.items():
                if done and db.execute('INSERT OR IGNORE INTO emi_badges VALUES(?,?)',(ctx.author.id,code)).rowcount:
                    db.execute('UPDATE users SET crystals=crystals+25 WHERE user_id=?',(ctx.author.id,))
            badges=[r[0] for r in db.execute('SELECT code FROM emi_badges WHERE user=?',(ctx.author.id,))]
        await ctx.send('Insignias: '+(', '.join(badges) or 'ninguna')+'\nCada nueva insignia da 25 cristales. Objetivos: 10 cartas, 10 victorias, racha de 7, una UR.',ephemeral=True)

    @commands.hybrid_command(name='cosmeticos',description='Compra y equipa títulos de perfil con cristales.')
    async def cosmeticos(self,ctx,accion:str='ver',codigo:str=''):
        self.bot.db.ensure_user(ctx.author.id)
        if accion in ('comprar','equipar'):
            if codigo not in COSMETICS: raise ValueError('Código no válido.')
            with self.store.connect() as db:
                db.execute('BEGIN IMMEDIATE')
                owned=db.execute('SELECT 1 FROM emi_cosmetics WHERE user=? AND code=?',(ctx.author.id,codigo)).fetchone()
                if accion=='comprar' and not owned:
                    cost=COSMETICS[codigo][1]
                    if not db.execute('UPDATE users SET crystals=crystals-? WHERE user_id=? AND crystals>=?',(cost,ctx.author.id,cost)).rowcount: raise ValueError('Cristales insuficientes.')
                    db.execute('INSERT INTO emi_cosmetics VALUES(?,?,0)',(ctx.author.id,codigo))
                elif not owned: raise ValueError('Compra el título primero.')
                if accion=='equipar':
                    db.execute('UPDATE emi_cosmetics SET equipped=0 WHERE user=?',(ctx.author.id,))
                    db.execute('UPDATE emi_cosmetics SET equipped=1 WHERE user=? AND code=?',(ctx.author.id,codigo))
        await ctx.send('\n'.join(f'{code}: {name} · {cost} cristales' for code,(name,cost) in COSMETICS.items())+'\nUsa accion:comprar o equipar con el código.',ephemeral=True)

    @commands.hybrid_command(name='historial',description='Consulta compras del mercado y premios colectivos.')
    async def historial(self,ctx):
        if not ctx.interaction: raise ValueError('Usa /historial para consultar en privado.')
        with self.store.connect() as db: rows=db.execute('SELECT * FROM emi_ledger WHERE user=? ORDER BY id DESC LIMIT 100',(ctx.author.id,)).fetchall()
        await self.bot.emi.panel(ctx,'Movimientos',[f"<t:{int(r['created'])}:f> · {r['amount']:+} · {r['reason']}" for r in rows],True)

    @commands.hybrid_command(name='sesion',description='Memoria de reuniones por texto, solo de participantes que aceptan.')
    @commands.guild_only()
    async def sesion(self,ctx,accion:str='ver',titulo:str='',identificador:int=0):
        with self.store.connect() as db:
            if accion=='crear':
                if db.execute('SELECT 1 FROM emi_sessions WHERE channel=? AND ended=0',(ctx.channel.id,)).fetchone(): raise ValueError('Ya hay una sesión abierta en este canal.')
                ident=db.execute('INSERT INTO emi_sessions(guild,owner,channel,title,started) VALUES(?,?,?,?,?)',(ctx.guild.id,ctx.author.id,ctx.channel.id,titulo[:180] or 'Reunión',time.time())).lastrowid
                db.commit()
                await ctx.send(f'Sesión #{ident} abierta. No se guarda ningún mensaje hasta que cada participante use /sesion accion:aceptar identificador:{ident}. Se conserva texto. Los participantes autorizados pueden consultar un resumen local de los mensajes. Usa /sesion accion:retirar para eliminar tus aportaciones.'); return
            row=db.execute('SELECT * FROM emi_sessions WHERE id=? AND guild=? AND channel=?',(identificador,ctx.guild.id,ctx.channel.id)).fetchone()
            if not row: raise ValueError('Indica el ID de una sesión de este canal.')
            if accion=='aceptar':
                if row['ended']: raise ValueError('Sesión cerrada.')
                db.execute('INSERT OR IGNORE INTO emi_consent VALUES(?,?)',(identificador,ctx.author.id))
            elif accion=='retirar':
                db.execute('DELETE FROM emi_consent WHERE session=? AND user=?',(identificador,ctx.author.id))
                db.execute('DELETE FROM emi_messages WHERE session=? AND user=?',(identificador,ctx.author.id))
            elif accion=='cerrar':
                if row['owner']!=ctx.author.id and not ctx.author.guild_permissions.manage_guild: raise ValueError('Solo el organizador o administrador puede cerrar.')
                db.execute('UPDATE emi_sessions SET ended=? WHERE id=?',(time.time(),identificador))
            count=db.execute('SELECT COUNT(*) FROM emi_consent WHERE session=?',(identificador,)).fetchone()[0]
        await ctx.send(f'Sesión #{identificador}: {accion} procesado. Participantes que aceptaron: {count}. /resumen sesion:{identificador} requiere consentimiento vigente.',ephemeral=True)

    @commands.Cog.listener()
    async def on_message(self,message):
        if message.author.bot or not message.guild or not message.content: return
        if message.content.startswith(('!',self.bot.command_prefix if isinstance(self.bot.command_prefix,str) else '!')): return
        with self.store.connect() as db:
            row=db.execute('SELECT s.id FROM emi_sessions s JOIN emi_consent c ON c.session=s.id WHERE s.channel=? AND s.ended=0 AND c.user=?',(message.channel.id,message.author.id)).fetchone()
            if row: db.execute('INSERT OR IGNORE INTO emi_messages VALUES(?,?,?,?,?)',(row['id'],message.id,message.author.id,message.content[:4000],time.time()))
    @commands.Cog.listener()
    async def on_raw_message_delete(self,payload):
        with self.store.connect() as db: db.execute('DELETE FROM emi_messages WHERE message=?',(payload.message_id,))
    @commands.Cog.listener()
    async def on_raw_message_edit(self,payload):
        if 'content' in payload.data:
            with self.store.connect() as db: db.execute('UPDATE emi_messages SET content=? WHERE message=?',(payload.data['content'][:4000],payload.message_id))

async def setup(bot):
    bot.remove_command('raid')
    await bot.add_cog(Community(bot))
