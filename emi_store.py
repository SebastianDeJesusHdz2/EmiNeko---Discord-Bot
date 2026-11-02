"""Persistencia de EmiNeko. No importa Discord ni modifica la base al importarse."""
import json
import sqlite3
import time
from contextlib import contextmanager

class Store:
    def __init__(self, path):
        self.path = path
        with self.connect() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS emi_protected (card INTEGER PRIMARY KEY);
            CREATE TABLE IF NOT EXISTS emi_items (
                id INTEGER PRIMARY KEY, owner INTEGER NOT NULL, guild INTEGER NOT NULL,
                kind TEXT NOT NULL, title TEXT NOT NULL, data TEXT NOT NULL,
                created REAL NOT NULL);
            CREATE INDEX IF NOT EXISTS emi_lookup ON emi_items(owner,guild,kind);
            CREATE TABLE IF NOT EXISTS emi_votes (
                poll INTEGER NOT NULL, user INTEGER NOT NULL, choice INTEGER NOT NULL,
                PRIMARY KEY(poll,user));
            CREATE TABLE IF NOT EXISTS emi_reminders (
                id INTEGER PRIMARY KEY, owner INTEGER NOT NULL, channel INTEGER NOT NULL,
                body TEXT NOT NULL, due REAL NOT NULL, sent INTEGER NOT NULL DEFAULT 0,
                attempts INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS emi_limits (
                user INTEGER NOT NULL, action TEXT NOT NULL, until REAL NOT NULL,
                PRIMARY KEY(user,action));
            ''')
    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()
    def add(self, owner, guild, kind, title, data=None):
        with self.connect() as db:
            return db.execute('INSERT INTO emi_items(owner,guild,kind,title,data,created) VALUES(?,?,?,?,?,?)',
                (owner,guild,kind,title,json.dumps(data or {},ensure_ascii=False),time.time())).lastrowid
    def list(self, owner, guild, kind):
        with self.connect() as db:
            return [dict(r) for r in db.execute('SELECT * FROM emi_items WHERE owner=? AND guild=? AND kind=? ORDER BY id DESC',(owner,guild,kind))]
    def get(self, item_id):
        with self.connect() as db:
            row=db.execute('SELECT * FROM emi_items WHERE id=?',(item_id,)).fetchone()
            return dict(row) if row else None
    def update(self, item_id, owner, data):
        with self.connect() as db:
            return db.execute('UPDATE emi_items SET data=? WHERE id=? AND owner=?',(json.dumps(data,ensure_ascii=False),item_id,owner)).rowcount
    def delete(self,item_id,owner):
        with self.connect() as db:
            return db.execute('DELETE FROM emi_items WHERE id=? AND owner=?',(item_id,owner)).rowcount
    def acquire(self,user,action,seconds):
        now=time.time()
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT until FROM emi_limits WHERE user=? AND action=?',(user,action)).fetchone()
            if row and row[0]>now:
                return int(row[0]-now)+1
            db.execute('INSERT OR REPLACE INTO emi_limits VALUES(?,?,?)',(user,action,now+seconds))
        return 0
    def vote(self,poll,user,choice,guild):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute("SELECT * FROM emi_items WHERE id=? AND kind='encuesta' AND guild=?",(poll,guild)).fetchone()
            if not row:
                raise ValueError('Encuesta no encontrada en este servidor.')
            data=json.loads(row['data'])
            if data.get('closed') or time.time()>=data['ends']:
                raise ValueError('La encuesta está cerrada.')
            if not 1<=choice<=len(data['options']):
                raise ValueError('Opción fuera de rango.')
            db.execute('INSERT OR REPLACE INTO emi_votes VALUES(?,?,?)',(poll,user,choice))
    def results(self,poll):
        with self.connect() as db:
            return dict(db.execute('SELECT choice,COUNT(*) FROM emi_votes WHERE poll=? GROUP BY choice',(poll,)))
    def remind(self,owner,channel,body,due):
        with self.connect() as db:
            return db.execute('INSERT INTO emi_reminders(owner,channel,body,due) VALUES(?,?,?,?)',(owner,channel,body,due)).lastrowid
