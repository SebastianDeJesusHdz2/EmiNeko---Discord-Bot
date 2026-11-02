#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""EmiNeko: Discord TCG, biblioteca, comunidad y entretenimiento.
Configuración y conexiones opcionales: PASO_A_PASO.md.
Las integraciones opcionales usan acceso gratuito con los límites de cada proveedor.
"""

import asyncio
import datetime
import json
import logging
import os
import random
import sqlite3
import sys
import urllib.parse
from typing import Any, Dict, List, Optional, Tuple

if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from pathlib import Path
from imageio_ffmpeg import get_ffmpeg_exe as ffmpeg_path
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent / ".env")

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

try:
    import yt_dlp
except ImportError:
    yt_dlp = None

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("EmiNeko")

# Configuración general
BOT_PREFIX = os.getenv("BOT_PREFIX", "!")
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "TU_TOKEN_DE_DISCORD_AQUI")
DB_PATH = os.getenv("BOT_DB_PATH", str(Path(__file__).resolve().parent / "otakubot_data.db"))

# Endpoints de APIs 100% Gratuitas (Sin API Key)
JIKAN_BASE_URL = "https://api.jikan.moe/v4"
ANILIST_GRAPHQL_URL = "https://graphql.anilist.co"
FREETOGAME_BASE_URL = "https://www.freetogame.com/api"
CHEAPSHARK_BASE_URL = "https://www.cheapshark.com/api/1.0"
STEAM_SEARCH_URL = "https://store.steampowered.com/api/storesearch/"
STEAM_APP_URL = "https://store.steampowered.com/api/appdetails"
NEKOS_BEST_URL = "https://nekos.best/api/v2"
WAIFU_PICS_URL = "https://api.waifu.pics/sfw"
PIPED_API_INSTANCES = [
    "https://pipedapi.kavin.rocks",
    "https://pipedapi.tokhmi.xyz",
    "https://pipedapi.moomoo.me",
]

# Configuración de rarezas para el Juego de Cartas (TCG)
RARITY_CONFIG: Dict[str, Dict[str, Any]] = {
    "UR": {
        "name": "Ultra Rara",
        "emoji": "🌈",
        "color": 0xFF007F,
        "mult": 2.25,
        "sell_value": 600,
        "weight": 3,
    },
    "SSR": {
        "name": "Super Super Rara",
        "emoji": "🌟",
        "color": 0xFFD700,
        "mult": 1.80,
        "sell_value": 280,
        "weight": 10,
    },
    "SR": {
        "name": "Super Rara",
        "emoji": "💜",
        "color": 0x9B59B6,
        "mult": 1.45,
        "sell_value": 120,
        "weight": 25,
    },
    "R": {
        "name": "Rara",
        "emoji": "💙",
        "color": 0x3498DB,
        "mult": 1.20,
        "sell_value": 55,
        "weight": 35,
    },
    "N": {
        "name": "Normal",
        "emoji": "🤍",
        "color": 0x95A5A6,
        "mult": 1.00,
        "sell_value": 25,
        "weight": 27,
    },
}

# Sistema Elemental con ventajas estratégicas (+25% de daño)
ELEMENTS: List[Dict[str, str]] = [
    {"id": "Fuego", "emoji": "🔥", "beats": "Viento"},
    {"id": "Viento", "emoji": "🌪️", "beats": "Rayo"},
    {"id": "Rayo", "emoji": "⚡", "beats": "Agua"},
    {"id": "Agua", "emoji": "💧", "beats": "Fuego"},
    {"id": "Luz", "emoji": "✨", "beats": "Oscuridad"},
    {"id": "Oscuridad", "emoji": "🌑", "beats": "Luz"},
]

ELEMENT_MAP = {e["id"]: e for e in ELEMENTS}

# Pool de respaldo por si la API externa está en mantenimiento o límite de peticiones
FALLBACK_CHARACTERS: List[Dict[str, Any]] = [
    {"mal_id": 417, "name": "Lelouch Lamperouge", "anime": "Code Geass", "favorites": 165000, "image": "https://cdn.myanimelist.net/images/characters/8/406163.jpg", "url": "https://myanimelist.net/character/417"},
    {"mal_id": 45627, "name": "Levi Ackerman", "anime": "Shingeki no Kyojin", "favorites": 142000, "image": "https://cdn.myanimelist.net/images/characters/2/241413.jpg", "url": "https://myanimelist.net/character/45627"},
    {"mal_id": 40, "name": "Monkey D. Luffy", "anime": "One Piece", "favorites": 138000, "image": "https://cdn.myanimelist.net/images/characters/9/310307.jpg", "url": "https://myanimelist.net/character/40"},
    {"mal_id": 71, "name": "L Lawliet", "anime": "Death Note", "favorites": 129000, "image": "https://cdn.myanimelist.net/images/characters/10/249647.jpg", "url": "https://myanimelist.net/character/71"},
    {"mal_id": 62, "name": "Roronoa Zoro", "anime": "One Piece", "favorites": 115000, "image": "https://cdn.myanimelist.net/images/characters/3/100534.jpg", "url": "https://myanimelist.net/character/62"},
    {"mal_id": 11, "name": "Edward Elric", "anime": "Fullmetal Alchemist: Brotherhood", "favorites": 110000, "image": "https://cdn.myanimelist.net/images/characters/9/72533.jpg", "url": "https://myanimelist.net/character/11"},
    {"mal_id": 164470, "name": "Satoru Gojo", "anime": "Jujutsu Kaisen", "favorites": 108000, "image": "https://cdn.myanimelist.net/images/characters/15/422168.jpg", "url": "https://myanimelist.net/character/164470"},
    {"mal_id": 2767, "name": "Killua Zoldyck", "anime": "Hunter x Hunter", "favorites": 105000, "image": "https://cdn.myanimelist.net/images/characters/9/325460.jpg", "url": "https://myanimelist.net/character/2767"},
    {"mal_id": 35252, "name": "Rintarou Okabe", "anime": "Steins;Gate", "favorites": 98000, "image": "https://cdn.myanimelist.net/images/characters/6/122643.jpg", "url": "https://myanimelist.net/character/35252"},
    {"mal_id": 422, "name": "Guts", "anime": "Berserk", "favorites": 96000, "image": "https://cdn.myanimelist.net/images/characters/15/540457.jpg", "url": "https://myanimelist.net/character/422"},
    {"mal_id": 17, "name": "Naruto Uzumaki", "anime": "Naruto: Shippuuden", "favorites": 89000, "image": "https://cdn.myanimelist.net/images/characters/9/131407.jpg", "url": "https://myanimelist.net/character/17"},
    {"mal_id": 34470, "name": "Kurisu Makise", "anime": "Steins;Gate", "favorites": 85000, "image": "https://cdn.myanimelist.net/images/characters/10/114399.jpg", "url": "https://myanimelist.net/character/34470"},
    {"mal_id": 118739, "name": "Mai Sakurajima", "anime": "Seishun Buta Yarou", "favorites": 74000, "image": "https://cdn.myanimelist.net/images/characters/2/366639.jpg", "url": "https://myanimelist.net/character/118739"},
    {"mal_id": 73935, "name": "Saitama", "anime": "One Punch Man", "favorites": 72000, "image": "https://cdn.myanimelist.net/images/characters/11/294388.jpg", "url": "https://myanimelist.net/character/73935"},
    {"mal_id": 174731, "name": "Frieren", "anime": "Sousou no Frieren", "favorites": 82000, "image": "https://cdn.myanimelist.net/images/characters/7/525105.jpg", "url": "https://myanimelist.net/character/174731"},
]

# Catálogo curado de joyas Indie en Steam (usado junto con Steam Store API en vivo)
CURATED_INDIE_APPIDS: List[Dict[str, Any]] = [
    {"appid": 367520, "title": "Hollow Knight", "genre": "Metroidvania / Soulslike", "why": "Un mundo subterráneo dibujado a mano con combate preciso y banda sonora inolvidable."},
    {"appid": 1145360, "title": "Hades", "genre": "Action Roguelike", "why": "Combate frenético, narrativa reactiva en el inframundo griego y dirección artística sobresaliente."},
    {"appid": 504230, "title": "Celeste", "genre": "Plataformas de Precisión", "why": "Uno de los mejores plataformeros 2D jamás creados con una historia emotiva sobre la superación."},
    {"appid": 413150, "title": "Stardew Valley", "genre": "Simulación / RPG", "why": "Creado por una sola persona; cientos de horas de granja, exploración de cuevas y vida comunitaria."},
    {"appid": 632470, "title": "Disco Elysium", "genre": "RPG Narrativo", "why": "Un sistema de diálogo revolucionario donde cada faceta de tu mente conversa contigo."},
    {"appid": 753640, "title": "Outer Wilds", "genre": "Exploración Espacial / Misterio", "why": "Un sistema solar atrapado en un bucle temporal de 22 minutos donde el único progreso es tu conocimiento."},
    {"appid": 391540, "title": "Undertale", "genre": "RPG / Bullet Hell", "why": "Un RPG subversivo lleno de carisma donde nadie tiene por qué morir."},
    {"appid": 646570, "title": "Slay the Spire", "genre": "Deckbuilder Roguelike", "why": "El referente absoluto de los juegos de cartas estratégicos con sinergias infinitas."},
    {"appid": 2379780, "title": "Balatro", "genre": "Póker Roguelike Deckbuilder", "why": "Hipnótico constructor de mazos basado en manos de póker y comodines que rompen las reglas."},
    {"appid": 588650, "title": "Dead Cells", "genre": "Roguevania / Acción 2D", "why": "Combate fluido a toda velocidad con docenas de armas, mutaciones y rutas alternativas."},
    {"appid": 105600, "title": "Terraria", "genre": "Sandbox / Aventura 2D", "why": "Construcción, exploración profunda y decenas de jefes épicos con soporte cooperativo."},
    {"appid": 632360, "title": "Risk of Rain 2", "genre": "Roguelike Cooperativo 3D", "why": "Escala de poder caótica y adictiva con una banda sonora electrónica extraordinaria."},
    {"appid": 1794680, "title": "Vampire Survivors", "genre": "Bullet Heaven / Roguelike", "why": "Dopamina pura convirtiendo a tu personaje en una tormenta imparable de proyectiles."},
    {"appid": 1364780, "title": "Street Fighter / Sea of Stars (1244090)", "appid_real": 1244090, "title": "Sea of Stars", "genre": "JRPG por Turnos Clásico", "why": "Homenaje moderno a Chrono Trigger con pixel art dinámico y música de Yasunori Mitsuda."},
    {"appid": 1623730, "title": "Palworld", "genre": "Supervivencia / Criaturas", "why": "Captura de criaturas, automatización de bases y exploración en mundo abierto."},
    {"appid": 1092790, "title": "Inscryption", "genre": "Terror Psicológico / Cartas", "why": "Una mezcla de juego de cartas, escape room y metaficción que sorprende a cada acto."},
    {"appid": 268910, "title": "Cuphead", "genre": "Run and Gun / Boss Rush", "why": "Animación tradicional de los años 30 dibujada a mano y jefes desafiantes."},
    {"appid": 1260320, "title": "Party Animals / Omori (1150690)", "appid_real": 1150690, "title": "OMORI", "genre": "RPG Psicológico", "why": "Una historia profunda sobre la amistad, los recuerdos y los miedos internos."},
]

# Wikis de Fandom preconfiguradas para búsqueda rápida con MediaWiki API
FANDOM_WIKIS: Dict[str, str] = {
    "wikipedia_es": "https://es.wikipedia.org/w/api.php",
    "wikipedia_en": "https://en.wikipedia.org/w/api.php",
    "onepiece": "https://onepiece.fandom.com/es/api.php",
    "naruto": "https://naruto.fandom.com/es/api.php",
    "dragonball": "https://dragonball.fandom.com/es/api.php",
    "jujutsukaisen": "https://jujutsu-kaisen.fandom.com/es/api.php",
    "kimetsu": "https://kimetsu-no-yaiba.fandom.com/es/api.php",
    "attackontitan": "https://shingeki-no-kyojin.fandom.com/es/api.php",
    "genshin": "https://genshin-impact.fandom.com/es/api.php",
    "hollowknight": "https://hollowknight.fandom.com/es/api.php",
    "undertale": "https://undertale.fandom.com/es/api.php",
    "terraria": "https://terraria.fandom.com/es/api.php",
    "stardew": "https://stardewvalleywiki.com/mediawiki/api.php",
}


# =============================================================================
# 🗄️ CAPA DE BASE DE DATOS (SQLITE3)
# =============================================================================
class DatabaseManager:
    """Gestiona usuarios, inventario de cartas, mazos, monedas y perfiles MAL."""

    def __init__(self, db_path: str = DB_PATH) -> None:
        self.db_path = db_path
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._get_conn() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS emi_ledger(id INTEGER PRIMARY KEY,user INTEGER,amount INTEGER,reason TEXT,created REAL);
                CREATE TABLE IF NOT EXISTS emi_protected (card INTEGER PRIMARY KEY);
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    coins INTEGER DEFAULT 500,
                    crystals INTEGER DEFAULT 10,
                    mal_username TEXT DEFAULT NULL,
                    wins INTEGER DEFAULT 0,
                    losses INTEGER DEFAULT 0,
                    daily_streak INTEGER DEFAULT 0,
                    last_daily TEXT DEFAULT NULL,
                    last_pull TEXT DEFAULT NULL,
                    pulls_left INTEGER DEFAULT 5
                );

                CREATE TABLE IF NOT EXISTS cards (
                    card_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    owner_id INTEGER NOT NULL,
                    mal_char_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    anime TEXT NOT NULL,
                    rarity TEXT NOT NULL,
                    element TEXT NOT NULL,
                    level INTEGER DEFAULT 1,
                    stars INTEGER DEFAULT 1,
                    exp INTEGER DEFAULT 0,
                    hp INTEGER NOT NULL,
                    atk INTEGER NOT NULL,
                    defense INTEGER NOT NULL,
                    spd INTEGER NOT NULL,
                    image_url TEXT,
                    char_url TEXT,
                    in_deck INTEGER DEFAULT 0,
                    obtained_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS raid_boss (
                    raid_id INTEGER PRIMARY KEY CHECK (raid_id = 1),
                    boss_name TEXT NOT NULL,
                    boss_anime TEXT NOT NULL,
                    boss_image TEXT NOT NULL,
                    element TEXT NOT NULL,
                    max_hp INTEGER NOT NULL,
                    current_hp INTEGER NOT NULL,
                    atk INTEGER NOT NULL,
                    level INTEGER DEFAULT 1,
                    updated_date TEXT NOT NULL
                );
                """
            )

    def ensure_user(self, user_id: int) -> sqlite3.Row:
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE user_id = ?", (user_id,)
            ).fetchone()
            if not row:
                conn.execute(
                    "INSERT INTO users (user_id, coins, crystals, pulls_left) VALUES (?, 500, 10, 5)",
                    (user_id,),
                )
                conn.commit()
                row = conn.execute(
                    "SELECT * FROM users WHERE user_id = ?", (user_id,)
                ).fetchone()
            return row

    def add_coins(self, user_id: int, amount: int, crystals: int = 0) -> None:
        self.ensure_user(user_id)
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE users SET coins = MAX(0, coins + ?), crystals = MAX(0, crystals + ?) WHERE user_id = ?",
                (amount, crystals, user_id),
            )
            conn.commit()

    def set_mal_username(self, user_id: int, mal_username: str) -> None:
        self.ensure_user(user_id)
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE users SET mal_username = ? WHERE user_id = ?",
                (mal_username, user_id),
            )
            conn.commit()

    def add_or_ascend_card(
        self,
        owner_id: int,
        mal_char_id: int,
        name: str,
        anime: str,
        rarity: str,
        element: str,
        hp: int,
        atk: int,
        defense: int,
        spd: int,
        image_url: str,
        char_url: str,
        *, cost: int = 0, use_ticket: bool = False,
    ) -> Tuple[int, bool, int]:
        """
        Si el usuario ya tiene exactamente el mismo personaje (mal_char_id),
        puede ascender sus estrellas (+1 estrella y +12% a todos sus stats)
        o agregarlo si tiene menos de 5 estrellas.
        Devuelve: (card_id, is_duplicate_ascended, new_stars)
        """
        self.ensure_user(owner_id)
        with self._get_conn() as conn:
            conn.execute('BEGIN IMMEDIATE')
            used_ticket = use_ticket and conn.execute('UPDATE users SET pulls_left=pulls_left-1 WHERE user_id=? AND pulls_left>0',(owner_id,)).rowcount
            if not used_ticket and cost and not conn.execute('UPDATE users SET coins=coins-? WHERE user_id=? AND coins>=?',(cost,owner_id,cost)).rowcount:
                raise commands.BadArgument('Saldo insuficiente para esta tirada. Usa /diario o /saldo.')
            if cost and not used_ticket:
                conn.execute('INSERT INTO emi_ledger(user,amount,reason,created) VALUES(?,?,?,?)',(owner_id,-cost,'tirada' if use_ticket else 'sobre',datetime.datetime.now().timestamp()))
            existing = conn.execute(
                "SELECT * FROM cards WHERE owner_id = ? AND mal_char_id = ? ORDER BY stars DESC LIMIT 1",
                (owner_id, mal_char_id),
            ).fetchone()

            rarity_order = {"N": 0, "R": 1, "SR": 2, "SSR": 3, "UR": 4}
            protected = existing and conn.execute("SELECT 1 FROM emi_protected WHERE card=?", (existing["card_id"],)).fetchone()
            if existing and not protected and existing["stars"] < 5 and rarity_order[rarity] <= rarity_order[existing["rarity"]]:
                new_stars = existing["stars"] + 1
                new_hp = int(existing["hp"] * 1.12)
                new_atk = int(existing["atk"] * 1.12)
                new_def = int(existing["defense"] * 1.12)
                new_spd = int(existing["spd"] * 1.08)
                conn.execute(
                    """
                    UPDATE cards
                    SET stars = ?, hp = ?, atk = ?, defense = ?, spd = ?
                    WHERE card_id = ?
                    """,
                    (new_stars, new_hp, new_atk, new_def, new_spd, existing["card_id"]),
                )
                conn.commit()
                return existing["card_id"], True, new_stars

            # Verificar cuántas cartas hay en el mazo para auto-equipar las primeras 3
            deck_count = conn.execute(
                "SELECT COUNT(*) as cnt FROM cards WHERE owner_id = ? AND in_deck > 0",
                (owner_id,),
            ).fetchone()["cnt"]
            in_deck_slot = (deck_count + 1) if deck_count < 3 else 0

            cursor = conn.execute(
                """
                INSERT INTO cards (
                    owner_id, mal_char_id, name, anime, rarity, element,
                    hp, atk, defense, spd, image_url, char_url, in_deck
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    owner_id,
                    mal_char_id,
                    name,
                    anime,
                    rarity,
                    element,
                    hp,
                    atk,
                    defense,
                    spd,
                    image_url,
                    char_url,
                    in_deck_slot,
                ),
            )
            conn.commit()
            return cursor.lastrowid, False, 1

    def get_user_cards(self, owner_id: int) -> List[sqlite3.Row]:
        with self._get_conn() as conn:
            return conn.execute(
                """
                SELECT * FROM cards
                WHERE owner_id = ?
                ORDER BY
                    in_deck DESC,
                    CASE rarity
                        WHEN 'UR' THEN 5
                        WHEN 'SSR' THEN 4
                        WHEN 'SR' THEN 3
                        WHEN 'R' THEN 2
                        ELSE 1
                    END DESC,
                    (hp + atk * 3 + defense * 2 + spd * 2) DESC
                """,
                (owner_id,),
            ).fetchall()

    def get_card(self, card_id: int) -> Optional[sqlite3.Row]:
        with self._get_conn() as conn:
            return conn.execute(
                "SELECT * FROM cards WHERE card_id = ?", (card_id,)
            ).fetchone()

    def get_user_deck(self, owner_id: int) -> List[sqlite3.Row]:
        with self._get_conn() as conn:
            deck = conn.execute(
                "SELECT * FROM cards WHERE owner_id = ? AND in_deck > 0 ORDER BY in_deck ASC LIMIT 3",
                (owner_id,),
            ).fetchall()
            if not deck:
                deck = conn.execute(
                    "SELECT * FROM cards WHERE owner_id = ? ORDER BY (hp + atk * 3 + defense * 2 + spd * 2) DESC LIMIT 3",
                    (owner_id,),
                ).fetchall()
            return deck

    def set_user_deck(self, owner_id: int, card_ids: List[int]) -> Tuple[bool, str]:
        if not card_ids or len(card_ids) > 3 or len(set(card_ids)) != len(card_ids):
            return False, "Debes indicar entre 1 y 3 IDs de cartas válidas."
        with self._get_conn() as conn:
            for cid in card_ids:
                row = conn.execute(
                    "SELECT card_id FROM cards WHERE card_id = ? AND owner_id = ?",
                    (cid, owner_id),
                ).fetchone()
                if not row:
                    return False, f"La carta con ID `#{cid}` no te pertenece o no existe."

            conn.execute(
                "UPDATE cards SET in_deck = 0 WHERE owner_id = ?", (owner_id,)
            )
            for idx, cid in enumerate(card_ids, start=1):
                conn.execute(
                    "UPDATE cards SET in_deck = ? WHERE card_id = ? AND owner_id = ?",
                    (idx, cid, owner_id),
                )
            conn.commit()
        return True, "Tu mazo de combate ha sido actualizado correctamente."

    def upgrade_card(self, owner_id: int, card_id: int) -> Tuple[bool, str, Optional[sqlite3.Row]]:
        user = self.ensure_user(owner_id)
        card = self.get_card(card_id)
        if not card or card["owner_id"] != owner_id:
            return False, "No tienes ninguna carta con ese ID.", None
        with self._get_conn() as conn:
            if conn.execute("SELECT 1 FROM emi_protected WHERE card=?", (card_id,)).fetchone():
                return False, "Desbloquea o retira del mercado la carta antes de mejorarla.", None
        if card["level"] >= 50:
            return False, "Esta carta ya alcanzó el nivel máximo (Nv. 50).", None

        cost = 80 + (card["level"] * 35)
        if user["coins"] < cost:
            return (
                False,
                f"Necesitas **{cost} 🪙 Monedas Otaku** para subir esta carta a Nv. {card['level'] + 1} (tienes **{user['coins']} 🪙**).",
                None,
            )

        new_lvl = card["level"] + 1
        new_hp = int(card["hp"] * 1.07) + 12
        new_atk = int(card["atk"] * 1.07) + 4
        new_def = int(card["defense"] * 1.07) + 3
        new_spd = int(card["spd"] * 1.04) + 2

        with self._get_conn() as conn:
            conn.execute(
                "UPDATE users SET coins = coins - ? WHERE user_id = ?",
                (cost, owner_id),
            )
            conn.execute(
                """
                UPDATE cards
                SET level = ?, hp = ?, atk = ?, defense = ?, spd = ?
                WHERE card_id = ?
                """,
                (new_lvl, new_hp, new_atk, new_def, new_spd, card_id),
            )
            conn.commit()

        updated = self.get_card(card_id)
        return True, f"¡Carta mejorada al **Nivel {new_lvl}** por **{cost} 🪙**!", updated

    def sell_card(self, owner_id: int, card_id: int) -> Tuple[bool, str, int]:
        card = self.get_card(card_id)
        if not card or card["owner_id"] != owner_id:
            return False, "Esa carta no existe o no te pertenece.", 0

        with self._get_conn() as conn:
            if conn.execute("SELECT 1 FROM emi_protected WHERE card=?", (card_id,)).fetchone():
                return False, "Carta protegida. Usa /bloquear para desbloquearla.", 0
        base_val = RARITY_CONFIG.get(card["rarity"], RARITY_CONFIG["N"])["sell_value"]
        value = int(base_val * (1 + (card["level"] - 1) * 0.25) * card["stars"])
        with self._get_conn() as conn:
            conn.execute("DELETE FROM cards WHERE card_id = ?", (card_id,))
            conn.execute(
                "UPDATE users SET coins = coins + ? WHERE user_id = ?",
                (value, owner_id),
            )
            conn.commit()
        return True, f"Vendiste a **{card['name']}** ({card['rarity']}) por **{value} 🪙**.", value

    def swap_card_owners(
        self, user1_id: int, card1_id: int, user2_id: int, card2_id: int
    ) -> Tuple[bool, str]:
        with self._get_conn() as conn:
            if conn.execute("SELECT 1 FROM emi_protected WHERE card IN (?,?)", (card1_id, card2_id)).fetchone():
                return False, "Una carta está protegida contra intercambio."
            c1 = conn.execute(
                "SELECT * FROM cards WHERE card_id = ? AND owner_id = ?",
                (card1_id, user1_id),
            ).fetchone()
            c2 = conn.execute(
                "SELECT * FROM cards WHERE card_id = ? AND owner_id = ?",
                (card2_id, user2_id),
            ).fetchone()
            if not c1 or not c2:
                return False, "Una de las cartas ya no pertenece a su dueño original."

            conn.execute(
                "UPDATE cards SET owner_id = ?, in_deck = 0 WHERE card_id = ?",
                (user2_id, card1_id),
            )
            conn.execute(
                "UPDATE cards SET owner_id = ?, in_deck = 0 WHERE card_id = ?",
                (user1_id, card2_id),
            )
            conn.commit()
        return True, "¡Intercambio completado con éxito!"

    def record_battle_result(self, winner_id: int, loser_id: Optional[int], reward: int) -> None:
        self.ensure_user(winner_id)
        if loser_id:
            self.ensure_user(loser_id)
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE users SET wins = wins + 1, coins = coins + ? WHERE user_id = ?",
                (reward, winner_id),
            )
            if loser_id:
                conn.execute(
                    "UPDATE users SET losses = losses + 1, coins = coins + 30 WHERE user_id = ?",
                    (loser_id,),
                )
            conn.commit()


# =============================================================================
# 🌐 CLIENTE DE APIS GRATUITAS (Jikan, AniList, FreeToGame, CheapShark, Steam, Wikis)
# =============================================================================
class FreeAPIClient:
    """Gestiona llamadas HTTP asíncronas con caché ligero y respaldo automático."""

    def __init__(self) -> None:
        self.session: Optional[aiohttp.ClientSession] = None
        self.cache = {}
        self.request_lock = asyncio.Lock()
        self.last_request = 0.0

    async def get_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=12)
            headers = {
                "User-Agent": "OtakuBotDiscord/2.0 (Free Open Source Anime & Indie Bot)"
            }
            self.session = aiohttp.ClientSession(timeout=timeout, headers=headers)
        return self.session

    async def close(self) -> None:
        if self.session and not self.session.closed:
            await self.session.close()

    async def fetch_json(
        self, url: str, params: Optional[Dict[str, Any]] = None
    ) -> Optional[Any]:
        import time
        key = (url, json.dumps(params or {}, sort_keys=True))
        cached = self.cache.get(key)
        if cached and cached[0] > time.monotonic():
            return cached[1]
        session = await self.get_session()
        async with self.request_lock:
            # Respect Jikan's sustained request budget; other services use the same queue.
            delay = 1.05 - (time.monotonic() - self.last_request)
            if delay > 0:
                await asyncio.sleep(delay)
            self.last_request = time.monotonic()
            try:
                async with session.get(url, params=params) as resp:
                    if resp.status == 200:
                        result = await resp.json(content_type=None)
                        if len(self.cache) >= 500:
                            self.cache.clear()
                        self.cache[key] = (time.monotonic() + 300, result)
                        return result
                    logger.warning("HTTP %s al consultar %s", resp.status, url)
            except (aiohttp.ClientError, asyncio.TimeoutError):
                logger.warning("Servicio no disponible: %s", url)
        return None


    async def post_json(
        self, url: str, payload: Dict[str, Any]
    ) -> Optional[Any]:
        session = await self.get_session()
        try:
            async with session.post(url, json=payload) as resp:
                if resp.status == 200:
                    return await resp.json(content_type=None)
        except Exception as exc:
            logger.warning("Error POST %s: %s", url, exc)
        return None

    # --- 1. GENERADOR DE CARTAS DE ANIME (Jikan API v4 + AniList GraphQL + Respaldo) ---
    async def fetch_random_anime_character(self) -> Dict[str, Any]:
        """Obtiene un personaje de anime real con imagen, anime de origen y popularidad."""
        page = random.randint(1, 35)
        data = await self.fetch_json(
            f"{JIKAN_BASE_URL}/top/characters", params={"page": page, "limit": 25}
        )
        if data and isinstance(data.get("data"), list) and data["data"]:
            char = random.choice(data["data"])
            mal_id = char.get("mal_id", random.randint(1000, 99999))
            name = char.get("name", "Personaje Misterioso")
            favorites = char.get("favorites", 1500)
            image = (
                char.get("images", {}).get("jpg", {}).get("image_url")
                or "https://cdn.myanimelist.net/images/characters/9/310307.jpg"
            )
            url = char.get("url", f"https://myanimelist.net/character/{mal_id}")
            nicknames = char.get("nicknames") or []
            credits = await self.fetch_json(f"{JIKAN_BASE_URL}/characters/{mal_id}/anime")
            appearances = credits.get("data", []) if credits else []
            anime_hint = next((entry.get("anime", {}).get("title") for entry in appearances if entry.get("anime", {}).get("title")), "Origen no disponible")
            return {
                "mal_id": mal_id,
                "name": name,
                "anime": anime_hint,
                "favorites": favorites,
                "image": image,
                "url": url,
            }

        # Respaldo instantáneo con AniList GraphQL API (100% gratis, sin API key)
        query = """
        query ($page: Int) {
          Page(page: $page, perPage: 20) {
            characters(sort: FAVOURITES_DESC) {
              id
              name { full }
              image { large }
              siteUrl
              favourites
              media(perPage: 1) {
                nodes { title { romaji } }
              }
            }
          }
        }
        """
        al_data = await self.post_json(
            ANILIST_GRAPHQL_URL,
            {"query": query, "variables": {"page": random.randint(1, 40)}},
        )
        chars = (
            al_data.get("data", {}).get("Page", {}).get("characters", [])
            if al_data
            else []
        )
        if chars:
            c = random.choice(chars)
            media_nodes = c.get("media", {}).get("nodes", [])
            anime_title = (
                media_nodes[0].get("title", {}).get("romaji", "Anime")
                if media_nodes
                else "Anime"
            )
            return {
                "mal_id": c.get("id", random.randint(10000, 99999)),
                "name": c.get("name", {}).get("full", "Héroe Anime"),
                "anime": anime_title,
                "favorites": c.get("favourites", 2000) * 3,
                "image": c.get("image", {}).get("large", ""),
                "url": c.get("siteUrl", "https://anilist.co"),
            }

        return random.choice(FALLBACK_CHARACTERS)

    # --- 2. PERFIL DE MYANIMELIST (Jikan API v4) ---
    async def fetch_mal_profile(self, username: str) -> Optional[Dict[str, Any]]:
        clean_user = urllib.parse.quote(username.strip())
        data = await self.fetch_json(f"{JIKAN_BASE_URL}/users/{clean_user}/full")
        if data and "data" in data:
            return data["data"]
        return None

    # --- 3. BÚSQUEDA Y RECOMENDACIONES DE ANIME (Jikan API v4 + AniList) ---
    async def search_anime(self, query_text: str) -> Optional[Dict[str, Any]]:
        data = await self.fetch_json(
            f"{JIKAN_BASE_URL}/anime",
            params={"q": query_text, "limit": 5, "sfw": "true"},
        )
        if data and data.get("data"):
            return data["data"][0]
        return None

    async def get_anime_recommendations(
        self, anime_query: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        if anime_query:
            base_anime = await self.search_anime(anime_query)
            if base_anime:
                mal_id = base_anime["mal_id"]
                rec_data = await self.fetch_json(
                    f"{JIKAN_BASE_URL}/anime/{mal_id}/recommendations"
                )
                if rec_data and rec_data.get("data"):
                    results = []
                    for item in rec_data["data"][:6]:
                        entry = item.get("entry", {})
                        results.append(
                            {
                                "title": entry.get("title", "Anime recomendado"),
                                "url": entry.get("url", "https://myanimelist.net"),
                                "image": entry.get("images", {})
                                .get("jpg", {})
                                .get("large_image_url"),
                                "votes": item.get("votes", 1),
                                "based_on": base_anime.get("title"),
                            }
                        )
                    if results:
                        return results

        # Si no se especificó un anime o no tuvo resultados, traer recomendaciones de temporada / top
        top_data = await self.fetch_json(
            f"{JIKAN_BASE_URL}/top/anime",
            params={"filter": "bypopularity", "page": random.randint(1, 5), "limit": 15},
        )
        results = []
        if top_data and top_data.get("data"):
            sample = random.sample(top_data["data"], k=min(5, len(top_data["data"])))
            for entry in sample:
                results.append(
                    {
                        "title": entry.get("title", "Anime"),
                        "url": entry.get("url", "https://myanimelist.net"),
                        "image": entry.get("images", {})
                        .get("jpg", {})
                        .get("large_image_url"),
                        "score": entry.get("score", "N/A"),
                        "synopsis": (entry.get("synopsis") or "Sin descripción.")[:220]
                        + "...",
                        "genres": ", ".join(
                            g["name"] for g in entry.get("genres", [])[:3]
                        ),
                    }
                )
        return results

    # --- 4. JUEGOS INDIE Y GRATUITOS (Steam Store API + FreeToGame API + CheapShark API) ---
    async def fetch_indie_game_details(self) -> Dict[str, Any]:
        choice = random.choice(CURATED_INDIE_APPIDS)
        appid = choice.get("appid_real", choice["appid"])
        steam_data = await self.fetch_json(
            STEAM_APP_URL, params={"appids": appid, "l": "spanish", "cc": "mx"}
        )
        info = {
            "title": choice["title"],
            "genre": choice["genre"],
            "why": choice["why"],
            "url": f"https://store.steampowered.com/app/{appid}/",
            "image": f"https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/{appid}/header.jpg",
            "price": "Consultar en tienda",
            "short_description": choice["why"],
            "developers": "Estudio Indie",
            "metacritic": None,
        }
        if steam_data and str(appid) in steam_data and steam_data[str(appid)].get("success"):
            app_info = steam_data[str(appid)]["data"]
            info["title"] = app_info.get("name", info["title"])
            info["short_description"] = app_info.get(
                "short_description", info["short_description"]
            )
            info["image"] = app_info.get("header_image", info["image"])
            devs = app_info.get("developers") or ["Estudio Indie"]
            info["developers"] = ", ".join(devs)
            if app_info.get("is_free"):
                info["price"] = "¡GRATIS (Free-to-Play)!"
            elif "price_overview" in app_info:
                po = app_info["price_overview"]
                discount = po.get("discount_percent", 0)
                final_fmt = po.get("final_formatted", "")
                if discount > 0:
                    info["price"] = f"{final_fmt} (-{discount}% de descuento 🔥)"
                else:
                    info["price"] = final_fmt
            if "metacritic" in app_info:
                info["metacritic"] = app_info["metacritic"].get("score")
        return info

    async def fetch_free_to_play_games(
        self, category: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        params = {"platform": "pc"}
        if category:
            params["category"] = category.lower().strip()
        data = await self.fetch_json(f"{FREETOGAME_BASE_URL}/games", params=params)
        if isinstance(data, list) and data:
            return random.sample(data, k=min(5, len(data)))
        return []

    async def fetch_game_deals(
        self, title: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {"pageSize": 6, "onSale": 1}
        if title:
            params["title"] = title
        else:
            params["sortBy"] = "Deal Rating"
        data = await self.fetch_json(f"{CHEAPSHARK_BASE_URL}/deals", params=params)
        if isinstance(data, list):
            return data[:6]
        return []

    # --- 5. WIKIS (MediaWiki Action API: Wikipedia ES/EN y Fandom) ---
    async def search_mediawiki(
        self, query_text: str, wiki_key: str = "wikipedia_es"
    ) -> Optional[Dict[str, Any]]:
        api_url = FANDOM_WIKIS.get(wiki_key.lower(), FANDOM_WIKIS["wikipedia_es"])
        search_params = {
            "action": "query",
            "list": "search",
            "srsearch": query_text,
            "srlimit": 1,
            "format": "json",
        }
        search_res = await self.fetch_json(api_url, params=search_params)
        hits = search_res.get("query", {}).get("search", []) if search_res else []
        if not hits:
            return None

        page_title = hits[0]["title"]
        detail_params = {
            "action": "query",
            "prop": "extracts|pageimages|info",
            "exintro": 1,
            "explaintext": 1,
            "exchars": 700,
            "piprop": "original|thumbnail",
            "pithumbsize": 600,
            "inprop": "url",
            "titles": page_title,
            "format": "json",
        }
        detail_res = await self.fetch_json(api_url, params=detail_params)
        pages = detail_res.get("query", {}).get("pages", {}) if detail_res else {}
        for _, page_data in pages.items():
            extract = page_data.get("extract") or "Artículo disponible en la wiki."
            img = (
                page_data.get("original", {}).get("source")
                or page_data.get("thumbnail", {}).get("source")
            )
            fullurl = page_data.get(
                "fullurl",
                f"https://es.wikipedia.org/wiki/{urllib.parse.quote(page_title)}",
            )
            return {
                "title": page_data.get("title", page_title),
                "extract": extract,
                "image": img,
                "url": fullurl,
                "wiki": wiki_key,
            }
        return None

    # --- 6. REACCIONES Y GIFS DE ANIME (Nekos.best + Waifu.pics) ---
    async def fetch_anime_reaction(self, action: str) -> Dict[str, str]:
        valid_nekos = [
            "hug", "pat", "slap", "wave", "dance", "smile", "highfive", "cry", "thumbsup", "laugh"
        ]
        act = action.lower().strip()
        if act not in valid_nekos:
            act = "hug"

        data = await self.fetch_json(f"{NEKOS_BEST_URL}/{act}")
        if data and data.get("results"):
            res = data["results"][0]
            return {
                "url": res.get("url", ""),
                "anime_name": res.get("anime_name", "Anime"),
            }

        wp_data = await self.fetch_json(f"{WAIFU_PICS_URL}/{act}")
        if wp_data and wp_data.get("url"):
            return {"url": wp_data["url"], "anime_name": "Waifu.pics"}
        return {
            "url": "https://nekos.best/api/v2/hug/001.gif",
            "anime_name": "Anime",
        }


# =============================================================================
# 🎲 UTILIDADES DE CARTAS Y CÁLCULO DE ESTADÍSTICAS
# =============================================================================
def generate_card_stats(favorites: int, force_min_rarity: Optional[str] = None) -> Tuple[str, str, int, int, int, int]:
    """Determina la rareza, elemento y calcula HP, ATK, DEF, SPD equilibrados."""
    rarities = list(RARITY_CONFIG.keys())
    weights = [RARITY_CONFIG[r]["weight"] for r in rarities]

    # Bonificación ligera si el personaje es muy popular en MyAnimeList
    if favorites > 80000:
        weights = [8, 18, 32, 27, 15]
    elif favorites > 30000:
        weights = [5, 14, 28, 33, 20]

    rarity = random.choices(rarities, weights=weights, k=1)[0]
    if force_min_rarity == "SR" and rarity in ("N", "R"):
        rarity = random.choices(["SR", "SSR", "UR"], weights=[70, 23, 7], k=1)[0]
    elif force_min_rarity == "SSR" and rarity in ("N", "R", "SR"):
        rarity = random.choices(["SSR", "UR"], weights=[80, 20], k=1)[0]

    mult = RARITY_CONFIG[rarity]["mult"]
    pop_bonus = min(1.30, 1.0 + (min(favorites, 150000) / 500000.0))
    total_mult = mult * pop_bonus

    hp = int(random.randint(420, 540) * total_mult)
    atk = int(random.randint(65, 92) * total_mult)
    defense = int(random.randint(40, 68) * total_mult)
    spd = int(random.randint(50, 88) * total_mult)
    element = random.choice(ELEMENTS)["id"]

    return rarity, element, hp, atk, defense, spd


def calculate_card_power(card: sqlite3.Row) -> int:
    return int(card["hp"] + card["atk"] * 3 + card["defense"] * 2 + card["spd"] * 2)


def has_elemental_advantage(attacker_elem: str, defender_elem: str) -> bool:
    info = ELEMENT_MAP.get(attacker_elem)
    return bool(info and info["beats"] == defender_elem)


# =============================================================================
# ⚔️ MOTOR INTERACTIVO DE BATALLAS DE CARTAS (PvE y PvP con discord.ui.View)
# =============================================================================
class BattleFighter:
    """Representa una carta activa dentro de un duelo por turnos."""

    def __init__(self, raw_card: Dict[str, Any]) -> None:
        self.card_id = raw_card.get("card_id", 0)
        self.name = raw_card["name"]
        self.anime = raw_card["anime"]
        self.rarity = raw_card["rarity"]
        self.element = raw_card["element"]
        self.level = raw_card.get("level", 1)
        self.stars = raw_card.get("stars", 1)
        self.max_hp = int(raw_card["hp"])
        self.hp = int(raw_card["hp"])
        self.atk = int(raw_card["atk"])
        self.defense = int(raw_card["defense"])
        self.spd = int(raw_card["spd"])
        self.image_url = raw_card.get("image_url", "")
        self.guarding = False


class CardBattleView(discord.ui.View):
    """Vista interactiva con botones para el juego de cartas por turnos."""

    def __init__(
        self,
        db: DatabaseManager,
        p1: discord.abc.User,
        p1_deck: List[BattleFighter],
        p2: Optional[discord.abc.User],
        p2_deck: List[BattleFighter],
        is_ai: bool = True,
    ) -> None:
        super().__init__(timeout=180)
        self.db = db
        self.p1 = p1
        self.p2 = p2
        self.p1_deck = p1_deck
        self.p2_deck = p2_deck
        self.p1_idx = 0
        self.p2_idx = 0
        self.p1_energy = 20
        self.p2_energy = 20
        self.is_ai = is_ai
        self.turn = 1 if self.active_p1.spd >= self.active_p2.spd else 2
        self.battle_log: List[str] = [
            "⚔️ ¡Comienza el Duelo de Cartas! Usa tus habilidades y ventajas elementales."
        ]
        self.finished = False

        if self.is_ai and self.turn == 2:
            self._execute_ai_turn()

    @property
    def active_p1(self) -> BattleFighter:
        return self.p1_deck[self.p1_idx]

    @property
    def active_p2(self) -> BattleFighter:
        return self.p2_deck[self.p2_idx]

    def build_embed(self) -> discord.Embed:
        f1 = self.active_p1
        f2 = self.active_p2
        e1 = ELEMENT_MAP.get(f1.element, {"emoji": "✨"})["emoji"]
        e2 = ELEMENT_MAP.get(f2.element, {"emoji": "🌑"})["emoji"]
        r1 = RARITY_CONFIG.get(f1.rarity, RARITY_CONFIG["N"])["emoji"]
        r2 = RARITY_CONFIG.get(f2.rarity, RARITY_CONFIG["N"])["emoji"]

        p2_name = "Maestro del Gremio (IA)" if self.is_ai else self.p2.display_name
        turn_owner = self.p1.display_name if self.turn == 1 else p2_name

        embed = discord.Embed(
            title=f"🎴 Duelo TCG: {self.p1.display_name} vs {p2_name}",
            description="\n".join(self.battle_log[-4:]),
            color=0xE91E63 if not self.finished else 0x2ECC71,
        )

        alive_p1 = sum(1 for c in self.p1_deck if c.hp > 0)
        alive_p2 = sum(1 for c in self.p2_deck if c.hp > 0)

        embed.add_field(
            name=f"🔵 {self.p1.display_name} ({alive_p1}/{len(self.p1_deck)} cartas)",
            value=(
                f"**{r1} [{f1.rarity}] {f1.name}** (Nv.{f1.level} {'⭐'*f1.stars})\n"
                f"Elemento: {e1} `{f1.element}`\n"
                f"❤️ HP: **{f1.hp}/{f1.max_hp}**\n"
                f"⚔️ ATK: `{f1.atk}` | 🛡️ DEF: `{f1.defense}` | ⚡ Energía: **{self.p1_energy}/100**"
            ),
            inline=True,
        )
        embed.add_field(
            name=f"🔴 {p2_name} ({alive_p2}/{len(self.p2_deck)} cartas)",
            value=(
                f"**{r2} [{f2.rarity}] {f2.name}** (Nv.{f2.level} {'⭐'*f2.stars})\n"
                f"Elemento: {e2} `{f2.element}`\n"
                f"❤️ HP: **{f2.hp}/{f2.max_hp}**\n"
                f"⚔️ ATK: `{f2.atk}` | 🛡️ DEF: `{f2.defense}` | ⚡ Energía: **{self.p2_energy}/100**"
            ),
            inline=True,
        )

        if f1.image_url:
            embed.set_thumbnail(url=f1.image_url)

        if not self.finished:
            embed.set_footer(
                text=f"Turno actual: {turn_owner} • Ventaja elemental otorga +25% de daño."
            )
        return embed

    def _compute_damage(
        self, attacker: BattleFighter, defender: BattleFighter, multiplier: float = 1.0, ignore_def: float = 0.0
    ) -> Tuple[int, bool]:
        effective_def = defender.defense * (1.0 - ignore_def)
        raw = (attacker.atk * multiplier) - (effective_def * 0.42)
        dmg = max(18, int(raw * random.uniform(0.93, 1.08)))
        adv = has_elemental_advantage(attacker.element, defender.element)
        if adv:
            dmg = int(dmg * 1.25)
        if defender.guarding:
            dmg = int(dmg * 0.50)
            defender.guarding = False
        return dmg, adv

    def _check_ko_and_advance(self) -> bool:
        if self.active_p1.hp <= 0:
            self.active_p1.hp = 0
            self.battle_log.append(f"💥 **{self.active_p1.name}** de {self.p1.display_name} cayó debilitado.")
            next_idx = next((i for i, c in enumerate(self.p1_deck) if c.hp > 0), None)
            if next_idx is None:
                self.finished = True
                p2_name = "Maestro del Gremio (IA)" if self.is_ai else self.p2.display_name
                self.battle_log.append(f"🏆 ¡**{p2_name}** gana el duelo!")
                if not self.is_ai and self.p2:
                    self.db.record_battle_result(self.p2.id, self.p1.id, 160)
                    self.battle_log.append(f"🪙 **{self.p2.display_name}** recibe **+160 Monedas Otaku**.")
                else:
                    self.db.add_coins(self.p1.id, 35)
                    self.battle_log.append(f"🪙 Recibes **+35 Monedas** de consolación por participar.")
                self._disable_all()
                return True
            self.p1_idx = next_idx
            self.battle_log.append(f"🔄 Entra al campo **{self.active_p1.name}**.")

        if self.active_p2.hp <= 0:
            self.active_p2.hp = 0
            p2_name = "Maestro del Gremio (IA)" if self.is_ai else self.p2.display_name
            self.battle_log.append(f"💥 **{self.active_p2.name}** de {p2_name} cayó debilitado.")
            next_idx = next((i for i, c in enumerate(self.p2_deck) if c.hp > 0), None)
            if next_idx is None:
                self.finished = True
                reward = 140 if self.is_ai else 180
                self.db.record_battle_result(
                    self.p1.id, None if self.is_ai else self.p2.id, reward
                )
                self.battle_log.append(
                    f"🏆 ¡**{self.p1.display_name}** gana la batalla y obtiene **+{reward} 🪙 Monedas Otaku**!"
                )
                self._disable_all()
                return True
            self.p2_idx = next_idx
            self.battle_log.append(f"🔄 {p2_name} envía a **{self.active_p2.name}**.")
        return False

    def _disable_all(self) -> None:
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True

    def _execute_ai_turn(self) -> None:
        if self.finished:
            return
        ai = self.active_p2
        target = self.active_p1
        ai.guarding = False
        if self.p2_energy >= 50:
            self.p2_energy -= 50
            dmg, adv = self._compute_damage(ai, target, multiplier=1.80, ignore_def=0.30)
            target.hp = max(0, target.hp - dmg)
            adv_txt = " *(¡Ventaja Elemental!)*" if adv else ""
            self.battle_log.append(
                f"🔥 **[IA] {ai.name}** desata su **Ultimate** e inflige **{dmg}** de daño{adv_txt}."
            )
        elif ai.hp < ai.max_hp * 0.30 and random.random() < 0.45:
            heal = int(ai.max_hp * 0.15)
            ai.hp = min(ai.max_hp, ai.hp + heal)
            ai.guarding = True
            self.p2_energy = min(100, self.p2_energy + 30)
            self.battle_log.append(
                f"🛡️ **[IA] {ai.name}** activa Guardia, recupera **+{heal} HP** y concentra energía."
            )
        else:
            dmg, adv = self._compute_damage(ai, target, multiplier=1.0)
            target.hp = max(0, target.hp - dmg)
            self.p2_energy = min(100, self.p2_energy + 25)
            adv_txt = " *(¡Super Efectivo!)*" if adv else ""
            self.battle_log.append(
                f"⚔️ **[IA] {ai.name}** ataca a **{target.name}** causando **{dmg}** de daño{adv_txt}."
            )
        self._check_ko_and_advance()
        self.turn = 1

    async def _validate_turn(self, interaction: discord.Interaction) -> bool:
        if self.finished:
            await interaction.response.send_message("Este duelo ya ha terminado.", ephemeral=True)
            return False
        expected_user = self.p1 if self.turn == 1 else self.p2
        if expected_user and interaction.user.id != expected_user.id:
            await interaction.response.send_message(
                f"Es el turno de **{expected_user.display_name}**.", ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="Ataque Básico", style=discord.ButtonStyle.primary, emoji="⚔️")
    async def btn_attack(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not await self._validate_turn(interaction):
            return
        attacker = self.active_p1 if self.turn == 1 else self.active_p2
        defender = self.active_p2 if self.turn == 1 else self.active_p1
        attacker.guarding = False

        dmg, adv = self._compute_damage(attacker, defender, multiplier=1.0)
        defender.hp = max(0, defender.hp - dmg)
        if self.turn == 1:
            self.p1_energy = min(100, self.p1_energy + 25)
        else:
            self.p2_energy = min(100, self.p2_energy + 25)

        adv_txt = " *(¡Ventaja Elemental +25%!)*" if adv else ""
        self.battle_log.append(
            f"⚔️ **{attacker.name}** ataca a **{defender.name}** e inflige **{dmg}** de daño{adv_txt}."
        )

        if not self._check_ko_and_advance():
            if self.is_ai:
                self.turn = 2
                self._execute_ai_turn()
            else:
                self.turn = 2 if self.turn == 1 else 1

        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(label="Habilidad Especial (50⚡)", style=discord.ButtonStyle.danger, emoji="💥")
    async def btn_special(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not await self._validate_turn(interaction):
            return
        energy = self.p1_energy if self.turn == 1 else self.p2_energy
        if energy < 50:
            await interaction.response.send_message(
                f"Necesitas **50⚡ de Energía** para lanzar tu Habilidad Especial (tienes **{energy}⚡**).",
                ephemeral=True,
            )
            return

        attacker = self.active_p1 if self.turn == 1 else self.active_p2
        defender = self.active_p2 if self.turn == 1 else self.active_p1
        attacker.guarding = False

        if self.turn == 1:
            self.p1_energy -= 50
        else:
            self.p2_energy -= 50

        dmg, adv = self._compute_damage(attacker, defender, multiplier=1.85, ignore_def=0.30)
        defender.hp = max(0, defender.hp - dmg)
        adv_txt = " *(¡Crítico Elemental!)*" if adv else ""
        self.battle_log.append(
            f"💥 ¡**{attacker.name}** desata su **Técnica Definitiva** y causa **{dmg}** de daño perforante{adv_txt}!"
        )

        if not self._check_ko_and_advance():
            if self.is_ai:
                self.turn = 2
                self._execute_ai_turn()
            else:
                self.turn = 2 if self.turn == 1 else 1

        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(label="Guardia + Curar", style=discord.ButtonStyle.success, emoji="🛡️")
    async def btn_defend(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not await self._validate_turn(interaction):
            return
        fighter = self.active_p1 if self.turn == 1 else self.active_p2
        fighter.guarding = True
        heal = int(fighter.max_hp * 0.15)
        fighter.hp = min(fighter.max_hp, fighter.hp + heal)

        if self.turn == 1:
            self.p1_energy = min(100, self.p1_energy + 30)
        else:
            self.p2_energy = min(100, self.p2_energy + 30)

        self.battle_log.append(
            f"🛡️ **{fighter.name}** adopta postura defensiva (-50% daño), recupera **+{heal} HP** y gana **+30⚡**."
        )

        if self.is_ai:
            self.turn = 2
            self._execute_ai_turn()
        else:
            self.turn = 2 if self.turn == 1 else 1

        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(label="Cambiar Carta", style=discord.ButtonStyle.secondary, emoji="🔄")
    async def btn_switch(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not await self._validate_turn(interaction):
            return
        deck = self.p1_deck if self.turn == 1 else self.p2_deck
        cur_idx = self.p1_idx if self.turn == 1 else self.p2_idx
        available = [i for i, c in enumerate(deck) if c.hp > 0 and i != cur_idx]
        if not available:
            await interaction.response.send_message(
                "No tienes otras cartas disponibles con vida en tu mazo para cambiar.",
                ephemeral=True,
            )
            return

        new_idx = available[0]
        if self.turn == 1:
            self.p1_idx = new_idx
            new_fighter = self.active_p1
        else:
            self.p2_idx = new_idx
            new_fighter = self.active_p2

        self.battle_log.append(
            f"🔄 Cambio táctico: entra **{new_fighter.name}** ({new_fighter.element}) al combate."
        )
        if self.is_ai:
            self.turn = 2
            self._execute_ai_turn()
        else:
            self.turn = 2 if self.turn == 1 else 1

        await interaction.response.edit_message(embed=self.build_embed(), view=self)


# =============================================================================
# 🤝 VISTA DE INTERCAMBIO DE CARTAS (TRADE)
# =============================================================================
class TradeOfferView(discord.ui.View):
    def __init__(
        self,
        db: DatabaseManager,
        sender: discord.abc.User,
        receiver: discord.abc.User,
        card_sender: sqlite3.Row,
        card_receiver: sqlite3.Row,
    ) -> None:
        super().__init__(timeout=120)
        self.db = db
        self.sender = sender
        self.receiver = receiver
        self.c1 = card_sender
        self.c2 = card_receiver

    @discord.ui.button(label="Aceptar Intercambio", style=discord.ButtonStyle.success, emoji="✅")
    async def accept_btn(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if interaction.user.id != self.receiver.id:
            await interaction.response.send_message(
                f"Solo **{self.receiver.display_name}** puede aceptar este intercambio.",
                ephemeral=True,
            )
            return

        ok, msg = self.db.swap_card_owners(
            self.sender.id, self.c1["card_id"], self.receiver.id, self.c2["card_id"]
        )
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True
        color = 0x2ECC71 if ok else 0xE74C3C
        embed = discord.Embed(
            title="🤝 Resultado del Intercambio",
            description=(
                f"{msg}\n\n"
                f"• **{self.sender.display_name}** recibió: **{self.c2['name']}** (`#{self.c2['card_id']}`)\n"
                f"• **{self.receiver.display_name}** recibió: **{self.c1['name']}** (`#{self.c1['card_id']}`)"
            ),
            color=color,
        )
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Rechazar", style=discord.ButtonStyle.danger, emoji="✖️")
    async def cancel_btn(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if interaction.user.id not in (self.sender.id, self.receiver.id):
            await interaction.response.send_message("No participas en este intercambio.", ephemeral=True)
            return
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True
        embed = discord.Embed(
            title="✖️ Intercambio Cancelado",
            description="La oferta de intercambio fue rechazada.",
            color=0xE74C3C,
        )
        await interaction.response.edit_message(embed=embed, view=self)


# =============================================================================
# 🎵 SISTEMA DE MÚSICA Y YOUTUBE (yt-dlp + FFmpeg + Piped API Fallback)
# =============================================================================
YTDL_OPTIONS: Dict[str, Any] = {
    "format": "bestaudio/best",
    "noplaylist": True,
    "quiet": True,
    "no_warnings": True,
    "default_search": "ytsearch",
    "source_address": "0.0.0.0",
}

FFMPEG_OPTIONS: Dict[str, str] = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn",
}


async def search_youtube_free(
    api_client: FreeAPIClient, query: str
) -> Optional[Dict[str, Any]]:
    """
    Busca un video o canción en YouTube de forma 100% gratuita sin API Key:
    1) Intenta con yt-dlp en un hilo asíncrono para obtener stream de audio directo y metadatos.
    2) Si yt-dlp no está instalado o falla, usa las instancias públicas de Piped REST API.
    """
    if query.lower().startswith(('http:', 'https:')):
        from emineko import youtube_url
        if not youtube_url(query): return None
    if yt_dlp is not None:
        loop = asyncio.get_running_loop()

        def _extract() -> Optional[Dict[str, Any]]:
            with yt_dlp.YoutubeDL(YTDL_OPTIONS) as ydl:
                search_Target = (
                    query
                    if query.startswith(("http://", "https://"))
                    else f"ytsearch1:{query}"
                )
                info = ydl.extract_info(search_Target, download=False)
                if "entries" in info and info["entries"]:
                    info = info["entries"][0]
                return info

        try:
            data = await loop.run_in_executor(None, _extract)
            if data:
                vid_id = data.get("id", "")
                webpage = data.get("webpage_url") or f"https://www.youtube.com/watch?v={vid_id}"
                return {
                    "title": data.get("title", "Video de YouTube"),
                    "webpage_url": webpage,
                    "stream_url": data.get("url"),
                    "duration": data.get("duration", 0),
                    "uploader": data.get("uploader", "Canal de YouTube"),
                    "thumbnail": data.get("thumbnail"),
                    "views": data.get("view_count", 0),
                }
        except Exception as exc:
            logger.warning("yt-dlp falló, intentando Piped API: %s", exc)

    # Respaldo con Piped API (100% libre y sin llave)
    for instance in PIPED_API_INSTANCES:
        res = await api_client.fetch_json(
            f"{instance}/search", params={"q": query, "filter": "videos"}
        )
        items = res.get("items", []) if isinstance(res, dict) else []
        if items:
            first = items[0]
            url_path = first.get("url", "")
            webpage = f"https://www.youtube.com{url_path}"
            return {
                "title": first.get("title", query),
                "webpage_url": webpage,
                "stream_url": None,
                "duration": first.get("duration", 0),
                "uploader": first.get("uploaderName", "YouTube"),
                "thumbnail": first.get("thumbnail"),
                "views": first.get("views", 0),
            }
    return None


class GuildMusicQueue:
    """Cola de reproducción de música por servidor."""

    def __init__(self) -> None:
        self.queue: List[Dict[str, Any]] = []
        self.current: Optional[Dict[str, Any]] = None


# =============================================================================
# ❓ VISTA DE TRIVIA OTAKU & INDIE
# =============================================================================
TRIVIA_BANK: List[Dict[str, Any]] = [
    {
        "question": "¿Cuál es el nombre verdadero de 'L' en el anime Death Note?",
        "options": ["L Lawliet", "Light Yagami", "Mihael Keehl", "Nate River"],
        "answer": 0,
        "category": "Anime • Death Note",
    },
    {
        "question": "¿Quién desarrolló prácticamente en solitario el famoso juego indie 'Stardew Valley'?",
        "options": ["Toby Fox", "Eric 'ConcernedApe' Barone", "Lucas Pope", "Edmund McMillen"],
        "answer": 1,
        "category": "Juegos Indie • Stardew Valley",
    },
    {
        "question": "En Fullmetal Alchemist: Brotherhood, ¿cuál es la ley fundamental de la alquimia?",
        "options": [
            "La Ley de la Conservación Espiritual",
            "El Intercambio Equivalente",
            "La Transmutación Infinita",
            "El Dogma de Amestris",
        ],
        "answer": 1,
        "category": "Anime • Fullmetal Alchemist",
    },
    {
        "question": "¿Cómo se llama el reino subterráneo donde transcurre la aventura de 'Hollow Knight'?",
        "options": ["Lordran", "Hallownest", "Pharloom", "Yharnam"],
        "answer": 1,
        "category": "Juegos Indie • Hollow Knight",
    },
    {
        "question": "En Jujutsu Kaisen, ¿cómo se llama la Expansión de Dominio de Satoru Gojo?",
        "options": [
            "Relicario Malévolo",
            "Vacío Inconmensurable (Unlimited Void)",
            "Jardín de las Sombras Quiméricas",
            "Ataúd de la Montaña de Hierro",
        ],
        "answer": 1,
        "category": "Anime • Jujutsu Kaisen",
    },
    {
        "question": "¿Qué estudio de animación produjo 'Sousou no Frieren' y 'One Punch Man (Temporada 1)'?",
        "options": ["ufotable", "Madhouse", "MAPPA", "Kyoto Animation"],
        "answer": 1,
        "category": "Anime • Estudios",
    },
    {
        "question": "En el juego indie 'Celeste', ¿cómo se llama la protagonista que escala la montaña?",
        "options": ["Madeline", "Hornet", "Mae Borowski", "Frisk"],
        "answer": 0,
        "category": "Juegos Indie • Celeste",
    },
]


class TriviaView(discord.ui.View):
    def __init__(self, db: DatabaseManager, item: Dict[str, Any]) -> None:
        super().__init__(timeout=30)
        self.db = db
        self.item = item
        self.answered_users: set[int] = set()

        for idx, opt in enumerate(item["options"]):
            btn = discord.ui.Button(
                label=opt[:80],
                style=discord.ButtonStyle.secondary,
                custom_id=f"trivia_{idx}",
            )
            btn.callback = self._make_callback(idx)
            self.add_item(btn)

    def _make_callback(self, idx: int):
        async def callback(interaction: discord.Interaction) -> None:
            if interaction.user.id in self.answered_users:
                await interaction.response.send_message(
                    "Ya respondiste esta pregunta de trivia.", ephemeral=True
                )
                return
            self.answered_users.add(interaction.user.id)

            if idx == self.item["answer"]:
                reward = 90
                self.db.add_coins(interaction.user.id, reward)
                for child in self.children:
                    if isinstance(child, discord.ui.Button):
                        child.disabled = True
                await interaction.response.edit_message(view=self)
                await interaction.followup.send(
                    f"🎉 ¡Correcto, {interaction.user.mention}! La respuesta era **{self.item['options'][idx]}**. Ganaste **+{reward} 🪙 Monedas Otaku**."
                )
            else:
                await interaction.response.send_message(
                    "❌ Respuesta incorrecta. ¡Sigue intentando en la próxima!",
                    ephemeral=True,
                )

        return callback


# =============================================================================
# 🤖 DEFINICIÓN PRINCIPAL DEL BOT Y TODOS SUS COMANDOS
# =============================================================================
class OtakuBot(commands.Bot):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.voice_states = True

        super().__init__(
            command_prefix=commands.when_mentioned_or(BOT_PREFIX),
            intents=intents,
            help_command=None,
            allowed_mentions=discord.AllowedMentions.none(),
        )
        self.db = DatabaseManager()
        self.api = FreeAPIClient()
        self.music_queues: Dict[int, GuildMusicQueue] = {}

    async def setup_hook(self) -> None:
        await self.load_extension("emineko")
        for extension in ("emi_community", "emi_media", "emi_audio", "emi_rooms", "emi_dashboard"):
            await self.load_extension(extension)
        try:
            await self.tree.sync()
            logger.info("Slash commands sincronizados correctamente.")
        except Exception as exc:
            logger.warning("No se pudieron sincronizar slash commands al inicio: %s", exc)

    async def close(self) -> None:
        from emi_audio import persist
        for guild_id in self.music_queues:
            persist(self, guild_id)
        for extension in list(self.extensions):
            await self.unload_extension(extension)
        await self.api.close()
        await super().close()

    def get_music_queue(self, guild_id: int) -> GuildMusicQueue:
        if guild_id not in self.music_queues:
            self.music_queues[guild_id] = GuildMusicQueue()
        return self.music_queues[guild_id]


bot = OtakuBot()


@bot.event
async def on_ready() -> None:
    logger.info("Conectado como %s (ID: %s)", bot.user, bot.user.id if bot.user else "N/A")
    activity = discord.Game(name=f"🐾 EmiNeko | /inicio")
    await bot.change_presence(status=discord.Status.online, activity=activity)


# -----------------------------------------------------------------------------
# 📖 COMANDO DE AYUDA GENERAL
# -----------------------------------------------------------------------------
@bot.hybrid_command(
    name="ayuda",
    aliases=["help", "comandos"],
    description="Muestra todos los comandos del bot de Anime, Cartas TCG, MyAnimeList, Música e Indies.",
)
async def cmd_help(ctx: commands.Context) -> None:
    await ctx.invoke(bot.get_command('inicio'))


@bot.hybrid_command(name="tirar", aliases=["gacha", "roll", "invocar"], description="Invoca una carta con una tirada gratuita o 60 monedas.")
async def cmd_pull_card(ctx: commands.Context) -> None:
    await ctx.defer()
    owner = ctx.author.id
    user = bot.db.ensure_user(owner)
    if user['pulls_left'] == 0 and user['coins'] < 60:
        await ctx.send('Necesitas una tirada o 60 monedas. Puedes reclamar /diario.')
        return
    character = await bot.api.fetch_random_anime_character()
    stats = generate_card_stats(character.get('favorites', 0))
    card_id, ascended, stars = bot.db.add_or_ascend_card(owner, character['mal_id'], character['name'], character['anime'], *stats, character['image'], character['url'], cost=60, use_ticket=True)
    card = bot.db.get_card(card_id)
    resources = bot.db.ensure_user(owner)
    embed = discord.Embed(title='Ascensión' if ascended else 'Nueva carta', description=f"**[{card['rarity']}] {card['name']}** · {'⭐'*stars}\n{card['anime']} · #{card_id}\n{card['element']} · Poder {calculate_card_power(card)}", color=RARITY_CONFIG[card['rarity']]['color'])
    if card['image_url']: embed.set_image(url=card['image_url'])
    embed.set_footer(text=f"Saldo: {resources['coins']} monedas y {resources['pulls_left']} tiradas")
    await ctx.send(embed=embed)


@bot.hybrid_command(
    name="coleccion",
    aliases=["cartas", "inventario", "cards"],
    description="Muestra tu colección de cartas de anime y tu mazo de combate.",
)
async def cmd_collection(
    ctx: commands.Context, miembro: Optional[discord.Member] = None
) -> None:
    target = miembro or ctx.author
    user_row = bot.db.ensure_user(target.id)
    cards = bot.db.get_user_cards(target.id)
    if not cards:
        await ctx.send(
            f"📭 **{target.display_name}** aún no tiene cartas. ¡Usa `{BOT_PREFIX}tirar` para invocar tu primera carta de anime!"
        )
        return

    from emineko import Pages
    lines = [f"**#{c['card_id']} [{c['rarity']}] {c['name']}** · Nv.{c['level']} · {'⭐'*c['stars']}\n{c['element']} · Poder {calculate_card_power(c)} · Mazo {c['in_deck'] or '—'}" for c in cards]
    view = Pages(ctx.author.id, f"Colección de {target.display_name} · {len(cards)} cartas", lines)
    await ctx.send(embed=view.embed(), view=view)


@bot.hybrid_command(
    name="carta",
    aliases=["vercarta", "cardinfo"],
    description="Muestra todos los detalles, imagen y estadísticas de una carta por su ID.",
)
async def cmd_card_detail(ctx: commands.Context, card_id: int) -> None:
    card = bot.db.get_card(card_id)
    if not card:
        await ctx.send(f"❌ No existe ninguna carta con el ID `#{card_id}`.")
        return

    r_info = RARITY_CONFIG.get(card["rarity"], RARITY_CONFIG["N"])
    e_info = ELEMENT_MAP.get(card["element"], ELEMENTS[0])
    power = calculate_card_power(card)

    embed = discord.Embed(
        title=f"{r_info['emoji']} [{card['rarity']}] {card['name']} (`#{card['card_id']}`)",
        url=card["char_url"],
        description=(
            f"📺 **Anime / Serie:** {card['anime']}\n"
            f"👤 **Dueño:** <@{card['owner_id']}>\n"
            f"⭐ **Ascensión:** {'⭐' * card['stars']} • **Nivel:** `{card['level']}/50`\n"
            f"🔮 **Elemento:** {e_info['emoji']} `{card['element']}` *(Fuerte contra {e_info['beats']})*"
        ),
        color=r_info["color"],
    )
    embed.add_field(
        name="⚔️ Estadísticas",
        value=(
            f"❤️ **Vida (HP):** `{card['hp']}`\n"
            f"🗡️ **Ataque (ATK):** `{card['atk']}`\n"
            f"🛡️ **Defensa (DEF):** `{card['defense']}`\n"
            f"💨 **Velocidad (SPD):** `{card['spd']}`\n"
            f"🔥 **Poder Total:** `{power}`"
        ),
        inline=False,
    )
    if card["image_url"]:
        embed.set_image(url=card["image_url"])
    await ctx.send(embed=embed)


@bot.hybrid_command(
    name="equipar",
    aliases=["deck"],
    description="Equipa hasta 3 cartas por su ID en tu mazo titular de batalla.",
)
async def cmd_equip_deck(
    ctx: commands.Context,
    carta1_id: Optional[int] = None,
    carta2_id: Optional[int] = None,
    carta3_id: Optional[int] = None,
) -> None:
    if carta1_id is None:
        deck = bot.db.get_user_deck(ctx.author.id)
        if not deck:
            await ctx.send(f"No tienes cartas aún. Usa `{BOT_PREFIX}tirar` para conseguir tus primeras cartas.")
            return
        desc = "\n".join(
            f"**Slot {i+1}:** `#{c['card_id']}` [{c['rarity']}] **{c['name']}** (Nv.{c['level']}) — ❤️{c['hp']} ⚔️{c['atk']} 🛡️{c['defense']}"
            for i, c in enumerate(deck)
        )
        embed = discord.Embed(
            title=f"🛡️ Mazo Titular de {ctx.author.display_name}",
            description=desc,
            color=0x3498DB,
        )
        embed.set_footer(text=f"Para cambiar tu mazo usa: {BOT_PREFIX}equipar <id1> [id2] [id3]")
        await ctx.send(embed=embed)
        return

    ids = [cid for cid in (carta1_id, carta2_id, carta3_id) if cid is not None]
    # Eliminar duplicados manteniendo el orden
    unique_ids = list(dict.fromkeys(ids))
    ok, msg = bot.db.set_user_deck(ctx.author.id, unique_ids)
    await ctx.send(f"{'✅' if ok else '❌'} {msg}")


@bot.hybrid_command(
    name="mejorar",
    aliases=["upgrade", "levelup"],
    description="Sube de nivel una de tus cartas usando tus Monedas Otaku.",
)
async def cmd_upgrade_card(ctx: commands.Context, card_id: int) -> None:
    ok, msg, updated = bot.db.upgrade_card(ctx.author.id, card_id)
    if not ok or not updated:
        await ctx.send(f"❌ {msg}")
        return
    embed = discord.Embed(
        title=f"⬆️ ¡{updated['name']} subió a Nivel {updated['level']}!",
        description=(
            f"{msg}\n\n"
            f"❤️ **HP:** `{updated['hp']}` | ⚔️ **ATK:** `{updated['atk']}` | "
            f"🛡️ **DEF:** `{updated['defense']}` | 💨 **SPD:** `{updated['spd']}`"
        ),
        color=0x2ECC71,
    )
    if updated["image_url"]:
        embed.set_thumbnail(url=updated["image_url"])
    await ctx.send(embed=embed)


@bot.hybrid_command(
    name="vender",
    aliases=["sell"],
    description="Vende una carta de tu inventario a cambio de Monedas Otaku.",
)
async def cmd_sell_card(ctx: commands.Context, card_id: int) -> None:
    ok, msg, _ = bot.db.sell_card(ctx.author.id, card_id)
    await ctx.send(f"{'🪙' if ok else '❌'} {msg}")


@bot.hybrid_command(
    name="intercambiar",
    aliases=["trade", "cambio"],
    description="Propone un intercambio de cartas con otro jugador del servidor.",
)
async def cmd_trade_card(
    ctx: commands.Context,
    usuario: discord.Member,
    mi_carta_id: int,
    su_carta_id: int,
) -> None:
    if usuario.bot or usuario.id == ctx.author.id:
        await ctx.send("❌ Debes elegir a otro jugador humano del servidor para intercambiar.")
        return

    c1 = bot.db.get_card(mi_carta_id)
    c2 = bot.db.get_card(su_carta_id)
    if not c1 or c1["owner_id"] != ctx.author.id:
        await ctx.send(f"❌ La carta `#{mi_carta_id}` no te pertenece.")
        return
    if not c2 or c2["owner_id"] != usuario.id:
        await ctx.send(f"❌ La carta `#{su_carta_id}` no pertenece a {usuario.display_name}.")
        return

    embed = discord.Embed(
        title="🤝 Propuesta de Intercambio de Cartas",
        description=(
            f"{ctx.author.mention} quiere intercambiar cartas con {usuario.mention}:\n\n"
            f"📤 **{ctx.author.display_name} entrega:** `#{c1['card_id']}` [{c1['rarity']}] **{c1['name']}** (Nv.{c1['level']})\n"
            f"📥 **{usuario.display_name} entrega:** `#{c2['card_id']}` [{c2['rarity']}] **{c2['name']}** (Nv.{c2['level']})"
        ),
        color=0xF1C40F,
    )
    view = TradeOfferView(bot.db, ctx.author, usuario, c1, c2)
    await ctx.send(content=usuario.mention, embed=embed, view=view)


@bot.hybrid_command(
    name="batalla",
    aliases=["duelo", "battle", "pvp"],
    description="Inicia un duelo táctico de cartas por turnos contra la IA o contra otro usuario.",
)
async def cmd_battle(
    ctx: commands.Context, oponente: Optional[discord.Member] = None
) -> None:
    if oponente and not oponente.bot and oponente.id != ctx.author.id:
        view = discord.ui.View(timeout=60)
        accepted = False
        accept = discord.ui.Button(label="Aceptar duelo", style=discord.ButtonStyle.success)
        reject = discord.ui.Button(label="Rechazar", style=discord.ButtonStyle.danger)
        async def answer(interaction, yes):
            nonlocal accepted
            if interaction.user.id != oponente.id:
                await interaction.response.send_message("Solo el rival puede responder.", ephemeral=True)
                return
            accepted = yes
            for child in view.children:
                child.disabled = True
            await interaction.response.edit_message(content="Duelo aceptado." if yes else "Duelo rechazado.", view=view)
            view.stop()
        async def yes(interaction): await answer(interaction, True)
        async def no(interaction): await answer(interaction, False)
        accept.callback, reject.callback = yes, no
        view.add_item(accept); view.add_item(reject)
        message = await ctx.send(f"{oponente.display_name}, {ctx.author.display_name} te invita a un duelo.", view=view)
        expired = await view.wait()
        if expired:
            for child in view.children: child.disabled = True
            await message.edit(content="Invitación de duelo vencida.", view=view)
        if not accepted:
            return
    p1_rows = bot.db.get_user_deck(ctx.author.id)
    if not p1_rows:
        await ctx.send(
            f"❌ Necesitas al menos 1 carta para combatir. ¡Usa `{BOT_PREFIX}tirar` para obtener tus primeras cartas!"
        )
        return

    p1_deck = [BattleFighter(dict(r)) for r in p1_rows]

    if oponente is None or oponente.bot or oponente.id == ctx.author.id:
        # Generar mazo equilibrado para la IA basado en el nivel de las cartas del jugador
        avg_lvl = max(1, int(sum(c.level for c in p1_deck) / len(p1_deck)))
        ai_Sample = random.sample(FALLBACK_CHARACTERS, k=len(p1_deck))
        ai_deck: List[BattleFighter] = []
        for ch in ai_Sample:
            rarity, elem, hp, atk, defense, spd = generate_card_stats(ch["favorites"])
            scale = 1.0 + (avg_lvl - 1) * 0.06
            ai_deck.append(
                BattleFighter(
                    {
                        "card_id": 0,
                        "name": ch["name"],
                        "anime": ch["anime"],
                        "rarity": rarity,
                        "element": elem,
                        "level": avg_lvl,
                        "stars": 1,
                        "hp": int(hp * scale * 0.92),
                        "atk": int(atk * scale * 0.92),
                        "defense": int(defense * scale * 0.92),
                        "spd": int(spd * scale * 0.92),
                        "image_url": ch["image"],
                    }
                )
            )
        view = CardBattleView(bot.db, ctx.author, p1_deck, None, ai_deck, is_ai=True)
        await ctx.send(embed=view.build_embed(), view=view)
    else:
        p2_rows = bot.db.get_user_deck(oponente.id)
        if not p2_rows:
            await ctx.send(
                f"❌ **{oponente.display_name}** aún no tiene cartas en su colección para un duelo PvP."
            )
            return
        p2_deck = [BattleFighter(dict(r)) for r in p2_rows]
        view = CardBattleView(
            bot.db, ctx.author, p1_deck, oponente, p2_deck, is_ai=False
        )
        await ctx.send(
            content=f"⚔️ {oponente.mention}, ¡{ctx.author.mention} te ha retado a un Duelo de Cartas!",
            embed=view.build_embed(),
            view=view,
        )


@bot.hybrid_command(
    name="raid",
    aliases=["jefe", "boss"],
    description="Ataca en equipo al Jefe Mundial de Anime del día usando tu mazo.",
)
async def cmd_raid(ctx: commands.Context) -> None:
    deck = bot.db.get_user_deck(ctx.author.id)
    if not deck:
        await ctx.send(f"❌ Primero consigue cartas con `{BOT_PREFIX}tirar` para participar en la Raid.")
        return

    today_str = datetime.date.today().isoformat()
    with bot.db._get_conn() as conn:
        boss = conn.execute("SELECT * FROM raid_boss WHERE raid_id = 1").fetchone()
        if not boss or boss["updated_date"] != today_str or boss["current_hp"] <= 0:
            picked = random.choice(FALLBACK_CHARACTERS)
            lvl = (boss["level"] + 1) if (boss and boss["current_hp"] <= 0) else 1
            max_hp = 8500 * lvl
            elem = random.choice(ELEMENTS)["id"]
            conn.execute(
                """
                INSERT OR REPLACE INTO raid_boss
                (raid_id, boss_name, boss_anime, boss_image, element, max_hp, current_hp, atk, level, updated_date)
                VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    picked["name"],
                    picked["anime"],
                    picked["image"],
                    elem,
                    max_hp,
                    max_hp,
                    180 * lvl,
                    lvl,
                    today_str,
                ),
            )
            conn.commit()
            boss = conn.execute("SELECT * FROM raid_boss WHERE raid_id = 1").fetchone()

        total_dmg = 0
        for c in deck:
            adv = 1.25 if has_elemental_advantage(c["element"], boss["element"]) else 1.0
            total_dmg += int((c["atk"] * 2.4 + c["spd"] * 0.8) * adv * random.uniform(0.95, 1.10))

        new_hp = max(0, boss["current_hp"] - total_dmg)
        conn.execute("UPDATE raid_boss SET current_hp = ? WHERE raid_id = 1", (new_hp,))
        conn.commit()

    reward = int(75 + (total_dmg * 0.08))
    if new_hp == 0:
        reward += 350
    bot.db.add_coins(ctx.author.id, reward)

    embed = discord.Embed(
        title=f"🐉 Raid Mundial: {boss['boss_name']} (Nv. {boss['level']})",
        description=(
            f"⚔️ El mazo de **{ctx.author.display_name}** infligió **{total_dmg:,}** puntos de daño.\n"
            f"❤️ **Vida del Jefe:** `{new_hp:,} / {boss['max_hp']:,} HP`\n"
            f"🪙 **Recompensa obtenida:** `+{reward} Monedas Otaku`"
            + ("\n🎉 **¡GOLPE DE GRACIA! Derrotaste al jefe y ganaste +350 🪙 extra!**" if new_hp == 0 else "")
        ),
        color=0xE67E22,
    )
    embed.set_thumbnail(url=boss["boss_image"])
    await ctx.send(embed=embed)


