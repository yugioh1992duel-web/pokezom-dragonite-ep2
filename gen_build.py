import json, os, shutil

B = os.path.dirname(os.path.abspath(__file__))
words = json.load(open(os.path.join(B, 'audio', 'vo_main_take_timings.json')))['words']
types = json.load(open('/home/hatch/workspace/pokezom_factory/types.json'))
template = open(os.path.join(B, 'template/index.html')).read()
GOLD = {"600", "700", "145", "dragonite", "mega", "shadow", "giant", "weather", "sixteen", "16",
        "hours", "multiscale", "mercy", "kindness", "myth", "divine", "lance", "barrier", "83",
        "fifty-five", "55", "pearl", "hyper", "beams", "legendary", "crystals", "underwater",
        "safari", "hug", "world", "storms", "dream"}

# ---- caption dictionary pass: whisper garbles -> script-canonical spellings ----
FIX = {'drutini': 'Dratini', 'tretunii': 'Dratini', 'dratini': 'Dratini', 'dragonite': 'Dragonite',
       'terrestrialize': 'Terastallize', 'mailbag': 'mail bag', 'hyperbeams': 'Hyper Beams',
       'antenna': 'antennae', 'ea': 'Z-A', 'lance': 'Lance', 'mewtwo': 'Mewtwo', "ash's": "Ash's",
       'bill': 'Bill', 'golden': 'Gold and'}
MERGE = {('dragon', 'air'): 'Dragonair', ('multi', 'scale'): 'Multiscale',
         ('pseudo', '-legendary'): 'pseudo-legendary'}

def fix_words(ws):
    out, i = [], 0
    while i < len(ws):
        w = ws[i]; raw = w['w']; core = raw.strip('.,!?'); trail = raw[len(raw.rstrip('.,!?')):] if raw.rstrip('.,!?') != raw else ''
        low = core.lower()
        nxt = ws[i + 1]['w'].strip('.,!?').lower() if i + 1 < len(ws) else ''
        prv = ws[i - 1]['w'].strip('.,!?').lower() if i > 0 else ''
        if (low, nxt) in MERGE:
            merged = MERGE[(low, nxt)]
            t2 = ws[i + 1]['w']; tr2 = t2[len(t2.rstrip('.,!?')):] if t2.rstrip('.,!?') != t2 else ''
            out.append({'w': merged + tr2, 's': w['s'], 'e': ws[i + 1]['e']}); i += 2; continue
        if low == 'mirror' and nxt.startswith('b'):
            out.append({'w': 'Miror' + trail, 's': w['s'], 'e': w['e']}); i += 1; continue
        cap = None
        if low == 'mega' and nxt in ('dragonite', 'evolutions', 'evolution', 'evolves', '-evolution'): cap = 'Mega'
        elif low == 'mega' and prv == 'or': cap = 'Mega'
        elif low == 'shadow' and nxt in ('dragonite', 'pokémon', 'pokemon'): cap = 'Shadow'
        elif low == 'silver' and prv == 'golden': cap = 'Silver'
        if cap:
            out.append({'w': cap + trail, 's': w['s'], 'e': w['e']}); i += 1; continue
        if low in FIX:
            rep = FIX[low]
            parts = rep.split(' ')
            parts[-1] = parts[-1] + trail
            out.append({'w': ' '.join(parts), 's': w['s'], 'e': w['e']}); i += 1; continue
        out.append(w); i += 1
    return out

def captions(start, end):
    ws = [w for w in fix_words(words) if start <= w['s'] < end]
    chunks, cur = [], []
    for w in ws:
        cur.append(w)
        if len(cur) >= 9 or (len(cur) >= 5 and w['w'].rstrip().endswith(('.', '!', '?'))):
            chunks.append(cur); cur = []
    if cur: chunks.append(cur)
    return [[round(c[0]['s'] - start, 2), ' '.join(w['w'] for w in c),
             [round(w['s'] - start, 2) for w in c],
             [i for i, w in enumerate(c) if w['w'].lower().strip('.,!?') in GOLD]] for c in chunks]

# ---------- OPTICAL SCALING (Ep.1 solver, Ep.2 placements) ----------
from PIL import Image as _Im
import numpy as _np
_PLACE_SPEC = {  # art: (bbox height fraction of 1080, art right edge, feet y)
 "Dratini": (0.585, 1885, 975), "Dragonair": (0.72, 1885, 965),
 "Dragonite": (0.88, 1885, 975), "Shadow_Dragonite": (0.88, 1885, 975),
 "Mega_Dragonite": (0.88, 1885, 980)}
