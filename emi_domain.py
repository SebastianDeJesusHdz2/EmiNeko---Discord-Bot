"""Operaciones transaccionales de comunidad y economía de EmiNeko."""
import datetime as dt
import json
import random
import time
from emi_store import Store

class Domain(Store):
    def __init__(self,path):
        super().__init__(path)
        with self.connect() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS emi_events(id INTEGER PRIMARY KEY, guild INTEGER, owner INTEGER, channel INTEGER,
                title TEXT, body TEXT, due REAL, slots INTEGER, closed INTEGER DEFAULT 0);
            CREATE TABLE IF NOT EXISTS emi_attendees(event INTEGER, user INTEGER, joined REAL, PRIMARY KEY(event,user));
            CREATE TABLE IF NOT EXISTS emi_market(id INTEGER PRIMARY KEY, seller INTEGER, card INTEGER, price INTEGER, active INTEGER DEFAULT 1);
            CREATE UNIQUE INDEX IF NOT EXISTS emi_listing ON emi_market(card) WHERE active=1;
            CREATE TABLE IF NOT EXISTS emi_ledger(id INTEGER PRIMARY KEY, user INTEGER, amount INTEGER, reason TEXT, created REAL);
            CREATE TABLE IF NOT EXISTS emi_arena(user INTEGER, season TEXT, rating INTEGER DEFAULT 1000, wins INTEGER DEFAULT 0,
                losses INTEGER DEFAULT 0, PRIMARY KEY(user,season));
            CREATE TABLE IF NOT EXISTS emi_boss(guild INTEGER, day TEXT, hp INTEGER, max_hp INTEGER, PRIMARY KEY(guild,day));
            CREATE TABLE IF NOT EXISTS emi_damage(guild INTEGER, day TEXT, user INTEGER, damage INTEGER DEFAULT 0,
                last REAL DEFAULT 0, claimed INTEGER DEFAULT 0, PRIMARY KEY(guild,day,user));
            CREATE TABLE IF NOT EXISTS emi_tournaments(id INTEGER PRIMARY KEY, guild INTEGER, owner INTEGER, title TEXT, data TEXT);
            CREATE TABLE IF NOT EXISTS emi_alerts(id INTEGER PRIMARY KEY, owner INTEGER, kind TEXT, target TEXT, threshold REAL,
                state TEXT DEFAULT '', checked REAL DEFAULT 0, error TEXT DEFAULT '');
            CREATE TABLE IF NOT EXISTS emi_badges(user INTEGER, code TEXT, PRIMARY KEY(user,code));
            CREATE TABLE IF NOT EXISTS emi_cosmetics(user INTEGER, code TEXT, equipped INTEGER DEFAULT 0, PRIMARY KEY(user,code));
            CREATE TABLE IF NOT EXISTS emi_photos(id INTEGER PRIMARY KEY, owner INTEGER, title TEXT, filename TEXT, metadata TEXT);
            CREATE TABLE IF NOT EXISTS emi_sessions(id INTEGER PRIMARY KEY, guild INTEGER, owner INTEGER, channel INTEGER,
                title TEXT, started REAL, ended REAL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS emi_consent(session INTEGER, user INTEGER, PRIMARY KEY(session,user));
            CREATE TABLE IF NOT EXISTS emi_messages(session INTEGER, message INTEGER PRIMARY KEY, user INTEGER, content TEXT, created REAL);
            CREATE TABLE IF NOT EXISTS emi_rooms(token TEXT PRIMARY KEY, owner INTEGER, guild INTEGER, video TEXT, position REAL,
                playing INTEGER, updated REAL, expires REAL);
            ''')
            cols={r['name'] for r in db.execute('PRAGMA table_info(emi_reminders)')}
            if 'repeat_seconds' not in cols: db.execute('ALTER TABLE emi_reminders ADD COLUMN repeat_seconds INTEGER NOT NULL DEFAULT 0')
    def ledger(self,db,user,amount,reason):
        db.execute('INSERT INTO emi_ledger(user,amount,reason,created) VALUES(?,?,?,?)',(user,amount,reason,time.time()))
    def event(self,guild,owner,channel,title,body,due,slots):
        if not title or len(title)>180 or len(body)>1500 or due<=time.time() or not 1<=slots<=100:
            raise ValueError('Título de 1–180 caracteres, detalle hasta 1500, fecha futura y 1–100 plazas.')
        with self.connect() as db:
            ident=db.execute('INSERT INTO emi_events(guild,owner,channel,title,body,due,slots) VALUES(?,?,?,?,?,?,?)',(guild,owner,channel,title,body,due,slots)).lastrowid
            db.execute('INSERT INTO emi_attendees VALUES(?,?,?)',(ident,owner,time.time()))
            db.execute('INSERT INTO emi_reminders(owner,channel,body,due) VALUES(?,?,?,?)',(owner,channel,f'Evento #{ident}: {title}',max(time.time()+1,due-600)))
            return ident
    def join_event(self,event,user,guild,leave=False):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT * FROM emi_events WHERE id=? AND guild=?',(event,guild)).fetchone()
            if not row or row['closed'] or row['due']<=time.time(): raise ValueError('Evento inexistente, cerrado o pasado.')
            if leave: db.execute('DELETE FROM emi_attendees WHERE event=? AND user=?',(event,user)); return 'Inscripción retirada.'
            db.execute('INSERT OR IGNORE INTO emi_attendees VALUES(?,?,?)',(event,user,time.time()))
            ordered=[r[0] for r in db.execute('SELECT user FROM emi_attendees WHERE event=? ORDER BY joined,user',(event,))]
            n=ordered.index(user)+1
            return f'Plaza {n}/{row["slots"]}.' if n<=row['slots'] else f'Lista de espera: puesto {n-row["slots"]}.'
    def list_card(self,user,card,price):
        if not 1<=price<=1000000: raise ValueError('Precio entre 1 y 1,000,000 monedas.')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT * FROM cards WHERE card_id=? AND owner_id=?',(card,user)).fetchone()
            if not row: raise ValueError('La carta no te pertenece.')
            if db.execute('SELECT 1 FROM emi_protected WHERE card=?',(card,)).fetchone(): raise ValueError('Desbloquea la carta primero.')
            db.execute('INSERT INTO emi_protected VALUES(?)',(card,))
            db.execute('UPDATE cards SET in_deck=0 WHERE card_id=?',(card,))
            return db.execute('INSERT INTO emi_market(seller,card,price) VALUES(?,?,?)',(user,card,price)).lastrowid
    def buy_card(self,buyer,listing,cancel=False):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT * FROM emi_market WHERE id=? AND active=1',(listing,)).fetchone()
            if not row: raise ValueError('Anuncio no disponible.')
            if cancel:
                if buyer!=row['seller']: raise ValueError('Solo el vendedor puede cancelar.')
            else:
                if buyer==row['seller']: raise ValueError('No puedes comprarte tu propia carta.')
                if not db.execute('UPDATE users SET coins=coins-? WHERE user_id=? AND coins>=?',(row['price'],buyer,row['price'])).rowcount:
                    raise ValueError('Saldo insuficiente.')
                if not db.execute('UPDATE cards SET owner_id=?,in_deck=0 WHERE card_id=? AND owner_id=?',(buyer,row['card'],row['seller'])).rowcount:
                    raise ValueError('El propietario cambió; compra cancelada.')
                db.execute('UPDATE users SET coins=coins+? WHERE user_id=?',(row['price'],row['seller']))
                self.ledger(db,buyer,-row['price'],f'mercado:{listing}')
                self.ledger(db,row['seller'],row['price'],f'mercado:{listing}')
            db.execute('UPDATE emi_market SET active=0 WHERE id=?',(listing,))
            db.execute('DELETE FROM emi_protected WHERE card=?',(row['card'],))
    def raid(self,guild,user,action,power=0):
        day=dt.datetime.now(dt.timezone.utc).date().isoformat()
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('INSERT OR IGNORE INTO emi_boss VALUES(?,?,30000,30000)',(guild,day))
            boss=db.execute('SELECT * FROM emi_boss WHERE guild=? AND day=?',(guild,day)).fetchone()
            if action=='atacar':
                if power<=0: raise ValueError('Equipa al menos una carta.')
                if boss['hp']<=0: raise ValueError('Jefe derrotado. Reclama tu recompensa.')
                db.execute('INSERT OR IGNORE INTO emi_damage(guild,day,user) VALUES(?,?,?)',(guild,day,user))
                entry=db.execute('SELECT * FROM emi_damage WHERE guild=? AND day=? AND user=?',(guild,day,user)).fetchone()
                if entry['last']+3600>time.time(): raise ValueError('Un ataque por hora a este jefe.')
                # Three phases: armor, vulnerable, enraged. Contribution is actual damage only.
                ratio=boss['hp']/boss['max_hp']; factor=.8 if ratio>2/3 else 1.25 if ratio>1/3 else 1.0
                damage=min(boss['hp'],max(100,min(5000,int(power*factor))))
                db.execute('UPDATE emi_boss SET hp=hp-? WHERE guild=? AND day=?',(damage,guild,day))
                db.execute('UPDATE emi_damage SET damage=damage+?,last=? WHERE guild=? AND day=? AND user=?',(damage,time.time(),guild,day,user))
            elif action=='reclamar':
                if boss['hp']>0: raise ValueError('La recompensa se libera al derrotar al jefe.')
                row=db.execute('SELECT * FROM emi_damage WHERE guild=? AND day=? AND user=?',(guild,day,user)).fetchone()
                if not row or row['claimed']: raise ValueError('Sin recompensa pendiente.')
                reward=200+min(400,row['damage']//50)
                db.execute('UPDATE users SET coins=coins+? WHERE user_id=?',(reward,user))
                db.execute('UPDATE emi_damage SET claimed=1 WHERE guild=? AND day=? AND user=?',(guild,day,user))
                self.ledger(db,user,reward,'raid:'+day)
                return f'Recompensa colectiva: +{reward} monedas.'
            boss=db.execute('SELECT * FROM emi_boss WHERE guild=? AND day=?',(guild,day)).fetchone()
            leaders=db.execute('SELECT user,damage FROM emi_damage WHERE guild=? AND day=? ORDER BY damage DESC LIMIT 10',(guild,day)).fetchall()
            phase='Armadura' if boss['hp']>20000 else 'Vulnerable' if boss['hp']>10000 else 'Furia'
            return f"Jefe de hoy (UTC): {boss['hp']}/{boss['max_hp']} HP · Fase {phase}\n"+'\n'.join(f"<@{r['user']}>: {r['damage']} daño" for r in leaders)
    def arena_result(self,winner,loser):
        season=dt.datetime.now(dt.timezone.utc).strftime('%Y-%m')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            for user in (winner,loser): db.execute('INSERT OR IGNORE INTO emi_arena(user,season) VALUES(?,?)',(user,season))
            a=db.execute('SELECT rating FROM emi_arena WHERE user=? AND season=?',(winner,season)).fetchone()[0]
            b=db.execute('SELECT rating FROM emi_arena WHERE user=? AND season=?',(loser,season)).fetchone()[0]
            delta=max(1,round(24*(1-1/(1+10**(max(-4000,min(4000,b-a))/400)))))
            db.execute('UPDATE emi_arena SET rating=rating+?,wins=wins+1 WHERE user=? AND season=?',(delta,winner,season))
            db.execute('UPDATE emi_arena SET rating=MAX(0,rating-?),losses=losses+1 WHERE user=? AND season=?',(delta,loser,season))
        return delta
    def tournament(self,guild,owner,title,participants):
        if not 2<=len(participants)<=32 or len(set(participants))!=len(participants): raise ValueError('Indica 2–32 participantes distintos.')
        random.shuffle(participants)
        size=1
        while size<len(participants): size*=2
        # Seed byes in separate pairs, never [None,None].
        byes=size-len(participants); bracket=[[participants.pop(),None] for _ in range(byes)]
        bracket += [participants[i:i+2] for i in range(0,len(participants),2)]
        data={'round':1,'matches':bracket,'winners':{str(i):m[0] for i,m in enumerate(bracket) if m[1] is None},'champion':None}
        with self.connect() as db:
            return db.execute('INSERT INTO emi_tournaments(guild,owner,title,data) VALUES(?,?,?,?)',(guild,owner,title,json.dumps(data))).lastrowid
    def tournament_win(self,ident,guild,user,match,winner,admin=False):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT * FROM emi_tournaments WHERE id=? AND guild=?',(ident,guild)).fetchone()
            if not row or (row['owner']!=user and not admin): raise ValueError('Solo el organizador o administrador puede registrar resultados.')
            data=json.loads(row['data'])
            if data['champion'] or not 1<=match<=len(data['matches']): raise ValueError('Partida no disponible.')
            index=match-1
            if str(index) in data['winners'] or winner not in data['matches'][index]: raise ValueError('Resultado ya registrado o ganador ajeno a la partida.')
            data['winners'][str(index)]=winner
            if len(data['winners'])==len(data['matches']):
                winners=[data['winners'][str(i)] for i in range(len(data['matches']))]
                if len(winners)==1: data['champion']=winners[0]
                else: data.update(round=data['round']+1,matches=[winners[i:i+2] for i in range(0,len(winners),2)],winners={})
            db.execute('UPDATE emi_tournaments SET data=? WHERE id=?',(json.dumps(data),ident))
        return data
    def import_games(self,user,games):
        if not isinstance(games,list) or len(games)>20000: raise ValueError('Se requiere una lista de hasta 20,000 juegos.')
        normalized=[]
        for game in games:
            if not isinstance(game,dict) or not str(game.get('name','')).strip(): raise ValueError('Cada juego necesita name.')
            name=str(game['name'])[:180]; source=str(game.get('source','Manual'))[:80]
            key=str(game.get('id') or f'{source}:{name.casefold()}')[:200]
            normalized.append((key,name,{'source':source,'external_id':key,'detalle':source,'genres':game.get('genres',[])[:20],
                'minutes':max(0,int(game.get('minutes',0))),'estado':str(game.get('status','pendiente'))[:100]}))
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            existing={json.loads(r['data']).get('external_id'):r for r in db.execute("SELECT * FROM emi_items WHERE owner=? AND kind='biblioteca'",(user,))}
            for key,name,data in normalized:
                if key in existing:
                    row=existing[key]; old=json.loads(row['data']); old.update({k:v for k,v in data.items() if k not in ('estado','detalle')})
                    db.execute('UPDATE emi_items SET title=?,data=? WHERE id=?',(name,json.dumps(old),row['id']))
                else:
                    cursor=db.execute('INSERT INTO emi_items(owner,guild,kind,title,data,created) VALUES(?,0,?,?,?,?)',(user,'biblioteca',name,json.dumps(data),time.time()))
                    existing[key]={'id':cursor.lastrowid,'data':json.dumps(data)}
        return len(normalized)