@bot.hybrid_command(
    name="diario",
    aliases=["daily", "recompensa"],
    description="Reclama tus Monedas Otaku y tiradas de Gacha diarias.",
)
async def cmd_daily(ctx: commands.Context) -> None:
    user = bot.db.ensure_user(ctx.author.id)
    today = datetime.date.today().isoformat()
    if user["last_daily"] == today:
        await ctx.send("⏳ Ya reclamaste tu recompensa diaria de hoy. ¡Vuelve mañana!")
        return

    yesterday = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
    streak = user["daily_streak"] + 1 if user["last_daily"] == yesterday else 1
    coins_reward = 250 + min(streak * 35, 350)
    pulls_bonus = 4

    with bot.db._get_conn() as conn:
        conn.execute(
            """
            UPDATE users
            SET coins = coins + ?, crystals = crystals + 5, pulls_left = pulls_left + ?, daily_streak = ?, last_daily = ?
            WHERE user_id = ?
            """,
            (coins_reward, pulls_bonus, streak, today, ctx.author.id),
        )
        conn.commit()

    embed = discord.Embed(
        title="🎁 ¡Recompensa Diaria Reclamada!",
        description=(
            f"🔥 **Racha diaria:** `{streak} día(s)`\n"
            f"🪙 **Monedas recibidas:** `+{coins_reward} Monedas Otaku` · +5 cristales\n"
            f"🎟️ **Tiradas de Gacha gratis:** `+{pulls_bonus} tiradas`"
        ),
        color=0x2ECC71,
    )
    await ctx.send(embed=embed)


