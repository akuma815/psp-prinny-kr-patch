#!/usr/bin/env python3
"""Rebuild frozen v2.3 text/code/font from source; recover frozen art from pinned release."""
from pathlib import Path
import argparse
import csv
from dataclasses import replace
import hashlib
import json
import shutil
import struct
import subprocess
import urllib.request
import zipfile

import demo00
import build_demo00_production as prod
import build_dialog_typewriter_patch as renderer
import build_boot_ui_runtime_patch as ui
import build_direct_run as direct
import build_font_poc
import font_assets
import start_tables
import lucky_doll
import picture_book
import integrate_stage_info_iso as stage
import build_dlc_kr as dlc
import compress_nis_lzs
import decompress_nis_lzs
import build_iso_production as iso
from build_translated_images_iso import (
    replace_start_fixed, replace_nispack_in_place, parse_nispack,
    nispack_payload, read_start_entries,
)
from restore_graphics_sources import restore

WORKSPACE = Path(__file__).resolve().parents[1]
ISO_SOURCE = 'af0d2873a96c5fe6f95b3fc2fb3e8702f98bba67e32f2f78c5c3d1bdaa8b9d03'
ISO_FINAL = 'ae53bc4b960b263a362756e801c21da7224ce3dd735d2da5882c04a0248622ac'
FONT = 'f6682e2027b1a382d3e01546f7a7115cb26cc1245ded6b839686a069abc743b0'
ZIP_HASH = '59cdf7c4d2f5545bd8a6c6a7cfeb7e1ddffbe7b23207d31ebc4c36d0c601b348'
RELEASE_URL = 'https://github.com/akuma815/psp-prinny-kr-patch/releases/download/v2.3/Prinny_KR_Patch_20260803.zip'
DLC_HASHES = {
    'DL0000.EDAT': ('a0209702de5210b2f35c57e7c12bfddbeb691200de06769b615ca50254d48c1b', '2a2fb6a26ad40aa7ef2bfd46795657416e4d45723f7b04b3a30e76e715b83739'),
    'DL0001.EDAT': ('86b48d56b6ba853f09ffb0a524ccebf4f601c78cb0f4937cb885ec8815bdb7a7', '4d3f0b113670c532cab6233c08309b000a34622673730cfd1b8d12dc6e503ccc'),
    'DL0002.EDAT': ('3fbc26ed99c1b3f474e50dd5290eb0497e61f0a7e8e9268fb82980a426079be9', 'fb6b75f3f60da7233eea63a229512a0762e3b789c7204c5e22d0d837677435ae'),
}


