#!/usr/bin/env python3
"""Builds assets/creatives/creatives.json for the #creatives section.

Folder layout (one folder per creative, folders starting with "_" are skipped):
  assets/creatives/_summary/summary.md        totals strip (orders, revenue, currency, period, image)
  assets/creatives/_summary/tw-total-sales.png
  assets/creatives/<slug>/meta.md              key: value fields, see _example/meta.md
  assets/creatives/<slug>/ad.(mp4|jpg|png|webp)
  assets/creatives/<slug>/tw.(png|jpg|webp)    Triple Whale proof (required)
  assets/creatives/<slug>/brief.(png|pdf|md), template.(png|pdf), sample.(png|mp4)

A creative is published only when tw.* exists and orders, cpa and roas are filled
(no [PREENCHER]). Check every number against tw.* before you commit.

Usage:
  python3 scripts/build_creatives.py             build the JSON
  python3 scripts/build_creatives.py --optimize  also convert images to WebP (max 1440px)
                                                 and videos to 720p H.264 under ~3 MB
"""
import json, re, shutil, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / 'assets' / 'creatives'
IMG = ('.png', '.jpg', '.jpeg', '.webp')
VID = ('.mp4', '.mov', '.webm')
PH = '[PREENCHER'


def parse(md):
    out = {}
    for line in md.read_text(encoding='utf-8').splitlines():
        m = re.match(r'^\s*([a-z_]+)\s*:\s*(.*)$', line)
        if m:
            out[m.group(1)] = m.group(2).strip()
    return out


def filled(v):
    return bool(v) and PH not in v


def find(folder, stem, exts):
    for e in exts:
        f = folder / (stem + e)
        if f.exists():
            return f
    return None


def to_webp(f, max_w=1440):
    from PIL import Image
    if f.suffix == '.webp':
        return f
    out = f.with_suffix('.webp')
    im = Image.open(f)
    im = im.convert('RGBA' if im.mode in ('RGBA', 'LA', 'P') else 'RGB')
    if im.width > max_w:
        im = im.resize((max_w, round(im.height * max_w / im.width)))
    im.save(out, 'WEBP', quality=82, method=6)
    f.unlink()
    return out


def to_web_video(f):
    if not shutil.which('ffmpeg'):
        print('  ffmpeg not found, video left as is:', f)
        return f
    out = f.with_name(f.stem + '.web.mp4')
    for crf in (28, 32, 36):
        subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', str(f), '-vf', 'scale=-2:min(720\\,ih)',
                        '-c:v', 'libx264', '-preset', 'slow', '-crf', str(crf), '-an', '-movflags', '+faststart', str(out)], check=True)
        if out.stat().st_size <= 3_000_000:
            break
    poster = f.with_name(f.stem + '-poster.webp')
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', str(out), '-vframes', '1', '-vf', 'scale=-2:720', str(poster)], check=True)
    f.unlink()
    final = f.with_suffix('.mp4')
    out.rename(final)
    return final


def rel(f):
    return f.relative_to(ROOT).as_posix() if f else None


def num(v):
    try:
        return float(re.sub(r'[^0-9.]', '', v))
    except ValueError:
        return 0.0


def main():
    optimize = '--optimize' in sys.argv
    cards, skipped = [], []
    for d in sorted(p for p in BASE.iterdir() if p.is_dir() and not p.name.startswith('_')):
        meta = d / 'meta.md'
        if not meta.exists():
            skipped.append((d.name, 'no meta.md'))
            continue
        m = parse(meta)
        tw = find(d, 'tw', IMG)
        missing = [k for k in ('brand', 'market', 'format', 'orders', 'cpa', 'roas') if not filled(m.get(k, ''))]
        if not tw:
            missing.append('tw image')
        if missing:
            skipped.append((d.name, 'missing ' + ', '.join(missing)))
            continue
        ad = find(d, 'ad', VID + IMG)
        files = {k: find(d, k, IMG + VID + ('.pdf', '.md')) for k in ('brief', 'template', 'sample')}
        if optimize:
            tw = to_webp(tw)
            if ad:
                ad = to_web_video(ad) if ad.suffix in VID else to_webp(ad)
            files = {k: (to_webp(f) if f and f.suffix in IMG else f) for k, f in files.items()}
        media = None
        if ad:
            poster = d / (ad.stem + '-poster.webp')
            media = {'type': 'video' if ad.suffix in VID else 'image', 'src': rel(ad), 'poster': rel(poster) if poster.exists() else None}
        role = [r.strip() for r in re.split(r'[,·|]', m.get('my_role', '')) if filled(r.strip())]
        g = lambda k: m.get(k) if filled(m.get(k, '')) else None
        card = {
            'slug': d.name, 'brand': m['brand'], 'market': m['market'], 'format': m['format'],
            'concept': g('concept'), 'angle': g('angle'), 'persona': g('persona'), 'hook': (g('hook') or '').strip('"') or None,
            'my_role': role, 'period': g('period'), 'currency': g('currency') or '',
            'spend': g('spend'), 'orders': m['orders'], 'revenue': g('revenue'), 'cpa': m['cpa'], 'roas': m['roas'],
            'source': g('source') or 'Triple Whale (Triple Attribution + platform view)',
            'learning': g('learning'), 'next_iteration': g('next_iteration'),
            'media': media, 'tw': rel(tw), **{k: rel(f) for k, f in files.items()},
        }
        card['alt'] = f"{card['brand']} {card['format']} ad, {card['market']}: {card['orders']} orders at {card['currency']}{card['cpa']} CPA"
        cards.append(card)
    cards.sort(key=lambda c: num(c['orders']), reverse=True)

    summary = None
    sm = BASE / '_summary' / 'summary.md'
    if sm.exists():
        s = parse(sm)
        if filled(s.get('orders', '')) and filled(s.get('period', '')):
            img = find(BASE / '_summary', 'tw-total-sales', IMG)
            if img and optimize:
                img = to_webp(img)
            summary = {'orders': s['orders'], 'revenue': s.get('revenue') if filled(s.get('revenue', '')) else '',
                       'currency': s.get('currency', ''), 'period': s['period'], 'image': rel(img)}
        else:
            skipped.append(('_summary', 'orders or period still [PREENCHER]'))

    (BASE / 'creatives.json').write_text(json.dumps({'summary': summary, 'cards': cards}, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(f'{len(cards)} card(s) written to assets/creatives/creatives.json')
    for c in cards:
        print(f"  check vs {c['tw']}: {c['brand']} {c['market']} | orders {c['orders']} | revenue {c['currency']}{c['revenue']} | cpa {c['currency']}{c['cpa']} | roas {c['roas']}")
    for name, why in skipped:
        print(f'  skipped {name}: {why}')


if __name__ == '__main__':
    main()
