#!/usr/bin/env python3
"""Build assets/creatives/creatives.json and web media for the #creatives section.

Source: an export folder (creatives-export) with
  _summary/index.csv           one row per creative: the ONLY source of numbers
  <slug>/meta.md               hook, angle, persona, learning, my_role, my_role_source
  <slug>/ad.(jpg|png|mp4)      the creative
  <slug>/tw.png                Triple Whale print (ad ID already blurred)

Only the slugs listed in SELECTION are published, grouped by brand in that order.
Rules: no number is typed by hand; fields holding [PREENCHER] are left out;
"my role" is shown only when my_role is filled (not [PREENCHER]).

Usage: python3 scripts/build_creatives.py /path/to/creatives-export
"""
import csv, json, re, shutil, subprocess, sys
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'assets' / 'creatives'
PH = '[PREENCHER'

SELECTION = {
    'Astra Straps': [
        'astrastraps-au-echo-videoad004-us-h2', 'astrastraps-us-echo-videoad001-au-h5',
        'astrastraps-us-aereslim-imagead001-batch1-v2-1', 'astrastraps-au-leam-ad003-916-h2',
        'astrastraps-au-aereslim-imagead002-h1-v2', 'astrastraps-us-aevumnylon-imagead-006-h5',
        'astrastraps-au-2-ad-reviews', 'astrastraps-us-class-stainless-imagead006-h4',
        'astrastraps-us-ad-pack-2-cc13', 'astrastraps-au-echo-videoad001-au-h5'],
    'Trestique': [
        'trestique-us-ad-winner-4', 'trestique-us-new-ad-1', 'trestique-us-new-ad-5',
        'trestique-us-faceinacase-static', 'trestique-us-early-access-img-ad-1', 'trestique-us-ad-winner-6',
        'trestique-us-new-ad-3', 'trestique-us-lae-andres-ugc', 'trestique-us-michele-johnston-ugc-ad-3',
        'trestique-us-ellen-ugc'],
}
# Currency symbols as given by the user: $ = USD, A$ = AUD, £ = GBP
CURRENCY = {'$': ('US$', 'USD'), 'A$': ('A$', 'AUD'), '£': ('£', 'GBP'), 'NZ$': ('NZ$', 'NZD')}


def filled(v):
    return bool(v) and PH not in v and v.lower() not in ('n/d', 'na', 'n/a')


def parse_meta(p):
    d = {}
    if p.exists():
        for line in p.read_text(encoding='utf-8').splitlines():
            m = re.match(r'^([a-z_]+):\s*(.*)$', line)
            if m:
                d[m.group(1)] = m.group(2).strip()
    return d


def clean(v):
    v = re.sub(r'\s*\((analise|analysis|análise)\)', '', v or '').strip()
    return v.replace('—', ',').replace('–', '-')


def hook_of(m):
    h = m.get('hook', '')
    q = re.match(r'^"(.+?)"', h)
    if q:
        return q.group(1)
    s = re.search(r'on screen:\s*"(.+?)"', h)
    return s.group(1) if s else ''


def money(v):
    """'A$1,898.58' -> '1,898.58' (symbol shown separately)."""
    return re.sub(r'^[^\d\-]+', '', (v or '').strip())


def period_label(p):
    m = re.match(r'(\d{4})-(\d{2})-(\d{2}) a (\d{4})-(\d{2})-(\d{2})', p or '')
    if not m:
        return p
    mon = 'Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec'.split()
    y1, m1, d1, y2, m2, d2 = map(int, m.groups())
    if y1 != y2:
        return f'{mon[m1-1]} {d1}, {y1} to {mon[m2-1]} {d2}, {y2}'
    return f'{mon[m1-1]} {d1} to {mon[m2-1]} {d2}, {y2}'


def web_image(src, dst, max_w=900):
    im = Image.open(src)
    im = im.convert('RGB')
    im.thumbnail((max_w, max_w * 2))
    im.save(dst, 'WEBP', quality=82, method=6)


