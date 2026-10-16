"""Restore editable RGBA author images from supported original media and XOR deltas."""
from pathlib import Path
import base64
import hashlib
import json
import zlib
from PIL import Image
import anime_assets
import txp_assets
from build_translated_images_iso import parse_anime_asset, parse_nispack, nispack_payload


def original_image(asset_id, original):
    container, member = asset_id.split('/', 1)
    if container == 'BG.DAT':
        data = (original / 'PSP_GAME/USRDIR/BG.DAT').read_bytes()
        item = next(x for x in parse_nispack(data) if x['name'] == member)
        return txp_assets.decode_txp(nispack_payload(data, item))
    if container == 'start.dat' and '/' not in member:
        return txp_assets.decode_txp((original / 'start_assets' / member).read_bytes())
    entry, record, texture = parse_anime_asset(member)
    if container == 'ANIME.DAT':
        data = (original / 'PSP_GAME/USRDIR/ANIME.DAT').read_bytes()
        item = next(x for x in parse_nispack(data) if x['name'] == entry)
        data = nispack_payload(data, item)
    elif container == 'start.dat':
        data = (original / 'start_assets' / entry).read_bytes()
    else:
        raise ValueError(asset_id)
    return anime_assets.decode_texture(data, anime_assets.parse_records(data)[record], texture)


def restore(manifest, original, output):
    document = json.loads(manifest.read_text(encoding='utf-8'))
    output.mkdir(parents=True, exist_ok=True)
    results = []
    for row in document['images']:
        image = original_image(row['asset_id'], original).convert('RGBA')
        raw = image.tobytes()
        if list(image.size) != row['size'] or hashlib.sha256(raw).hexdigest() != row['original_rgba_sha256']:
            raise ValueError('original texture mismatch: ' + row['asset_id'])
        delta = zlib.decompress(base64.b64decode(row['xor_zlib_base64']))
        if len(delta) != len(raw):
            raise ValueError('RGBA delta length mismatch')
        restored = bytes(a ^ b for a, b in zip(raw, delta))
        if hashlib.sha256(restored).hexdigest() != row['author_rgba_sha256']:
            raise ValueError('author pixels mismatch')
        name = row['filename']
        if Path(name).name != name or not name.endswith('.png'):
            raise ValueError('unsafe author image filename')
        Image.frombytes('RGBA', image.size, restored).save(output / name)
        results.append({'filename': name, 'rgba_sha256': row['author_rgba_sha256']})
    return results
