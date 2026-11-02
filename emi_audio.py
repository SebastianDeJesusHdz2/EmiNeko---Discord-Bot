"""Controles de audio y cola durable; no reproduce video en voz."""
import asyncio
import json
import time
import discord
from discord.ext import commands
from emineko import button_context, same_voice
from emi_domain import Domain

def persist(bot,guild_id):
    store=Domain(bot.db.db_path); mq=bot.get_music_queue(guild_id)
    data={'current':mq.current,'queue':mq.queue,'repeat':getattr(mq,'repeat','off'),'volume':getattr(mq,'volume',.5)}
    with store.connect() as db:
        row=db.execute("SELECT id FROM emi_items WHERE owner=0 AND guild=? AND kind='music'",(guild_id,)).fetchone()
        if row: db.execute('UPDATE emi_items SET data=? WHERE id=?',(json.dumps(data),row['id']))
        else: db.execute('INSERT INTO emi_items(owner,guild,kind,title,data,created) VALUES(0,?,\'music\',\'Cola\',?,?)',(guild_id,json.dumps(data),time.time()))

class Audio(commands.Cog):
    def __init__(self,bot): self.bot=bot
    async def cog_load(self):
        store=Domain(self.bot.db.db_path)
        with store.connect() as db: rows=db.execute("SELECT * FROM emi_items WHERE kind='music' AND owner=0").fetchall()
        for row in rows:
            data=json.loads(row['data']); mq=self.bot.get_music_queue(row['guild'])
            mq.queue=([data['current']] if data.get('current') else [])+data.get('queue',[])
            mq.repeat=data.get('repeat','off'); mq.volume=data.get('volume',.5)
    @commands.hybrid_command(name='audio',description='Volumen, repetición, mover, vaciar, adelantar o restaurar cola guardada.')
    @commands.guild_only()
    async def audio(self,ctx,accion:str='panel',valor:str=''):
        mq=self.bot.get_music_queue(ctx.guild.id)
        if accion=='restaurar':
            if not getattr(ctx.author,'voice',None): await ctx.send('Entra a un canal de voz.'); return
            if ctx.voice_client and not same_voice(ctx): await ctx.send('Entra al canal del bot.'); return
            if not ctx.voice_client: await ctx.author.voice.channel.connect()
            module=__import__(self.bot.__class__.__module__)
            module._play_next_in_guild(ctx.guild,self.bot)
            await ctx.send('Cola restaurada; se intentará reproducir la siguiente pista.'); return
        if not same_voice(ctx): await ctx.send('Debes estar en el mismo canal de voz.'); return
        vc=ctx.voice_client
        try:
            if accion=='volumen':
                volume=int(valor)
                if not 0<=volume<=100: raise ValueError()
                mq.volume=volume/100
                if isinstance(vc.source,discord.PCMVolumeTransformer): vc.source.volume=mq.volume
            elif accion=='repetir':
                if valor not in ('off','pista','cola'): raise ValueError()
                mq.repeat=valor
            elif accion=='mover':
                old,new=map(int,valor.split(','))
                if not 1<=old<=len(mq.queue) or not 1<=new<=len(mq.queue): raise ValueError()
                item=mq.queue.pop(old-1); mq.queue.insert(new-1,item)
            elif accion=='vaciar': mq.queue.clear()
            elif accion=='ir':
                seconds=int(valor)
                if not 0<=seconds<=86400 or not mq.current: raise ValueError()
                track=dict(mq.current); track['offset']=seconds
                mq.current=None; mq.queue.insert(0,track); mq.skip_once=True
                module=__import__(self.bot.__class__.__module__)
                if vc.is_playing() or vc.is_paused(): vc.stop()
                else: module._play_next_in_guild(ctx.guild,self.bot)
            elif accion!='panel': raise ValueError()
        except ValueError:
            await ctx.send('Usa volumen 0–100; repetir off/pista/cola; mover origen,destino; ir segundos; vaciar; restaurar.'); return
        persist(self.bot,ctx.guild.id)
        view=discord.ui.View(timeout=180)
        for name,label in [('pausa','⏸ Pausa'),('reanudar','▶ Reanudar'),('saltar','⏭ Saltar'),('salir','⏹ Salir')]:
            button=discord.ui.Button(label=label)
            async def invoke(i,command_name=name):
                command=self.bot.get_command(command_name)
                interaction_ctx=button_context(i,self.bot,command)
                try:
                    await command.can_run(interaction_ctx)
                    await command.callback(interaction_ctx)
                except commands.CheckFailure as exc:
                    await i.response.send_message(str(exc),ephemeral=True)
            button.callback=invoke; view.add_item(button)
        await ctx.send(f"Audio · Volumen {int(getattr(mq,'volume',.5)*100)}% · Repetir {getattr(mq,'repeat','off')} · {len(mq.queue)} pendientes",view=view)
async def setup(bot): await bot.add_cog(Audio(bot))