@bot.hybrid_command(
    name="tienda",
    aliases=["shop"],
    description="Muestra la tienda de sobres especiales y recargas usando monedas del juego.",
)
async def cmd_shop(ctx: commands.Context) -> None:
    user = bot.db.ensure_user(ctx.author.id)
    embed = discord.Embed(
        title="🏪 Tienda del Gremio Otaku (100% con Monedas del Juego)",
        description=f"Tienes **{user['coins']} 🪙 Monedas Otaku**. Usa `{BOT_PREFIX}comprar <codigo>` para adquirir un artículo:",
        color=0xF39C12,
    )
    embed.add_field(
        name="1️⃣ `pack_tiradas` — Pack de 5 Tiradas Gacha (220 🪙)",
        value="Agrega 5 tiradas inmediatas para invocar personajes con `/tirar`.",
        inline=False,
    )
    embed.add_field(
        name="2️⃣ `sobre_sr` — Sobre Élite SR+ Garantizado (380 🪙)",
        value="Invoca al instante un personaje con rareza **SR, SSR o UR garantizada**.",
        inline=False,
    )
    embed.add_field(
        name="3️⃣ `sobre_ssr` — Sobre Legendario SSR/UR Garantizado (850 🪙)",
        value="Invoca al instante un personaje de rango **SSR (80%) o UR Mítico (20%)**.",
        inline=False,
    )
    from emineko import Shop
    user = bot.db.ensure_user(ctx.author.id)
    embed.set_footer(text=f"Saldo: {user['coins']} monedas. Pulsa un producto para comprarlo y abrirlo.")
    await ctx.send(embed=embed, view=Shop(bot, ctx.author.id))