def _place(art):
    im = _Im.open(os.path.join(B, "assets", art + ".png")).convert("RGBA")
    W, H = im.size; bb = im.getchannel("A").getbbox()
    frac, right, feet = _PLACE_SPEC[art]
    k = (frac * 1080) / (bb[3] - bb[1]); S = k * max(W, H)
    ox = (S - W * k) / 2; oy = (S - H * k) / 2
    return dict(size=int(round(S)), x=int(round(right - ox - bb[2] * k)), y=int(round(feet - oy - bb[3] * k)))
PLACE = {a: _place(a) for a in _PLACE_SPEC}

def _blue_clusters(art):
    """Dragonair-style saturated blue orbs -> list of (fx, fy) sorted by y."""
    a = _np.asarray(_Im.open(os.path.join(B, "assets", art + ".png")).convert("RGBA")).astype(int)
    r, g, b, al = a[..., 0], a[..., 1], a[..., 2], a[..., 3]
    m = (al > 200) & (b > 120) & (b > r + 40) & (g > 60)
    ys, xs = _np.where(m)
    if len(xs) < 20: return []
    med = _np.median(ys)
    out = []
    for sel in (ys <= med, ys > med):
        if sel.sum() > 10:
            out.append((round(float(xs[sel].mean()) / a.shape[1], 3), round(float(ys[sel].mean()) / a.shape[0], 3)))
    return out

def _centroid(art, maskfn):
    a = _np.asarray(_Im.open(os.path.join(B, "assets", art + ".png")).convert("RGBA")).astype(int)
    ys, xs = _np.where(maskfn(a))
    return round(float(xs.mean()) / a.shape[1], 3), round(float(ys.mean()) / a.shape[0], 3)

DRAGONAIR_ORBS = _blue_clusters("Dragonair")
MEGA_BLUE = _blue_clusters("Mega_Dragonite")
MEGA_CORE = _centroid("Mega_Dragonite", lambda a: (a[..., 3] > 200) & (a[..., 0] > 180) & (a[..., 1] > 80) & (a[..., 1] < 180) & (a[..., 2] < 100))
print("optical placements:", {a: (p["size"], p["x"], p["y"]) for a, p in PLACE.items()})
print("dragonair orbs:", DRAGONAIR_ORBS, "| mega blue clusters:", MEGA_BLUE, "| mega core:", MEGA_CORE)

def gpos(art, fx, fy):
    p = PLACE[art]
    return int(round(p["x"] + fx * p["size"])), int(round(p["y"] + fy * p["size"]))

def hero(name, size=760, x=1080, y=185, tin=0.3, tout=None, sil=0, punch=None, white=False,
         evoIn=False, evoOutAt=None, moves=None, place=True):
    h = {"art": name + ".png", "sil": name + "_sil.png", "x": x, "y": y, "size": size,
         "in": tin, "silUntil": sil, "idle": [tin + 1.2, 999]}
    if place and name in PLACE:
        h["size"], h["x"], h["y"] = PLACE[name]["size"], PLACE[name]["x"], PLACE[name]["y"]
    if name == "Mega_Dragonite":
        h["coreX"], h["coreY"] = MEGA_CORE
    if tout is not None: h["out"] = tout
    if punch: h["punch"] = punch
    if white: h["white"] = name + "_white.png"
    if evoIn: h["evoIn"] = True
    if evoOutAt is not None: h["evoOutAt"] = evoOutAt
    if moves: h["moves"] = moves
    return h

def hl(t, html, out, x=70, y=560, size=76): return {"at": t, "html": html, "out": out, "x": x, "y": y, "size": size}
def chip(t, html, out, x=70, y=880): return {"at": t, "html": html, "out": out, "x": x, "y": y}
def still(img, at, out, label=None, x=70, y=545, w=700, h=330, fit=None):
    s = {"img": img, "at": at, "out": out, "x": x, "y": y, "w": w, "h": h}
    if label: s["label"] = label
    if fit: s["fit"] = fit
    return s

def have(img): return os.path.exists(os.path.join(B, 'assets', img))

