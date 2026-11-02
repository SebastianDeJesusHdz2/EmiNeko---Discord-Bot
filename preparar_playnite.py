from pathlib import Path
import json
root=Path(__file__).resolve().parent
(root/'data').mkdir(exist_ok=True)
(root/'.secrets').mkdir(exist_ok=True)
config=root/'playnite_bridge'/'config.json'
config.write_text(json.dumps({'output':str(root/'data'/'playnite.json')},indent=2),encoding='utf-8')
print('Puente preparado. Copia playnite_bridge a Extensions de Playnite.')