def web_video(src, dst_mp4, dst_poster):
    for crf in (28, 31, 34):
        subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', str(src),
                        '-vf', "scale='min(720,iw)':-2", '-c:v', 'libx264', '-preset', 'slow', '-crf', str(crf),
                        '-pix_fmt', 'yuv420p', '-an', '-movflags', '+faststart', str(dst_mp4)], check=True)
        if dst_mp4.stat().st_size <= 1_600_000:
            break
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-ss', '0.5', '-i', str(src), '-vframes', '1',
                    '-vf', "scale='min(720,iw)':-2", '-q:v', '4', str(dst_poster)], check=True)


def main():
    src = Path(sys.argv[1]).resolve()
    rows = {r['folder']: r for r in csv.DictReader(open(src / '_summary' / 'index.csv', encoding='utf-8'))}
    brands, problems = [], []
    keep = set()
    for brand, slugs in SELECTION.items():
        cards = []
        for slug in slugs:
            r = rows.get(slug)
            if not r:
                problems.append(f'{slug}: not in index.csv')
                continue
            d = src / slug
            m = parse_meta(d / 'meta.md')
            sym = r['currency'].split()[0] if r['currency'] else ''
            cur, code = CURRENCY.get(sym, (sym, ''))
            out = OUT / slug
            out.mkdir(parents=True, exist_ok=True)
            keep.add(slug)
            media = None
            ad = next((d / n for n in ('ad.mp4', 'ad.jpg', 'ad.png', 'ad.jpeg') if (d / n).exists()), None)
            if ad and ad.suffix == '.mp4':
                if not ((out / 'ad.mp4').exists() and (out / 'poster.jpg').exists()):
                    web_video(ad, out / 'ad.mp4', out / 'poster.jpg')
                media = {'type': 'video', 'src': f'assets/creatives/{slug}/ad.mp4', 'poster': f'assets/creatives/{slug}/poster.jpg'}
            elif ad:
                web_image(ad, out / 'ad.webp')
                media = {'type': 'image', 'src': f'assets/creatives/{slug}/ad.webp'}
            else:
                problems.append(f'{slug}: no ad file')
            tw = None
            if (d / 'tw.png').exists():
                web_image(d / 'tw.png', out / 'tw.webp', max_w=1400)
                tw = f'assets/creatives/{slug}/tw.webp'
            else:
                problems.append(f'{slug}: no tw.png')
            role = m.get('my_role', '')
            roles = [x.strip() for x in role.split(',') if x.strip()] if filled(role) else []
            g = lambda k: clean(m[k]) if filled(m.get(k, '')) else None
            card = {
                'slug': slug, 'brand': r['brand'], 'market': r['market'], 'name': r['ad_name'], 'format': r['format'],
                'period': period_label(r['period']), 'currency': cur, 'currency_code': code,
                'spend': money(r['spend']), 'orders': r['orders'], 'revenue': money(r['revenue']),
                'cpa': money(r['cpa']), 'roas': r['roas'], 'ctr': r['ctr'], 'status': r['status'],
                'hook': hook_of(m) or None, 'angle': g('angle'), 'persona': g('persona'),
                'learning': g('learning'), 'next_iteration': g('next_iteration'),
                'my_role': roles, 'media': media, 'tw': tw,
            }
            # lifetime (since launch), only when the export has it
            if filled(r.get('lt_orders', '')) and filled(r.get('lt_spend', '')):
                ltw = None
                if (d / 'tw-lifetime.png').exists():
                    web_image(d / 'tw-lifetime.png', out / 'tw-lifetime.webp', max_w=1400)
                    ltw = f'assets/creatives/{slug}/tw-lifetime.webp'
                launch = r.get('launch_date', '')
                card['lifetime'] = {
                    'label': 'Since launch' if filled(launch) else 'All Triple Whale history',
                    'period': period_label(r['lt_period']),
                    'launch_date': period_label(f'{launch} a {launch}').split(' to ')[1] if filled(launch) else None,
                    'spend': money(r['lt_spend']), 'orders': r['lt_orders'], 'revenue': money(r['lt_revenue']),
                    'cpa': money(r['lt_cpa']), 'roas': r['lt_roas'], 'ctr': r['lt_ctr'], 'tw': ltw,
                }
            fmt = {'UGC': 'UGC video', 'video': 'video', 'static': 'static', 'carousel': 'carousel'}.get(card['format'], card['format'])
            card['alt'] = f"{card['brand']} {card['market']} {fmt} ad: {card['orders']} purchases at {cur}{card['cpa']} CPA, {card['roas']} ROAS"
            cards.append(card)
        brands.append({'brand': brand, 'cards': cards})
    # account context, from _summary/summary.md / the user's list
    context = {
        'Astra Straps': 'Store totals, last 365 days (Triple Whale Summary, all channels): US US$2,029,210 sales at 2.17 ROAS, AU A$631,902 at 1.97, UK £326,859 at 2.52. Meta pixel purchases: 7,226 US + 1,427 AU + 781 UK = 9,434.',
        'Trestique': 'Trestique US, last 365 days (Triple Whale Summary): US$1,593,152 total sales, US$880,653 blended spend, 1.89 ROAS, US$606,750 net profit.',
    }
    for b in brands:
        b['context'] = context.get(b['brand'])
    # Trestique all-time top 30 (grouped by ad name), from the export's resumo.csv
    tl = None
    tl_csv = OUT / '_trestique-lifetime' / 'source.csv'
    if tl_csv.exists():
        rows30 = list(csv.DictReader(open(tl_csv, encoding='utf-8')))
        items = [{
            'rank': int(x['rank']), 'name': x['ad_name'], 'spend': float(x['spend_usd']), 'orders': int(x['pixel_purchases']),
            'revenue': float(x['pixel_cv_usd']), 'cpa': float(x['pixel_cpa_usd']), 'roas': x['pixel_roas'], 'ctr': x['ctr'],
            'tw': f"assets/creatives/_trestique-lifetime/{x['print'].rsplit('.', 1)[0]}.webp",
        } for x in rows30]
        tot_spend = round(sum(i['spend'] for i in items), 2)
        tot_rev = round(sum(i['revenue'] for i in items), 2)
        tl = {
            'period': 'Nov 24, 2022 to Nov 23, 2026', 'currency': 'US$',
            'note': 'Grouped by ad name across all campaigns (Triple Whale, TA + Platform Views, pixel). A name can cover several ads, so these totals can be higher than the single-ad numbers on the cards above. The same video can also appear under two names; rows are not merged.',
            'items': items,
            'totals': {'spend': tot_spend, 'orders': sum(i['orders'] for i in items), 'revenue': tot_rev,
                       'roas': f'{tot_rev / tot_spend:.2f}'},
        }
        print(f"  trestique top {len(items)}: spend {tot_spend:,.2f}, purchases {tl['totals']['orders']}, revenue {tot_rev:,.2f}, roas {tl['totals']['roas']}")
    (OUT / 'creatives.json').write_text(json.dumps({'brands': brands, 'trestique_lifetime': tl}, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    # drop old card folders that are no longer selected
    for p in OUT.iterdir():
        if p.is_dir() and not p.name.startswith('_') and p.name not in keep:
            shutil.rmtree(p)
    n = sum(len(b['cards']) for b in brands)
    print(f'{n} cards written')
    for b in brands:
        for c in b['cards']:
            print(f"  {c['slug']}: {c['orders']} purchases, {c['currency']}{c['revenue']} revenue, CPA {c['currency']}{c['cpa']}, ROAS {c['roas']}, CTR {c['ctr']}, role={c['my_role']}")
    for p in problems:
        print('  PROBLEM', p)


if __name__ == '__main__':
    main()