orb_x, orb_y = gpos("Dragonair", *DRAGONAIR_ORBS[0]) if DRAGONAIR_ORBS else (1300, 300)
# pearl gleam anchor = tail tip of the official art (blue-cluster finder only sees the teal eye/back wing)
pc = (0.905, 0.70)
pearl_x, pearl_y = gpos("Mega_Dragonite", *pc)
print("gleam anchors: dragonair orb", (orb_x, orb_y), "| mega pearl", (pearl_x, pearl_y), "from frac", pc)

# ---------- Ep.2 segment map (section_map.json; all beat times are section-relative) ----------
SEGS = [
 dict(id='s0', start=0.0, dur=37.98, types=["Dragon", "Flying"], formLabel="",
      heroes=[hero("Dratini", tin=0.9, tout=6.4, sil=99),
              hero("Dragonair", tin=6.4, tout=10.3, sil=99),
              hero("Dragonite", tin=10.3, tout=15.9, sil=99),
              dict(art="Dragonite.png", sil="Dragonite_sil.png", x=880, y=-140, size=1420,
                   **{"in": 15.9, "out": 20.6, "silUntil": 99, "idle": [17.1, 999]}),
              hero("Shadow_Dragonite", tin=20.6, tout=24.6, sil=99),
              hero("Mega_Dragonite", tin=24.6, tout=29.2, sil=99)],
      titleCard={"at": 29.3, "big": "EVERY DRAGONITE", "sub": "EXPLAINED — AND RANKED", "out": 37.7}),
 dict(id='s1', start=37.98, dur=60.72, types=["Dragon"], formLabel="FORM 1 OF 6",
      habitat={"img": "hab_underwater.jpg", "in": 0.4, "out": 27.0},
      heroes=[hero("Dratini", white=True, evoOutAt=59.4,
                   moves=[{"kind": "sway", "at": 2.0, "dur": 22}])],
      nameBlock={"name": "DRATINI", "sub": "THE DRAGON POKÉMON · #147", "pills": ["Dragon"], "at": 0.5},
      quoteCard={"at": 13.8, "text": "Long considered a mythical Pokémon until recently, when a small colony was found living underwater.", "src": "POKÉDEX — POKÉMON RED · BLUE", "out": 24.5},
      chips=[chip(20.5, "GEN 1: SAFARI ZONE — <span class='gold'>FISHING ONLY</span>", 27.5),
             chip(28.3, "ITS ANIME EPISODE WAS <span class='gold'>BANNED</span> IN THE US", 34.5),
             chip(41.5, "ABILITY: <span class='gold'>SHED SKIN</span>", 47.5),
             chip(50.8, "THE <span class='gold'>ONLY</span> DRAGON FAMILY IN GEN 1", 57.5)]),
 dict(id='s2', start=98.70, dur=69.76, types=["Dragon"], formLabel="FORM 2 OF 6",
      heroes=[hero("Dragonair", white=True, evoIn=True, evoOutAt=68.6,
                   moves=[{"kind": "sway", "at": 2.5, "dur": 34}])],
      nameBlock={"name": "DRAGONAIR", "sub": "THE DRAGON POKÉMON · #148", "pills": ["Dragon"], "at": 0.5},
      gleams=[{"x": orb_x, "y": orb_y, "at": 14.8, "size": 150, "color": "#7ec8ff", "n": 2}],
      quoteCard={"at": 15.2, "text": "Its crystalline orbs appear to give this Pokémon the power to freely control the weather.", "src": "POKÉDEX — POKÉMON SILVER", "out": 22.5},
      headlines=[hl(30.5, "THE <span class='gold'>DIVINE</span> POKÉMON", 37.5),
                 hl(44.5, "THE FAN-FAVORITE<br/><span class='gold'>DESIGN</span>", 51.5)],
      chips=[chip(58.8, "EVOLVES AT LEVEL <span class='gold'>55</span>", 65.5)]),
 dict(id='s3', start=168.46, dur=110.14, types=["Dragon", "Flying"], formLabel="FORM 3 OF 6",
      habitat={"img": "hab_storm.jpg", "in": 77.0, "out": 94.0},
      heroes=[hero("Dragonite", white=True, evoIn=True, punch=8.2,
                   moves=[{"kind": "launch", "at": 79.38}])],
      nameBlock={"name": "DRAGONITE", "sub": "THE DRAGON POKÉMON · #149", "pills": ["Dragon", "Flying"], "at": 0.6},
      statAnim={"at": 28.8, "from": 0, "to": 600, "label": "TOTAL STATS", "x": 70, "y": 880, "out": 40.0},
      chips=[chip(41.8, "ABILITY: <span class='gold'>MULTISCALE</span> — FIRST HIT CUT IN HALF", 49.5),
             chip(47.8, "<span class='gold'>TERA NORMAL</span> + EXTREME SPEED", 54.5),
             chip(59.0, "<span class='gold'>3 DRAGONITE</span> — TWO AT LEVEL 47", 65.5, y=892),
             chip(66.8, "<span class='red'>ILLEGAL:</span> BARRIER — A MOVE IT CAN'T LEARN", 72.5, y=892),
             chip(87.8, "THE <span class='gold'>SEA INCARNATE</span>", 93.0)],
      headlines=[hl(79.6, "AROUND THE WORLD<br/>IN <span class='gold'>16 HOURS</span>", 86.5)],
      stills=[still("still_lance.png", 55.8, 64.5, "LANCE — CHAMPION OF KANTO"),
              still("still_mailman.png", 91.2, 98.5, "MEWTWO STRIKES BACK (1999) — THE MAILMAN"),
              still("still_hug.jpg", 99.8, 107.5, "ASH'S DRAGONITE — FAMOUS FOR HUGS")]),
 dict(id='s4', start=278.60, dur=44.66, types=["Water", "Dragon"], formLabel="FORM 4 OF 6",
      habitat={"img": "hab_fog.jpg", "in": 0.3, "out": 44.2, "shade": 0.5},
      heroes=[dict(art="Dragonite.png", sil="Dragonite_sil.png", x=1030, y=-180, size=1500,
                   **{"in": 0.4, "silUntil": 99, "idle": [1.6, 999],
                      "moves": [{"kind": "loom", "at": 1.0, "dur": 40}]})],
      nameBlock={"name": "GIANT DRAGONITE", "sub": "MYSTERY AT THE LIGHTHOUSE · ANIME EP. 13", "pills": ["Dragon", "Flying"], "at": 0.5},
      stills=[still("still_giant.png", 6.0, 24.0, None, w=533, h=400, y=625)],
      chips=[chip(26.5, "SIZE: <span class='gold'>UNMEASURED</span>", 33.0, y=892)],
      headlines=[hl(34.5, "DYNAMAX... BEFORE<br/><span class='gold'>DYNAMAX?</span>", 41.5, y=690)]),
 dict(id='s5', start=323.26, dur=43.08, types=["Dragon", "Flying"], formLabel="FORM 5 OF 6", mood="shadow",
      heroes=[hero("Shadow_Dragonite", moves=[{"kind": "shake", "at": 23.76}])],
      nameBlock={"name": "SHADOW DRAGONITE", "sub": "POKÉMON XD · THE FINAL SHADOW POKÉMON", "pills": ["Dragon", "Flying"], "at": 0.5},
      chips=[chip(7.8, "SHADOW POKÉMON <span class='gold'>#83</span> — THE LAST ONE MADE", 13.5),
             chip(14.5, "STOLEN BY <span class='gold'>MIROR B.</span>", 20.0),
             chip(27.2, "<span class='gold'>+20% ATTACK</span>", 30.5, y=892),
             chip(29.2, "<span class='red'>−20% DEFENSE</span>", 33.0, x=540, y=892)],
      headlines=[hl(39.3, "THE SAFETY IS <span class='gold'>OFF</span>", 42.9, y=705)]),
 dict(id='s6', start=366.34, dur=72.50, types=["Dragon", "Flying"], formLabel="FORM 6 OF 6", mood="mega2",
      heroes=[hero("Mega_Dragonite", punch=8.1)],
      nameBlock={"name": "MEGA DRAGONITE", "sub": "MEGA EVOLUTION · LEGENDS: Z-A (2025)", "pills": ["Dragon", "Flying"], "at": 0.6},
      gleams=[{"x": pearl_x, "y": pearl_y, "at": 24.9, "size": 170, "color": "#8ef7ff", "n": 2}],
      statAnim={"at": 32.8, "from": 600, "to": 700, "label": "TOTAL STATS", "x": 70, "y": 880, "out": 36.8},
      chips=[chip(37.0, "ATTACK <span class='red'>−10</span>", 42.5, y=892),
             chip(39.6, "SP. ATK <span class='gold'>+45 → 145</span>", 45.0, y=800),
             chip(48.8, "KEEPS <span class='gold'>MULTISCALE</span> — THE SHIELD STAYS UP", 55.5)],
      quoteCard={"at": 54.2, "text": "Mega Evolution has excessively powered up this Pokémon's feelings of kindness. It finishes off its opponents with mercy in its heart.", "src": "POKÉDEX — LEGENDS: Z-A", "out": 63.5},
      headlines=[hl(65.0, "KINDNESS, TURNED<br/><span class='gold'>ALL THE WAY UP</span>", 71.5, y=705)]),
 dict(id='s7', start=438.84, dur=79.74, types=["Dragon", "Flying"], formLabel="THE RANKING",
      heroes=[dict(art="Dragonite.png", sil="Dragonite_sil.png", x=1150, y=-260, size=1500,
                   **{"in": 0.2, "silUntil": 99, "idle": [1.4, 999],
                      "moves": [{"kind": "loom", "at": 1.0, "dur": 70}]})],
      ranking={"slots": [{"art": a, "x": 34 + i * 314, "y": 330, "w": 280, "num": 6 - i, "name": n, "in": 0.4 + i * 0.15}
                          for i, (a, n) in enumerate([("Dratini.png", "DRATINI"), ("Dragonite_sil.png", "GIANT"),
                                                       ("Shadow_Dragonite.png", "SHADOW"), ("Dragonair.png", "DRAGONAIR"),
                                                       ("Dragonite.png", "DRAGONITE"), ("Mega_Dragonite.png", "MEGA DRAGONITE")])],
               "hits": [{"idx": i, "t": t} for i, t in enumerate([4.5, 10.8, 19.9, 27.1, 40.1, 50.2])]},
      headlines=[hl(62.3, "YOUR TURN — <span class='gold'>VOTE BELOW!</span>", 72.0, x=480, y=130, size=84)],
      chips=[chip(73.8, "NEXT EPISODE: <span class='gold'>EVERY METAGROSS</span>", 79.4, x=620, y=790)]),
]