def load(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def rows(path):
    with path.open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def digest(data):
    return hashlib.sha256(data).hexdigest()


def require_hash(path, expected):
    actual = iso.sha256_file(path)
    if actual != expected:
        raise ValueError(f'SHA-256 mismatch: {path}: {actual}, expected {expected}')
    return actual


def iso_files(path, directory='/', result=None):
    result = {} if result is None else result
    for positioned in iso.positioned_children(path, iso.locate_directory(path, directory)):
        record = positioned.record
        if record.name in ('.', '..'):
            continue
        name = iso._normalized_name(record.name)
        if Path(name).name != name or name in ('', '.', '..'):
            raise ValueError('unsafe ISO filename')
        child = directory.rstrip('/') + '/' + name
        if record.is_directory:
            iso_files(path, child, result)
        else:
            result[child] = positioned
    return result


def extract(path, output):
    inventory = iso_files(path)
    for name, positioned in inventory.items():
        target = output / name.lstrip('/')
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(iso.read_region(path, positioned.record.offset, positioned.record.size))
    system = (output / 'PSP_GAME/USRDIR/SYSTEM.DAT').read_bytes()
    slot = nispack_payload(system, next(x for x in parse_nispack(system) if x['name'] == 'start.lzs'))
    logical = struct.unpack_from('<I', slot, 8)[0] + 4
    start, extension = decompress_nis_lzs.decompress(slot[:logical])
    if extension != 'dat':
        raise ValueError('unexpected start.lzs extension')
    (output / 'start.dat').write_bytes(start)
    assets = output / 'start_assets'
    assets.mkdir()
    for entry in read_start_entries(start)[1]:
        if Path(entry.name).name != entry.name:
            raise ValueError('unsafe start.dat filename')
        (assets / entry.name).write_bytes(start[entry.data_start:entry.data_end])
    return inventory


def text_payloads(original, frozen, font_path):
    mapping_rows = load(WORKSPACE / 'config/locked_mapping.json')['entries']
    if len(mapping_rows) != 998:
        raise ValueError('frozen character mapping changed')
    mapping = {r['character']: bytes.fromhex(r['cp932_hex']) for r in mapping_rows}
    profile = load(WORKSPACE / 'config/demo00_production_profile.json')
    assets = original / 'start_assets'
    replacements = {}
    table = demo00.parse((assets / 'Demo00.dat').read_bytes())
    byid = {r.record_id: r for r in table.records}
    records = list(table.records)
    for entry in load(WORKSPACE / 'text/demo00_translation.json')['entries']:
        translation = entry['translation']
        if translation['status'] == 'untranslated':
            continue
        if translation['status'] != 'complete':
            raise ValueError('incomplete Demo00 translation')
        record = byid[int(entry['entry_id'].split('/')[1], 16)]
        if record.to_bytes().hex() != entry['protected']['raw_hex']:
            raise ValueError('protected Demo00 source changed')
        records[record.index] = replace(record,
            speaker_raw=prod.encode_slot(translation['speaker'], demo00.SPEAKER_SIZE, mapping, entry['entry_id']),
            lines_raw=tuple(prod.encode_slot(x, demo00.LINE_SIZE, mapping, entry['entry_id']) for x in translation['lines']))
    replacements['Demo00.dat'] = demo00.Table(tuple(records), table.footer).to_bytes()
    boot, _ = renderer.patch_executable((original / 'PSP_GAME/SYSDIR/BOOT.BIN').read_bytes(), 6, 9)
    boot = bytearray(boot)
    for entry in load(WORKSPACE / 'text/boot_ui_translation.json')['entries']:
        offset = int(entry['offset'], 0)
        source = entry['source'].encode('cp932')
        size = ui.slot_size(len(source))
        if boot[offset:offset + len(source)] != source:
            raise ValueError('protected BOOT UI source changed')
        encoded = ui.encode_text(entry['translation'], mapping)
        if len(encoded) >= size:
            raise ValueError('BOOT translation exceeds slot')
        boot[offset:offset + size] = encoded + bytes(size - len(encoded))
    fnt = bytearray((assets / 'font.fnt').read_bytes())
    txp = bytearray((assets / 'font.txp').read_bytes())
    for row in mapping_rows:
        struct.pack_into('<H', fnt, 2 + font_assets.dense_cp932_index(bytes.fromhex(row['cp932_hex'])) * 2, row['glyph_id'])
        raw = build_font_poc.pack_4bpp_low_first(build_font_poc.rasterize(row['character'], font_path, profile), 8)
        pos = 0x50 + row['glyph_id'] * 140
        txp[pos:pos + 140] = raw
    replacements.update({'font.fnt': bytes(fnt), 'font.txp': bytes(txp)})
    text = WORKSPACE / 'text/translation'
    replacements['StageInfo00.dat'] = stage.patch_stage_info((assets / 'StageInfo00.dat').read_bytes(), stage.load_stage_rows(text / 'stage_info.csv'), mapping)[0]
    replacements['LuckyDoll.dat'] = lucky_doll.patch((assets / 'LuckyDoll.dat').read_bytes(), lucky_doll.load_rows(text / 'lucky_doll.csv'), mapping)[0]
    replacements['PictureBook.dat'] = picture_book.patch((assets / 'PictureBook.dat').read_bytes(), picture_book.load_rows(text / 'picture_book_ko_translated.csv'), mapping)[0]
    for name, filename in [('LuckyItem.dat', 'lucky_item_ko_translated.csv'), ('Collection.dat', 'collection_ko_translated.csv'), ('Honor.dat', 'honor_ko_translated.csv'), ('MusicShop.dat', 'music_shop_ko_translated.csv')]:
        replacements[name] = start_tables.patch(name, (assets / name).read_bytes(), start_tables.load_rows(text / filename, name), mapping)[0]
    replacements['ClearTime00.dat'] = direct.patch_clear_time((assets / 'ClearTime00.dat').read_bytes(), load(text / 'clear_time.json'), mapping)[0]
    fwd, rev, _ = direct.patch_unicode_tables((assets / 'jis2ucs.bin').read_bytes(), (assets / 'ucs2jis.bin').read_bytes(), mapping_rows[:987])
    replacements.update({'jis2ucs.bin': fwd, 'ucs2jis.bin': rev})
    for name in ('anime00.dat', 'number.txp'):
        replacements[name] = (frozen / 'start_assets' / name).read_bytes()
    start = replace_start_fixed((original / 'start.dat').read_bytes(), replacements)
    compressed, _ = compress_nis_lzs.compress(start, extension='dat', flag=0xD5)
    system = (original / 'PSP_GAME/USRDIR/SYSTEM.DAT').read_bytes()
    slot = nispack_payload(system, next(e for e in parse_nispack(system) if e['name'] == 'start.lzs'))
    if len(compressed) > len(slot):
        raise ValueError('compressed start.dat exceeds original slot')
    system = replace_nispack_in_place(system, {'start.lzs': compressed + bytes(len(slot) - len(compressed))})
    payloads = {'/PSP_GAME/SYSDIR/BOOT.BIN': bytes(boot), '/PSP_GAME/SYSDIR/EBOOT.BIN': bytes(boot), '/PSP_GAME/USRDIR/SYSTEM.DAT': system}
    for name in ('ANIME.DAT', 'BG.DAT', 'STAGE.DAT'):
        payloads['/PSP_GAME/USRDIR/' + name] = (frozen / 'PSP_GAME/USRDIR' / name).read_bytes()
    return payloads, mapping


def assemble(original, output, payloads):
    inventory = iso_files(original)
    plan = []
    for name, payload in payloads.items():
        positioned = inventory[name]
        record = positioned.record
        if len(payload) > iso.align(record.size, 2048):
            raise ValueError('replacement exceeds ISO extent: ' + name)
        plan.append((record.offset, record.offset + max(record.size, len(payload)), name, payload, positioned.record_offset + 10))
    ranges = sorted([(a, b) for a, b, *_ in plan] + [(p, p + 8) for *_, p in plan])
    if any(a[1] > b[0] for a, b in zip(ranges, ranges[1:])):
        raise ValueError('planned ISO writes overlap')
    shutil.copyfile(original, output)
    with output.open('r+b') as stream:
        for begin, end, name, payload, size_pos in plan:
            stream.seek(begin)
            stream.write(payload + bytes(end - begin - len(payload)))
            iso.write_both_endian_u32(stream, size_pos, len(payload))
    # Prove every changed byte is inside the predeclared data/directory ranges.
    with original.open('rb') as before, output.open('rb') as after:
        cursor = 0
        for begin, end in ranges + [(original.stat().st_size, original.stat().st_size)]:
            remaining = begin - cursor
            while remaining:
                count = min(1024 * 1024, remaining)
                if before.read(count) != after.read(count):
                    raise ValueError('unplanned ISO change')
                remaining -= count
            before.seek(end)
            after.seek(end)
            cursor = end
    actual = iso_files(output)
    if inventory.keys() != actual.keys():
        raise ValueError('ISO file list changed')
    logical = []
    for name, item in actual.items():
        expected = digest(payloads[name]) if name in payloads else iso.hash_region(original, inventory[name].record.offset, inventory[name].record.size)
        sha = iso.hash_region(output, item.record.offset, item.record.size)
        if sha != expected:
            raise ValueError('ISO logical file mismatch: ' + name)
        logical.append({'path': name, 'sha256': sha, 'source_generated': name in payloads and name.endswith(('BOOT.BIN', 'EBOOT.BIN', 'SYSTEM.DAT'))})
    return logical, [{'offset': a, 'end': b} for a, b in ranges]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--original-iso', required=True, type=Path)
    parser.add_argument('--original-dlc-dir', required=True, type=Path)
    parser.add_argument('--font', required=True, type=Path)
    parser.add_argument('--xdelta', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path, help='New empty directory; contains local ROM data. Never commit it.')
    parser.add_argument('--release-zip', type=Path, help='Pinned v2.3 ZIP; downloaded automatically if omitted')
    parser.add_argument('--candidate', action='store_true', help='Use current DLC spelling; output is an unverified candidate, not frozen final')
    args = parser.parse_args()
    original = args.original_iso.resolve()
    require_hash(original, ISO_SOURCE)
    require_hash(args.font, FONT)
    for name, hashes in DLC_HASHES.items():
        require_hash(args.original_dlc_dir / name, hashes[0])
    out = args.output.resolve()
    if out.exists() and any(out.iterdir()):
        raise ValueError('output directory must be empty')
    out.mkdir(parents=True, exist_ok=True)
    archive = args.release_zip
    if archive is None:
        archive = out / 'pinned_v2.3.zip'
        urllib.request.urlretrieve(RELEASE_URL, archive)
    require_hash(archive, ZIP_HASH)
    patch = out / 'main.xdelta'
    with zipfile.ZipFile(archive) as z:
        matches = [n for n in z.namelist() if n.endswith('/Prinny_ULJS00150_KR_20260803.xdelta') or n == 'Prinny_ULJS00150_KR_20260803.xdelta']
        if len(matches) != 1:
            raise ValueError('release main patch missing or ambiguous')
        patch.write_bytes(z.read(matches[0]))
    frozen_iso = out / 'pinned_final.iso'
    subprocess.run([str(args.xdelta.resolve()), '-d', '-s', str(original), str(patch), str(frozen_iso)], check=True)
    require_hash(frozen_iso, ISO_FINAL)
    print('Extracting supported original and frozen art...', flush=True)
    extract(original, out / 'original')
    extract(frozen_iso, out / 'frozen')
    author_images = restore(WORKSPACE / 'graphics/restore/author_rgba_deltas.json', out / 'original', out / 'editable_author_images')
    print(f'Restored {len(author_images)} author images; rebuilding text/code/font...', flush=True)
    payloads, mapping = text_payloads(out / 'original', out / 'frozen', args.font)
    output_iso = out / ('Prinny_KR_candidate.iso' if args.candidate else 'Prinny_KR_final.iso')
    logical, ranges = assemble(original, output_iso, payloads)
    output_hash = iso.sha256_file(output_iso)
    if not args.candidate:
        require_hash(output_iso, ISO_FINAL)
    dlc_results = []
    dlc_out = out / 'patched_dlc/ULJS00150'
    dlc_out.mkdir(parents=True)
    overrides = load(WORKSPACE / 'config/frozen_dlc_overrides.json')
    for name, hashes in DLC_HASHES.items():
        filename = name[:6].lower() + '_ddem.csv'
        translated = rows(WORKSPACE / 'text/translation/dlc' / filename)
        if not args.candidate:
            for override in (r for r in overrides if r['file'] == filename):
                row = next(r for r in translated if r['entry_id'] == override['entry_id'])
                if row[override['field']] != override['source']:
                    raise ValueError('frozen source spelling changed; use --candidate for edits')
                row[override['field']] = override['frozen_release']
        payload, _ = dlc.patch_ddem((args.original_dlc_dir / name).read_bytes(), translated, mapping)
        payload, _ = dlc.patch_dsti(payload, rows(WORKSPACE / 'text/translation/dlc/dlc_stage_info.csv'), mapping)
        target = dlc_out / name
        target.write_bytes(payload)
        if not args.candidate:
            require_hash(target, hashes[1])
        dlc_results.append({'name': name, 'sha256': digest(payload), 'frozen_equal': digest(payload) == hashes[1]})
    param = args.original_dlc_dir / 'PARAM.PBP'
    param_hash = None
    if param.exists():
        shutil.copyfile(param, dlc_out / param.name)
        param_hash = require_hash(dlc_out / param.name, iso.sha256_file(param))
    # Final checks prove original media were not modified.
    require_hash(original, ISO_SOURCE)
    for name, hashes in DLC_HASHES.items():
        require_hash(args.original_dlc_dir / name, hashes[0])
    report = {'schema_version': 1, 'profile': 'candidate_unverified' if args.candidate else 'frozen_v2.3',
        'iso_sha256': output_hash, 'iso_frozen_equal': output_hash == ISO_FINAL,
        'dlc': dlc_results, 'originals_unchanged': True, 'logical_iso_files': logical,
        'param_pbp_unchanged_sha256': param_hash,
        'expected_iso_write_ranges': ranges, 'author_images_rgba_verified': author_images,
        'font_sha256': FONT, 'pinned_release_zip_sha256': ZIP_HASH,
        'source_generated': ['BOOT/EBOOT', 'Demo00', '13 start text/font/table members including Demo00', 'DLC DDEM/DSTI'],
        'frozen_graphics': ['ANIME.DAT', 'BG.DAT', 'STAGE.DAT', 'start.dat/anime00.dat', 'start.dat/number.txp'],
        'runtime_qa_performed': False}
    (out / 'rebuild_report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('PASS: ' + report['profile'] + ' ' + output_hash, flush=True)


if __name__ == '__main__':
    main()