@bot.hybrid_command(
    name="comprar",
    aliases=["buy"],
    description="Compra un sobre o pack en la tienda usando tus Monedas Otaku.",
)
async def cmd_buy(ctx: commands.Context, codigo: str) -> None:
    if not ctx.interaction or not ctx.interaction.response.is_done():
        await ctx.defer()
    user = bot.db.ensure_user(ctx.author.id)
    item = codigo.lower().strip()

    if item in ("1", "pack_tiradas", "tiradas"):
        cost = 220
        if user["coins"] < cost:
            await ctx.send(f"❌ Necesitas **{cost} 🪙** (tienes **{user['coins']} 🪙**).")
            return
        with bot.db._get_conn() as conn:
            conn.execute(
                "UPDATE users SET coins = coins - ?, pulls_left = pulls_left + 5 WHERE user_id = ?",
                (cost, ctx.author.id),
            )
            conn.execute('INSERT INTO emi_ledger(user,amount,reason,created) VALUES(?,?,?,?)',(ctx.author.id,-cost,'pack de tiradas',datetime.datetime.now().timestamp()))
            conn.commit()
        await ctx.send(f"✅ Compraste **+5 Tiradas de Gacha** por **{cost} 🪙**. ¡Usa `{BOT_PREFIX}tirar`!")
        return

    if item in ("2", "sobre_sr", "sr", "3", "sobre_ssr", "ssr"):
        is_ssr = item in ("3", "sobre_ssr", "ssr")
        cost = 850 if is_ssr else 380
        min_r = "SSR" if is_ssr else "SR"
        if user["coins"] < cost:
            await ctx.send(f"❌ Necesitas **{cost} 🪙** (tienes **{user['coins']} 🪙**).")
            return
        char_data = await bot.api.fetch_random_anime_character()
        rarity, element, hp, atk, defense, spd = generate_card_stats(
            char_data.get("favorites", 10000), force_min_rarity=min_r
        )
        card_id, is_asc, stars = bot.db.add_or_ascend_card(
            ctx.author.id,
            char_data["mal_id"],
            char_data["name"],
            char_data["anime"],
            rarity,
            element,
            hp,
            atk,
            defense,
            spd,
            char_data["image"],
            char_data["url"], cost=cost,
        )
        saved = bot.db.get_card(card_id)
        rarity, element, hp, atk, defense, spd = (saved[k] for k in ("rarity", "element", "hp", "atk", "defense", "spd"))
        r_info = RARITY_CONFIG[rarity]
        embed = discord.Embed(
            title=f"{r_info['emoji']} ¡Sobre Especial Abierto: [{rarity}] {char_data['name']}!",
            description=(
                f"🆔 ID: `#{card_id}` • {'⭐'*stars}\n"
                f"📺 Origen: {char_data['anime']}\n"
                f"❤️ HP: `{hp}` | ⚔️ ATK: `{atk}` | 🛡️ DEF: `{defense}` | 💨 SPD: `{spd}`"
            ),
            color=r_info["color"],
        )
        if char_data.get("image"):
            embed.set_image(url=char_data["image"])
        await ctx.send(embed=embed)
        return

    await ctx.send(f"❌ Código no válido. Revisa `{BOT_PREFIX}tienda` (`pack_tiradas`, `sobre_sr`, `sobre_ssr`).")


