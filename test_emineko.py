"""Pruebas aisladas: python -m unittest test_emineko -v"""
import json
import os
import sqlite3
import unittest
from pathlib import Path
from emi_store import Store

TEST_PATH=Path(__file__).resolve().parent/'.unit-emineko.db'
os.environ['BOT_DB_PATH']=str(TEST_PATH)
import bot

class StoreTests(unittest.TestCase):
    def setUp(self):
        self.store=Store(str(TEST_PATH))
        with self.store.connect() as db:
            for table in ('emi_items','emi_votes','emi_reminders','emi_limits','emi_protected','cards','users'):
                db.execute('DELETE FROM '+table)
    def test_private_scope_and_owner(self):
        ident=self.store.add(1,0,'memoria','dato',{'detalle':'privado'})
        self.assertEqual([],self.store.list(2,0,'memoria'))
        self.assertEqual(0,self.store.delete(ident,2))
        self.assertEqual(0,self.store.update(ident,2,{}))
        self.assertEqual(1,self.store.delete(ident,1))
    def test_votes_replace_and_close(self):
        import time
        ident=self.store.add(1,44,'encuesta','Pregunta',{'options':['a','b'],'ends':time.time()+100})
        self.store.vote(ident,8,1,44)
        self.store.vote(ident,8,2,44)
        self.assertEqual({2:1},self.store.results(ident))
        with self.assertRaises(ValueError): self.store.vote(ident,8,1,45)
        self.store.update(ident,1,{'options':['a','b'],'ends':0})
        with self.assertRaises(ValueError): self.store.vote(ident,8,1,44)
    def test_restart_reminder_and_limits(self):
        ident=self.store.remind(1,2,'prueba',100)
        self.assertEqual(0,self.store.acquire(1,'raid',60))
        restarted=Store(str(TEST_PATH))
        self.assertGreater(restarted.acquire(1,'raid',60),0)
        with restarted.connect() as db:
            self.assertEqual('prueba',db.execute('SELECT body FROM emi_reminders WHERE id=?',(ident,)).fetchone()[0])
    def card(self,rarity='N'):
        return bot.bot.db.add_or_ascend_card(1,42,'Test','Anime',rarity,'fire',100,10,10,10,'','')[0]
    def test_pack_rarity_and_deck_duplicates(self):
        first=self.card('N'); second=self.card('SSR')
        self.assertNotEqual(first,second)
        self.assertEqual('SSR',bot.bot.db.get_card(second)['rarity'])
        self.assertFalse(bot.bot.db.set_user_deck(1,[first,first])[0])
    def test_protected_card(self):
        ident=self.card()
        with self.store.connect() as db: db.execute('INSERT INTO emi_protected VALUES(?)',(ident,))
        self.assertFalse(bot.bot.db.sell_card(1,ident)[0])
        self.assertIsNotNone(bot.bot.db.get_card(ident))

if __name__=='__main__': unittest.main()
