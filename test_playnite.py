"""Comprueba importación, actualización, aislamiento y vista predeterminada de Playnite."""
import asyncio
import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from emi_domain import Domain
from emineko import Emi
from vincular_playnite import Config, Sync

class BridgeTests(unittest.IsolatedAsyncioTestCase):
    async def test_export_to_private_library(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            root=Path(folder)
            store=Domain(root/'test.db')
            file=root/'playnite.json'
            games=[dict(id='abcd', name='Ejemplo', source='Epic', minutes=0,genres=[],status='pendiente')]
            file.write_text(json.dumps({'games':games}),encoding='utf-8-sig')
            owner=123456789012345678
            config=Config(file,owner)
            sync=Sync(store)
            self.assertEqual({'Epic':1},sync.run(config))
            self.assertIsNone(sync.run(config))
            file.write_text('{',encoding='utf-8')
            with self.assertRaises(ValueError): sync.run(config)
            games.append(dict(id='efgh',name='Otro',source='Xbox'))
            file.write_text(json.dumps({'games':games}),encoding='utf-8')
            self.assertEqual({'Epic':1,'Xbox':1},sync.run(config))
            self.assertEqual(2,len(store.list(owner,0,'biblioteca')))
            self.assertFalse(store.list(owner+1,0,'biblioteca'))
            ctx=SimpleNamespace(author=SimpleNamespace(id=owner),interaction=True,defer=AsyncMock())
            bridge=SimpleNamespace(sync_bridge=AsyncMock())
            cog=SimpleNamespace(store=store,bot=SimpleNamespace(get_cog=lambda name:bridge),panel=AsyncMock())
            with patch('vincular_playnite.settings',return_value=config):
                await Emi.records(cog,ctx,'biblioteca','ver','','Epic',0)
                bridge.sync_bridge.assert_awaited_once()
                self.assertIn('1 juegos',cog.panel.await_args.args[1])
                self.assertIn('Epic',cog.panel.await_args.args[2][0])
                ctx.author.id=owner+1
                await Emi.records(cog,ctx,'biblioteca','ver','','',0)
                bridge.sync_bridge.assert_awaited_once()
                self.assertIn('0 juegos',cog.panel.await_args.args[1])