@bot.hybrid_command(
    name="ranking",
    aliases=["top", "leaderboard"],
    description="Muestra el ranking de jugadores con más victorias y monedas.",
)
async def cmd_leaderboard(ctx: commands.Context) -> None:
    with bot.db._get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM users ORDER BY wins DESC, coins DESC LIMIT 10"
        ).fetchall()

    if not rows:
        await ctx.send("Aún no hay jugadores registrados en el ranking.")
        return

    medals = ["🥇", "🥈", "🥉"]
    lines = []
    for idx, r in enumerate(rows):
        badge = medals[idx] if idx < 3 else f"`#{idx+1}`"
        lines.append(
            f"{badge} <@{r['user_id']}> — 🏆 **{r['wins']} Victorias** | 🪙 `{r['coins']} Monedas`"
        )

    embed = discord.Embed(
        title="🏆 Ranking Global del Gremio TCG",
        description="\n".join(lines),
        color=0xFFD700,
    )
    await ctx.send(embed=embed)


# -----------------------------------------------------------------------------
# 📊 COMANDOS DE MYANIMELIST Y ANIME (Jikan REST API v4)
# -----------------------------------------------------------------------------
@bot.hybrid_command(
    name="vincular_mal",
    aliases=["setmal", "linkmal"],
    description="Guarda tu nombre de usuario de MyAnimeList para consultar tu perfil rápidamente.",
)
async def cmd_link_mal(ctx: commands.Context, username: str) -> None:
    bot.db.set_mal_username(ctx.author.id, username.strip())
    await ctx.send(
        f"✅ Tu cuenta de **MyAnimeList** ha sido vinculada como **`{username.strip()}`**. Ahora puedes usar `{BOT_PREFIX}mal` directamente."
    )


