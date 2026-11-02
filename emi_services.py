"""Adaptadores externos; ninguna credencial se imprime ni se envía a Discord."""
import asyncio
import io
import json
import os
from pathlib import Path
import re
import warnings
import aiohttp

ROOT=Path(__file__).resolve().parent

class ServiceError(ValueError): pass

class Services:
    def __init__(self,session_factory): self.session_factory=session_factory
    async def json(self,url,params=None,headers=None,body=None):
        session=await self.session_factory()
        try:
            async with session.request('POST' if body is not None else 'GET',url,params=params,headers=headers,json=body,timeout=aiohttp.ClientTimeout(total=90)) as response:
                if response.status!=200: raise ServiceError(f'El proveedor respondió HTTP {response.status}. Revisa credenciales, cuota y disponibilidad.')
                return await response.json()
        except (aiohttp.ClientError,asyncio.TimeoutError): raise ServiceError('El proveedor no está disponible o agotó el tiempo de espera.') from None
    async def tmdb(self,path,params=None):
        token=os.getenv('TMDB_TOKEN','')
        if not token: raise ServiceError('Configura TMDB_TOKEN (API Read Access Token); consulta PASO_A_PASO.md.')
        return await self.json('https://api.themoviedb.org/3/'+path,params={'language':'es-MX',**(params or {})},headers={'Authorization':'Bearer '+token})
    async def price(self,gameid):
        data=await self.json('https://www.cheapshark.com/api/1.0/games',params={'id':gameid})
        deals=data.get('deals',[])
        if not deals: raise ServiceError('No hay ofertas disponibles para ese gameID de CheapShark.')
        cheapest=min(deals,key=lambda x:float(x['price']))
        return data.get('info',{}).get('title',gameid),float(cheapest['price']),cheapest.get('dealID','')

def video_id(url):
    from urllib.parse import urlparse,parse_qs
    parsed=urlparse(url)
    if parsed.scheme!='https' or parsed.hostname not in ('youtube.com','www.youtube.com','m.youtube.com','youtu.be'): return None
    value=parsed.path.strip('/') if parsed.hostname=='youtu.be' else parse_qs(parsed.query).get('v',[''])[0]
    if not value and parsed.path.startswith(('/shorts/','/embed/')): value=parsed.path.split('/')[2]
    return value if re.fullmatch(r'[a-zA-Z0-9_-]{11}',value or '') else None

def photo_bytes(data):
    from PIL import Image,ImageOps,ExifTags
    Image.MAX_IMAGE_PIXELS=30_000_000
    with warnings.catch_warnings():
        warnings.simplefilter('error',Image.DecompressionBombWarning)
        try:
            with Image.open(io.BytesIO(data)) as image:
                image.load()
                metadata={ExifTags.TAGS.get(k,str(k)):str(v)[:200] for k,v in image.getexif().items() if ExifTags.TAGS.get(k) in ('Make','Model','LensModel','ExposureTime','FNumber','ISOSpeedRatings','PhotographicSensitivity','FocalLength')}
                metadata.update(width=image.width,height=image.height)
                image=ImageOps.exif_transpose(image).convert('RGB'); image.thumbnail((2400,2400))
                out=io.BytesIO(); image.save(out,format='JPEG',quality=90)
                return out.getvalue(),metadata
        except (OSError,ValueError,Image.DecompressionBombError,Image.DecompressionBombWarning):
            raise ServiceError('Imagen inválida o demasiado grande. Usa JPEG/PNG/WebP de hasta 30 megapíxeles.') from None
