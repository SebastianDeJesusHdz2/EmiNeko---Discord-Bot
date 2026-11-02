"""Regresiones de la versión completa: economía, permisos, ficheros y adaptadores."""
import asyncio
import io
import json
import os
from pathlib import Path
import time
import unittest
from unittest.mock import patch,AsyncMock
from concurrent.futures import ThreadPoolExecutor

ROOT=Path(__file__).resolve().parent
os.environ['BOT_DB_PATH']=str(ROOT/'.complete-bot.db')
os.environ['EMI_WEB_ENABLED']='0'
import bot
from emi_domain import Domain
from emi_services import photo_bytes,video_id,ServiceError,Services
from emi_rooms import Rooms
from aiohttp import web
from PIL import Image

class DomainTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db=bot.DatabaseManager(str(ROOT/'.complete-domain.db'))
        cls.store=Domain(cls.db.db_path)
    def setUp(self):
        with self.store.connect() as db:
            tables=[r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
            for table in tables: db.execute('DELETE FROM '+table)
        for user in (1,2,3): self.db.ensure_user(user)
    def card(self,user=1):
        return self.db.add_or_ascend_card(user,42,'Test','Test anime','SSR','fire',100,20,10,10,'','')[0]
    def test_market_atomic_transfer_and_balance(self):
        card=self.card(); ident=self.store.list_card(1,card,100)
        self.assertFalse(self.db.sell_card(1,card)[0])
        self.store.buy_card(2,ident)
        self.assertEqual(2,self.db.get_card(card)['owner_id'])
        self.assertEqual(600,self.db.ensure_user(1)['coins'])
        self.assertEqual(400,self.db.ensure_user(2)['coins'])
        with self.assertRaises(ValueError): self.store.buy_card(3,ident)
    def test_market_failure_rolls_back(self):
        card=self.card(); ident=self.store.list_card(1,card,800)
        with self.assertRaises(ValueError): self.store.buy_card(2,ident)
        self.assertEqual(1,self.db.get_card(card)['owner_id'])
        self.assertEqual(500,self.db.ensure_user(2)['coins'])
        with self.assertRaises(ValueError): self.store.buy_card(2,ident,cancel=True)
        self.store.buy_card(1,ident,cancel=True)
        self.assertTrue(self.db.sell_card(1,card)[0])
    def test_market_competing_buyers(self):
        card=self.card(); ident=self.store.list_card(1,card,100)
        def buy(user):
            try: self.store.buy_card(user,ident); return True
            except ValueError: return False
        with ThreadPoolExecutor(max_workers=2) as pool: outcomes=list(pool.map(buy,[2,3]))
        self.assertEqual(1,sum(outcomes))
        self.assertEqual(1500,sum(self.db.ensure_user(x)['coins'] for x in (1,2,3)))
    def test_event_waitlist_and_tenant(self):
        ident=self.store.event(40,1,200,'Reunión','Agenda',time.time()+5000,2)
        self.assertIn('Plaza 2',self.store.join_event(ident,2,40))
        self.assertIn('espera',self.store.join_event(ident,3,40))
        with self.assertRaises(ValueError): self.store.join_event(ident,3,41)
        self.store.join_event(ident,2,40,leave=True)
        self.assertIn('Plaza 2',self.store.join_event(ident,3,40))
    def test_raid_cooldown_and_reward_once(self):
        self.store.raid(40,1,'atacar',5000)
        with self.assertRaises(ValueError): self.store.raid(40,1,'atacar',5000)
        with self.assertRaises(ValueError): self.store.raid(40,2,'reclamar')
        with self.store.connect() as db: db.execute('UPDATE emi_boss SET hp=0 WHERE guild=40')
        self.store.raid(40,1,'reclamar')
        balance=self.db.ensure_user(1)['coins']
        with self.assertRaises(ValueError): self.store.raid(40,1,'reclamar')
        self.assertEqual(balance,self.db.ensure_user(1)['coins'])
    def test_tournament_byes_and_permissions(self):
        ident=self.store.tournament(40,1,'Torneo',['a','b','c','d','e'])
        with self.assertRaises(ValueError): self.store.tournament_win(ident,41,1,1,'a')
        while True:
            with self.store.connect() as db: row=db.execute('SELECT data FROM emi_tournaments WHERE id=?',(ident,)).fetchone()
            data=json.loads(row[0])
            if data['champion']: break
            index=next(i for i in range(len(data['matches'])) if str(i) not in data['winners'])
            winner=data['matches'][index][0]
            with self.assertRaises(ValueError): self.store.tournament_win(ident,40,2,index+1,winner)
            self.store.tournament_win(ident,40,1,index+1,winner)
        self.assertIn(data['champion'],['a','b','c','d','e'])
    def test_import_idempotence_preserves_progress(self):
        games=[{'id':'gog:123','name':'Game','source':'GOG','minutes':20}]
        self.store.import_games(1,games)
        row=self.store.list(1,0,'biblioteca')[0]; data=json.loads(row['data']);data['estado']='terminado'
        self.store.update(row['id'],1,data)
        games[0]['minutes']=40
        self.store.import_games(1,games*2)
        rows=self.store.list(1,0,'biblioteca')
        self.assertEqual(1,len(rows))
        self.assertEqual('terminado',json.loads(rows[0]['data'])['estado'])
        self.assertEqual(40,json.loads(rows[0]['data'])['minutes'])
    def test_arena_season_and_no_coins(self):
        delta=self.store.arena_result(1,2)
        self.assertEqual(12,delta)
        self.assertEqual(500,self.db.ensure_user(1)['coins'])
        with self.store.connect() as db:
            self.assertEqual(1,db.execute('SELECT wins FROM emi_arena WHERE user=1').fetchone()[0])

class AdapterTests(unittest.TestCase):
    def test_youtube_url_validation(self):
        self.assertEqual('abcdefghijk',video_id('https://youtu.be/abcdefghijk'))
        self.assertEqual('abcdefghijk',video_id('https://www.youtube.com/watch?v=abcdefghijk'))
        for url in ('file:///etc/passwd','http://localhost/a','https://youtube.com.evil.test/watch?v=abcdefghijk'):
            self.assertIsNone(video_id(url))
    def test_image_sanitization(self):
        image=Image.new('RGB',(100,80),'red'); exif=Image.Exif();exif[271]='Camera';exif[315]='Private name'
        buffer=io.BytesIO();image.save(buffer,format='JPEG',exif=exif)
        clean,metadata=photo_bytes(buffer.getvalue())
        self.assertEqual('Camera',metadata['Make']); self.assertNotIn('Artist',metadata)
        with Image.open(io.BytesIO(clean)) as output: self.assertFalse(output.getexif())
        with self.assertRaises(ServiceError): photo_bytes(b'not an image')

class AsyncTests(unittest.IsolatedAsyncioTestCase):
    async def test_shop_button_then_pull(self):
        from types import SimpleNamespace
        from emineko import Shop
        from discord.ext import commands
        uid=781002
        with bot.bot.db._get_conn() as db:
            db.execute('DELETE FROM cards WHERE owner_id=?',(uid,))
            db.execute('DELETE FROM users WHERE user_id=?',(uid,))
        user=SimpleNamespace(id=uid)
        interaction=SimpleNamespace(user=user,message=SimpleNamespace(_state=None),response=SimpleNamespace(defer=AsyncMock(),is_done=lambda:True))
        bot.bot.emi_purchase_lock=asyncio.Lock()
        shop=Shop(bot.bot,uid)
        with patch.object(commands.Context,'send',new=AsyncMock()):
            await shop.children[0].callback(interaction)
        self.assertEqual((280,10),tuple(bot.bot.db.ensure_user(uid)[k] for k in ('coins','pulls_left')))
        character={'mal_id':123,'name':'Prueba','anime':'Serie','favorites':100,'image':'','url':''}
        ctx=SimpleNamespace(author=user,defer=AsyncMock(),send=AsyncMock())
        with patch.object(bot.bot.api,'fetch_random_anime_character',new=AsyncMock(return_value=character)):
            await bot.bot.get_command('tirar').callback(ctx)
        self.assertEqual(9,bot.bot.db.ensure_user(uid)['pulls_left'])
        self.assertEqual(1,len(bot.bot.db.get_user_cards(uid)))

    async def test_private_search_runs_locally(self):
        from types import SimpleNamespace
        from emi_media import Media
        store=Domain(bot.bot.db.db_path)
        store.add(81123,0,'memoria','Cámara',{'detalle':'para el concierto'})
        store.add(81124,0,'memoria','Cámara ajena',{'detalle':'privado'})
        panel=AsyncMock()
        cog=SimpleNamespace(store=store,bot=SimpleNamespace(emi=SimpleNamespace(panel=panel)))
        ctx=SimpleNamespace(author=SimpleNamespace(id=81123),defer=AsyncMock())
        await Media.preguntar.callback(cog,ctx,'camara')
        results=panel.await_args.args[2]
        self.assertTrue(any('concierto' in entry for entry in results))
        self.assertFalse(any('ajena' in entry for entry in results))

    async def test_room_token_and_expiry(self):
        rooms=Rooms(bot.bot)
        token='test-token-'+'x'*32
        with rooms.store.connect() as db:
            db.execute('DELETE FROM emi_rooms')
            db.execute('INSERT INTO emi_rooms VALUES(?,?,?,?,?,?,?,?)',(token,1,40,'abcdefghijk',20,0,time.time(),time.time()+60))
        class Request:
            headers={'Authorization':'Bearer '+token}
        response=await rooms.state(Request())
        self.assertEqual(20,json.loads(response.body)['position'])
        Request.headers={'Authorization':'Bearer wrong'}
        with self.assertRaises(web.HTTPUnauthorized): await rooms.state(Request())
        Request.headers={'Authorization':'Bearer '+token}
        with rooms.store.connect() as db: db.execute('UPDATE emi_rooms SET expires=0')
        with self.assertRaises(web.HTTPNotFound): await rooms.state(Request())
    async def test_memory_capture_requires_consent(self):
        from emi_community import Community
        cog=Community(bot.bot)
        with cog.store.connect() as db:
            db.execute('DELETE FROM emi_sessions');db.execute('DELETE FROM emi_consent');db.execute('DELETE FROM emi_messages')
            db.execute('INSERT INTO emi_sessions(id,guild,owner,channel,title,started) VALUES(1,40,1,200,\'Test\',?)',(time.time(),))
        class Author: bot=False;id=2
        class Channel: id=200
        class Message: author=Author();channel=Channel();guild=True;content='Privado';id=501
        await cog.on_message(Message())
        with cog.store.connect() as db:
            self.assertEqual(0,db.execute('SELECT COUNT(*) FROM emi_messages').fetchone()[0])
            db.execute('INSERT INTO emi_consent VALUES(1,2)')
        await cog.on_message(Message())
        with cog.store.connect() as db: self.assertEqual(1,db.execute('SELECT COUNT(*) FROM emi_messages').fetchone()[0])

if __name__=='__main__': unittest.main()