for cfg in SEGS:
    cfg['world'] = cfg['types']
    cfg['duration'] = cfg['dur']
    cfg['captions'] = captions(cfg['start'], cfg['start'] + cfg['dur'])
    d = os.path.join(B, 'segments', cfg['id']); os.makedirs(os.path.join(d, 'assets'), exist_ok=True)
    html = template.replace('/*__CONFIG__*/', json.dumps(cfg)).replace('/*__TYPES__*/', json.dumps(types)).replace('__DURATION__', str(cfg['dur']))
    open(os.path.join(d, 'index.html'), 'w').write(html)
    json.dump({"$schema": "https://hyperframes.heygen.com/schema/hyperframes.json", "registry": "https://raw.githubusercontent.com/heygen-com/hyperframes/main/registry", "paths": {"blocks": "compositions", "components": "compositions/components", "assets": "assets"}}, open(os.path.join(d, 'hyperframes.json'), 'w'), indent=2)
    arts = [h['art'][:-4] for h in cfg.get('heroes', [])] + [s['art'][:-4] for s in cfg.get('ranking', {}).get('slots', [])]
    for a in set(arts):
        for suf in ('.png', '_sil.png', '_white.png'):
            src = os.path.join(B, 'assets', a + suf)
            if os.path.exists(src): shutil.copy(src, os.path.join(d, 'assets', a + suf))
    for st in cfg.get('stills', []):
        src = os.path.join(B, 'assets', st['img'])
        if os.path.exists(src): shutil.copy(src, os.path.join(d, 'assets', st['img']))
        else: print('MISSING STILL:', cfg['id'], st['img'])
    if cfg.get('habitat'):
        src = os.path.join(B, 'assets', cfg['habitat']['img'])
        if os.path.exists(src): shutil.copy(src, os.path.join(d, 'assets', cfg['habitat']['img']))
        else: print('MISSING HABITAT:', cfg['id'], cfg['habitat']['img'])
    shutil.copy('/home/hatch/workspace/pokezom_tristorm_build/hf/assets/gsap.min.js', os.path.join(d, 'assets', 'gsap.min.js'))
    print(cfg['id'], 'ok, caps', len(cfg['captions']))
print('ALL SEGMENTS BUILT (Ep.2 v1)')