@bot.hybrid_command(
    name="mal",
    aliases=["perfil_mal", "myanimelist"],
    description="Muestra el perfil completo, estadísticas y favoritos de MyAnimeList.",
)
async def cmd_mal_profile(
    ctx: commands.Context, username: Optional[str] = None
) -> None:
    await ctx.defer()
    if not username:
        user_row = bot.db.ensure_user(ctx.author.id)
        username = user_row["mal_username"]
        if not username:
            await ctx.send(
                f"ℹ️ Indica un nombre de usuario (`{BOT_PREFIX}mal <usuario>`) o vincula el tuyo con `{BOT_PREFIX}vincular_mal <tu_usuario>`."
            )
            return

    profile = await bot.api.fetch_mal_profile(username)
    if not profile:
        await ctx.send(
            f"❌ No se pudo encontrar el perfil público **`{username}`** en MyAnimeList (verifica que esté bien escrito y sea público)."
        )
        return

    anime_stats = profile.get("statistics", {}).get("anime", {})
    manga_stats = profile.get("statistics", {}).get("manga", {})
    favs = profile.get("favorites", {})
    fav_anime = [a["title"] for a in favs.get("anime", [])[:4]]
    fav_chars = [c["name"] for c in favs.get("characters", [])[:4]]

    embed = discord.Embed(
        title=f"📊 Perfil de MyAnimeList: {profile.get('username')}",
        url=profile.get("url", f"https://myanimelist.net/profile/{username}"),
        description=(profile.get("about") or "Sin biografía pública.")[:280],
        color=0x2E51A2,
    )
    avatar = profile.get("images", {}).get("jpg", {}).get("image_url")
    if avatar:
        embed.set_thumbnail(url=avatar)

    embed.add_field(
        name="📺 Estadísticas de Anime",
        value=(
            f"⏱️ **Días vistos:** `{anime_stats.get('days_watched', 0)}` días\n"
            f"⭐ **Nota Promedio:** `{anime_stats.get('mean_score', 0)}`\n"
            f"✅ **Completados:** `{anime_stats.get('completed', 0)}`\n"
            f"👀 **Viendo ahora:** `{anime_stats.get('watching', 0)}`\n"
            f"🗓️ **Planeados:** `{anime_stats.get('plan_to_watch', 0)}`\n"
            f"🎞️ **Episodios totales:** `{anime_stats.get('episodes_watched', 0):,}`"
        ),
        inline=True,
    )
    embed.add_field(
        name="📖 Estadísticas de Manga",
        value=(
            f"⏱️ **Días leídos:** `{manga_stats.get('days_read', 0)}` días\n"
            f"⭐ **Nota Promedio:** `{manga_stats.get('mean_score', 0)}`\n"
            f"✅ **Completados:** `{manga_stats.get('completed', 0)}`\n"
            f"📖 **Leyendo:** `{manga_stats.get('reading', 0)}`\n"
            f"📑 **Capítulos leídos:** `{manga_stats.get('chapters_read', 0):,}`"
        ),
        inline=True,
    )
    if fav_anime or fav_chars:
        embed.add_field(
            name="❤️ Favoritos Destacados",
            value=(
                f"🎬 **Animes:** {', '.join(fav_anime) if fav_anime else 'Ninguno listado'}\n"
                f"🌟 **Personajes:** {', '.join(fav_chars) if fav_chars else 'Ninguno listado'}"
            ),
            inline=False,
        )
    embed.set_footer(text="Datos en tiempo real vía Jikan REST API v4 (MyAnimeList)")
    await ctx.send(embed=embed)


@bot.hybrid_command(
    name="anime",
    aliases=["buscar_anime", "animeinfo"],
    description="Busca información detallada, puntuación y tráiler de cualquier anime.",
)
async def cmd_search_anime(ctx: commands.Context, *, nombre: str) -> None:
    await ctx.defer()
    info = await bot.api.search_anime(nombre)
    if not info:
        await ctx.send(f"❌ No encontré ningún anime que coincida con **`{nombre}`**.")
        return

    genres = ", ".join(g["name"] for g in info.get("genres", [])) or "N/A"
    studios = ", ".join(s["name"] for s in info.get("studios", [])) or "Desconocido"
    trailer = info.get("trailer", {}).get("url")
    synopsis = (info.get("synopsis") or "Sin sinopsis disponible.")[:480] + "..."

    embed = discord.Embed(
        title=f"🎬 {info.get('title')} ({info.get('year') or 'Anime'})",
        url=info.get("url"),
        description=synopsis,
        color=0x3498DB,
    )
    embed.add_field(
        name="📌 Detalles",
        value=(
            f"⭐ **Puntuación MAL:** `{info.get('score', 'N/A')}` (#{info.get('rank', 'N/A')})\n"
            f"🎞️ **Episodios:** `{info.get('episodes') or '?'}` ({info.get('status', 'N/A')})\n"
            f"🏢 **Estudio:** {studios}\n"
            f"🏷️ **Géneros:** {genres}"
        ),
        inline=False,
    )
    if trailer:
        embed.add_field(name="🎥 Tráiler Oficial", value=f"[Ver en YouTube]({trailer})", inline=False)

    img = info.get("images", {}).get("jpg", {}).get("large_image_url")
    if img:
        embed.set_image(url=img)
    await ctx.send(embed=embed)


@bot.hybrid_command(
    name="recomendar_anime",
    aliases=["rec_anime", "anirec"],
    description="Te recomienda animes similares a uno que te guste o joyas populares.",
)
async def cmd_recommend_anime(
    ctx: commands.Context, *, anime_base: Optional[str] = None
) -> None:
    await ctx.defer()
    recs = await bot.api.get_anime_recommendations(anime_base)
    if not recs:
        await ctx.send("❌ No pude obtener recomendaciones en este momento, intenta de nuevo en unos segundos.")
        return

    lines = []
    for idx, r in enumerate(recs, start=1):
        extra = (
            f"• 👍 `{r['votes']} votos de similitud`"
            if "votes" in r
            else f"• ⭐ `{r.get('score', 'N/A')}` ({r.get('genres', 'Anime')})"
        )
        lines.append(f"**{idx}. [{r['title']}]({r['url']})** {extra}")

    header = (
        f"Basadas en **{recs[0]['based_on']}**"
        if anime_base and "based_on" in recs[0]
        else "Selección dinámica de animes recomendados"
    )
    embed = discord.Embed(
        title="✨ Recomendaciones de Anime para Ti",
        description=f"*{header}:*\n\n" + "\n".join(lines),
        color=0x9B59B6,
    )
    if recs[0].get("image"):
        embed.set_thumbnail(url=recs[0]["image"])
    await ctx.send(embed=embed)


@bot.hybrid_command(
    name="temporada",
    aliases=["season", "emision"],
    description="Muestra los animes más destacados en emisión durante la temporada actual.",
)
async def cmd_current_season(ctx: commands.Context) -> None:
    await ctx.defer()
    data = await bot.api.fetch_json(f"{JIKAN_BASE_URL}/seasons/now", params={"limit": 8})
    items = data.get("data", []) if data else []
    if not items:
        await ctx.send("❌ No se pudo consultar la temporada actual en este instante.")
        return

    lines = []
    for a in items[:8]:
        lines.append(
            f"• **[{a.get('title')}]({a.get('url')})** — ⭐ `{a.get('score') or 'Nuevo'}` | 🎞️ `{a.get('episodes') or '?'} eps`"
        )
    embed = discord.Embed(
        title="🌸 Animes Destacados de la Temporada Actual",
        description="\n".join(lines),
        color=0xE91E63,
    )
    img = items[0].get("images", {}).get("jpg", {}).get("large_image_url")
    if img:
        embed.set_thumbnail(url=img)
    await ctx.send(embed=embed)


# -----------------------------------------------------------------------------
# 🎮 RECOMENDADOR DE JUEGOS INDIE Y OFERTAS (Steam + FreeToGame + CheapShark)
# -----------------------------------------------------------------------------
class IndieDiscoveryView(discord.ui.View):
    def __init__(self, api: FreeAPIClient) -> None:
        super().__init__(timeout=120)
        self.api = api

    @discord.ui.button(label="🎲 Descubrir Otro Juego Indie", style=discord.ButtonStyle.primary)
    async def next_indie(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.defer()
        game = await self.api.fetch_indie_game_details()
        embed = build_indie_embed(game)
        await interaction.edit_original_response(embed=embed, view=self)


def build_indie_embed(game: Dict[str, Any]) -> discord.Embed:
    embed = discord.Embed(
        title=f"🎮 Recomendación Indie: {game['title']}",
        url=game["url"],
        description=game["short_description"],
        color=0x00B894,
    )
    meta_str = f"`{game['metacritic']}/100`" if game.get("metacritic") else "`Aclamado por la crítica`"
    embed.add_field(
        name="🕹️ Ficha del Juego",
        value=(
            f"🏷️ **Género:** {game['genre']}\n"
            f"👩‍💻 **Desarrollador:** {game['developers']}\n"
            f"💰 **Precio actual en Steam:** {game['price']}\n"
            f"🏆 **Valoración:** {meta_str}\n"
            f"🔗 **Tienda:** [Abrir en Steam]({game['url']})"
        ),
        inline=False,
    )
    embed.add_field(
        name="💡 ¿Por qué jugarlo?",
        value=game["why"],
        inline=False,
    )
    if game.get("image"):
        embed.set_image(url=game["image"])
    embed.set_footer(text="Datos en tiempo real vía Steam Store API")
    return embed


@bot.hybrid_command(
    name="indie",
    aliases=["juego_indie", "recomendar_indie"],
    description="Recomienda una joya de los videojuegos Indie con precios actuales de Steam.",
)
async def cmd_indie_game(ctx: commands.Context) -> None:
    await ctx.defer()
    game = await bot.api.fetch_indie_game_details()
    embed = build_indie_embed(game)
    view = IndieDiscoveryView(bot.api)
    await ctx.send(embed=embed, view=view)


@bot.hybrid_command(
    name="juegos_gratis",
    aliases=["freegames", "f2p"],
    description="Recomienda videojuegos 100% gratuitos usando FreeToGame API.",
)
async def cmd_free_games(
    ctx: commands.Context, categoria: Optional[str] = None
) -> None:
    await ctx.defer()
    games = await bot.api.fetch_free_to_play_games(categoria)
    if not games:
        await ctx.send(
            "❌ No encontré juegos con esa categoría. Categorías válidas de ejemplo: `mmorpg`, `shooter`, `strategy`, `card`, `fighting`, `anime`."
        )
        return

    lines = []
    for g in games:
        lines.append(
            f"• **[{g.get('title')}]({g.get('game_url')})** ({g.get('genre')})\n  _{g.get('short_description', '')[:120]}..._"
        )
    embed = discord.Embed(
        title="🆓 Juegos 100% Gratuitos Recomendados (PC)",
        description="\n\n".join(lines),
        color=0x1ABC9C,
    )
    if games[0].get("thumbnail"):
        embed.set_thumbnail(url=games[0]["thumbnail"])
    embed.set_footer(text="Impulsado por FreeToGame API (Sin costo)")
    await ctx.send(embed=embed)


@bot.hybrid_command(
    name="ofertas_juegos",
    aliases=["ofertas", "deals"],
    description="Busca las mejores ofertas actuales de juegos en PC vía CheapShark API.",
)
async def cmd_game_deals(
    ctx: commands.Context, *, titulo: Optional[str] = None
) -> None:
    await ctx.defer()
    deals = await bot.api.fetch_game_deals(titulo)
    if not deals:
        await ctx.send("❌ No se encontraron ofertas activas para esa búsqueda.")
        return

    lines = []
    for d in deals:
        name = d.get("title", "Juego")
        sale = d.get("salePrice", "0.00")
        normal = d.get("normalPrice", "0.00")
        savings = int(float(d.get("savings", 0)))
        deal_id = d.get("dealID", "")
        deal_url = f"https://www.cheapshark.com/redirect?dealID={deal_id}"
        lines.append(
            f"🔥 **[{name}]({deal_url})** — **${sale} USD** ~~(${normal})~~ `-{savings}%`"
        )

    embed = discord.Embed(
        title="💸 Cazador de Ofertas de Videojuegos (Steam / GOG / Humble)",
        description="\n".join(lines),
        color=0x2ECC71,
    )
    if deals[0].get("thumb"):
        embed.set_thumbnail(url=deals[0]["thumb"])
    embed.set_footer(text="Datos en tiempo real vía CheapShark Public API")
    await ctx.send(embed=embed)


# -----------------------------------------------------------------------------
# 🎵 COMANDOS DE MÚSICA Y VIDEOS DE YOUTUBE (yt-dlp + FFmpeg + Piped)
# -----------------------------------------------------------------------------
@bot.hybrid_command(
    name="youtube",
    aliases=["yt", "video"],
    description="Busca un video en YouTube y lo publica en el chat para verlo al instante.",
)
async def cmd_youtube_search(ctx: commands.Context, *, busqueda: str) -> None:
    await ctx.defer()
    video = await search_youtube_free(bot.api, busqueda)
    if not video:
        await ctx.send(f"❌ No pude encontrar resultados de YouTube para **`{busqueda}`**.")
        return

    mins, secs = divmod(int(video.get("duration") or 0), 60)
    await ctx.send(
        f"📺 **{video['title']}** (`{mins}:{secs:02d}`) — Subido por **{video['uploader']}**\n{video['webpage_url']}"
    )


async def _advance_music(guild, bot_instance):
    mq = bot_instance.get_music_queue(guild.id)
    vc = guild.voice_client
    if not vc or not vc.is_connected() or vc.is_playing() or vc.is_paused():
        return
    from emi_audio import persist
    if mq.current and not getattr(mq, 'skip_once', False):
        if getattr(mq, 'repeat', 'off') == 'pista':
            mq.queue.insert(0, mq.current)
        elif getattr(mq, 'repeat', 'off') == 'cola':
            mq.queue.append(mq.current)
    mq.skip_once = False
    mq.current = None
    while mq.queue:
        item = mq.queue.pop(0)
        track = await search_youtube_free(bot_instance.api, item['webpage_url'])
        if not vc.is_connected():
            return
        if not track or not track.get('stream_url'):
            continue
        mq.current = track
        try:
            options = dict(FFMPEG_OPTIONS)
            offset = int(item.get('offset', 0))
            if offset:
                options['before_options'] += f' -ss {offset}'
            source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(track['stream_url'], executable=ffmpeg_path(), **options), volume=getattr(mq, 'volume', .5))
            vc.play(source, after=lambda err: _play_next_in_guild(guild, bot_instance))
            persist(bot_instance, guild.id)
            return
        except Exception:
            logger.exception('No se pudo reproducir una pista')
    mq.current = None
    persist(bot_instance, guild.id)


def _play_next_in_guild(guild, bot_instance):
    async def advance():
        mq = bot_instance.get_music_queue(guild.id)
        if not hasattr(mq, 'lock'):
            mq.lock = asyncio.Lock()
        async with mq.lock:
            await _advance_music(guild, bot_instance)
    asyncio.run_coroutine_threadsafe(advance(), bot_instance.loop)


@bot.hybrid_command(
    name="play",
    aliases=["p", "musica"],
    description="Reproduce música o el audio de un video de YouTube en tu canal de voz.",
)
async def cmd_play(ctx: commands.Context, *, busqueda_o_url: str) -> None:
    if not ctx.interaction or not ctx.interaction.response.is_done():
        await ctx.defer()
    if not ctx.author.voice or not ctx.author.voice.channel:
        await ctx.send("❌ Primero debes unirte a un canal de voz para escuchar música.")
        return

    if yt_dlp is None:
        await ctx.send("⚠️ La librería `yt-dlp` no está instalada. Ejecuta `pip install yt-dlp PyNaCl` y asegúrate de tener `ffmpeg` instalado.")
        return

    voice_channel = ctx.author.voice.channel
    vc = ctx.voice_client
    if not vc:
        vc = await voice_channel.connect()
    elif vc.channel != voice_channel:
        await ctx.send("Únete al canal donde ya está sonando la música.")
        return

    track = await search_youtube_free(bot.api, busqueda_o_url)
    if not track or not track.get("stream_url"):
        await ctx.send("❌ No se pudo extraer el stream de audio para esa búsqueda.")
        return

    mq = bot.get_music_queue(ctx.guild.id)
    mq.queue.append(track)
    from emi_audio import persist
    persist(bot, ctx.guild.id)

    if not vc.is_playing() and not vc.is_paused():
        _play_next_in_guild(ctx.guild, bot)
        embed = discord.Embed(
            title="🎶 Reproduciendo Ahora",
            description=f"**[{track['title']}]({track['webpage_url']})**\n👤 Canal: {track['uploader']}",
            color=0xE74C3C,
        )
    else:
        embed = discord.Embed(
            title="➕ Añadido a la Cola de Reproducción",
            description=f"**[{track['title']}]({track['webpage_url']})**\nPosición en cola: `#{len(mq.queue)}`",
            color=0x3498DB,
        )

    if track.get("thumbnail"):
        embed.set_thumbnail(url=track["thumbnail"])
    await ctx.send(embed=embed)


@bot.hybrid_command(
    name="cola",
    aliases=["queue", "q"],
    description="Muestra las canciones pendientes en la cola de reproducción.",
)
async def cmd_queue(ctx: commands.Context) -> None:
    mq = bot.get_music_queue(ctx.guild.id)
    if not mq.current and not mq.queue:
        await ctx.send("📭 La cola de reproducción está vacía.")
        return

    desc = ""
    if mq.current:
        desc += f"▶️ **Sonando ahora:** [{mq.current['title']}]({mq.current['webpage_url']})\n\n"
    if mq.queue:
        desc += "**Próximas pistas:**\n" + "\n".join(
            f"`{i+1}.` [{t['title']}]({t['webpage_url']})"
            for i, t in enumerate(mq.queue[:10])
        )
    embed = discord.Embed(title="🎵 Cola de Música del Servidor", description=desc, color=0x9B59B6)
    await ctx.send(embed=embed)


@bot.hybrid_command(name="saltar", aliases=["skip", "s"], description="Salta la canción actual.")
async def cmd_skip(ctx: commands.Context) -> None:
    if ctx.voice_client and (ctx.voice_client.is_playing() or ctx.voice_client.is_paused()):
        bot.get_music_queue(ctx.guild.id).skip_once = True
        ctx.voice_client.stop()
        await ctx.send("⏭️ Canción saltada.")
    else:
        await ctx.send("❌ No hay ninguna canción reproduciéndose.")


@bot.hybrid_command(name="pausa", aliases=["pause"], description="Pausa la música actual.")
async def cmd_pause(ctx: commands.Context) -> None:
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.pause()
        await ctx.send("⏸️ Música pausada.")
    else:
        await ctx.send("❌ No hay música sonando en este momento.")


@bot.hybrid_command(name="reanudar", aliases=["resume"], description="Reanuda la música pausada.")
async def cmd_resume(ctx: commands.Context) -> None:
    if ctx.voice_client and ctx.voice_client.is_paused():
        ctx.voice_client.resume()
        await ctx.send("▶️ Música reanudada.")
    else:
        await ctx.send("❌ La música no está en pausa.")


@bot.hybrid_command(
    name="salir",
    aliases=["stop", "leave", "disconnect"],
    description="Detiene la música, limpia la cola y desconecta al bot del canal de voz.",
)
async def cmd_leave(ctx: commands.Context) -> None:
    if ctx.voice_client:
        mq = bot.get_music_queue(ctx.guild.id)
        mq.queue.clear()
        mq.current = None
        from emi_audio import persist
        persist(bot, ctx.guild.id)
        await ctx.voice_client.disconnect()
        await ctx.send("👋 Desconectado del canal de voz y cola limpiada.")
    else:
        await ctx.send("❌ No estoy conectado a ningún canal de voz.")


# -----------------------------------------------------------------------------
# 📚 WIKIS, TRIVIA Y REACCIONES DE ANIME
# -----------------------------------------------------------------------------
@bot.hybrid_command(
    name="wiki",
    aliases=["fandom", "wikipedia"],
    description="Busca artículos en Wikipedia o en Wikis de Fandom (onepiece, naruto, hollowknight, etc.).",
)
async def cmd_wiki(
    ctx: commands.Context,
    termino: str,
    fuente: Optional[str] = "wikipedia_es",
) -> None:
    await ctx.defer()
    res = await bot.api.search_mediawiki(termino, fuente or "wikipedia_es")
    if not res:
        available = ", ".join(f"`{k}`" for k in FANDOM_WIKIS.keys())
        await ctx.send(
            f"❌ No encontré artículos para **`{termino}`** en `{fuente}`.\nFuentes disponibles: {available}"
        )
        return

    embed = discord.Embed(
        title=f"📚 Wiki ({res['wiki']}): {res['title']}",
        url=res["url"],
        description=res["extract"],
        color=0x3498DB,
    )
    if res.get("image"):
        embed.set_thumbnail(url=res["image"])
    embed.set_footer(text="Datos extraídos en vivo vía MediaWiki Action API")
    await ctx.send(embed=embed)


@bot.hybrid_command(
    name="trivia",
    aliases=["quiz"],
    description="Responde una pregunta de trivia sobre Anime o Juegos Indie para ganar monedas.",
)
async def cmd_trivia(ctx: commands.Context) -> None:
    item = random.choice(TRIVIA_BANK)
    embed = discord.Embed(
        title=f"🧠 Trivia Otaku & Indie ({item['category']})",
        description=f"**{item['question']}**\n\n*¡El primero en responder correctamente gana **+90 🪙 Monedas Otaku**!*",
        color=0xF1C40F,
    )
    view = TriviaView(bot.db, item)
    await ctx.send(embed=embed, view=view)


@bot.hybrid_command(
    name="reaccion",
    aliases=["gif", "hug", "pat", "slap"],
    description="Envía un GIF de reacción de anime (hug, pat, slap, wave, dance, smile, cry).",
)
async def cmd_reaction(
    ctx: commands.Context,
    accion: str = "hug",
    usuario: Optional[discord.Member] = None,
) -> None:
    await ctx.defer()
    data = await bot.api.fetch_anime_reaction(accion)
    target_txt = f" a **{usuario.display_name}**" if usuario else ""
    embed = discord.Embed(
        description=f"✨ **{ctx.author.display_name}** aplica `{accion}`{target_txt} • *(Anime: {data['anime_name']})*",
        color=0xFF69B4,
    )
    embed.set_image(url=data["url"])
    await ctx.send(embed=embed)


# =============================================================================
# 🚀 PUNTO DE ENTRADA
# =============================================================================
if __name__ == "__main__":
    if not DISCORD_TOKEN or DISCORD_TOKEN in ("TU_TOKEN_DE_DISCORD_AQUI", "PEGA_TU_TOKEN_AQUI"):
        banner = "=" * 65
        print(f"\n{banner}\n⚠️  AVISO IMPORTANTE:\n   Abre el archivo '.env' en esta carpeta y coloca tu Token de Discord:\n   DISCORD_TOKEN=tu_token_aqui\n{banner}\n")
    else:
        bot.run(DISCORD_TOKEN)
