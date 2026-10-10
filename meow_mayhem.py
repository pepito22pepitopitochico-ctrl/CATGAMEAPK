# -*- coding: utf-8 -*-
"""
MEOW MAYHEM  -  Pac-Man + Plataformas 2D
Todos los graficos y sonidos se generan por codigo (no hay archivos externos).

CONTROLES
  Menus      : flechas + ENTER      (ESC = atras / pausa)
  Laberinto  : flechas o WASD
  Plataformas: flechas/AD = mover, ESPACIO/W/ARRIBA = saltar, X/Z/J = arañar,
               C/V/B = lanzar pelota (si tienes), ABAJO/S = bajar al volar
  M = silenciar / activar sonido
"""
import math
import random
import sys
import os
import json
import array
from collections import deque

import pygame

W, H, T, FPS = 800, 608, 32, 60
GROUND_ROW = 15
GY = GROUND_ROW * T          # suelo de las arenas de jefes (480)
O = 1                        # grosor del contorno de los sprites

# ----------------------------------------------------------------------------
#  AJUSTES DE JUEGO (todo en frames; 60 frames = 1 segundo)
# ----------------------------------------------------------------------------
ATK_CD = 72            # cooldown del arañazo del gato: 1,2 s
DOG_REST = 72          # los perros jefe esperan 1,2 s entre ataques
STOMP_INV = 180        # invulnerable 3 s tras saltarle encima a un perro
HUMAN_REST = 300       # el humano descansa 5 s despues de cada ataque
TIRED_T = 240          # humano cansado 4 s si llegas al final de la persecucion
FLAWLESS_BONUS = 3     # corazones extra si vences a un jefe sin daño (sin limite)
MAX_HEARTS_NORMAL = 5  # tope de los corazones normales
RUN_MAX = 300          # los enemigos del laberinto corren como maximo 5 s
TIRED_MIN, TIRED_MAX = 360, 420   # despues caminan a la mitad 6-7 s
RUN_MULT, TIRED_MULT = 1.65, 0.5
SLOW_SCALE = 0.45      # camara lenta (todo menos el gato)

POWER_DUR = {"speed": 600, "shield": 480, "fly": 600, "sense": 720, "slow": 600}
POWER_NAMES = {"speed": "SUPER VELOCIDAD", "shield": "INMUNE", "fly": "¡A VOLAR!",
               "sense": "SENTIDO GATUNO", "slow": "CÁMARA LENTA"}
ITEM_KINDS = ["life", "heal", "speed", "shield", "fly", "sense", "slow", "ball"]
ITEM_WEIGHTS = [10, 14, 14, 12, 10, 12, 10, 18]
ITEM_TEXT = {"life": "¡VIDA EXTRA! +1 corazón", "heal": "+1 corazón (máx. 5)",
             "ball": "¡PELOTA! +3 lanzamientos (C)"}

JUMP_KEYS = (pygame.K_SPACE, pygame.K_UP, pygame.K_w)
ATK_KEYS = (pygame.K_x, pygame.K_z, pygame.K_j, pygame.K_k, pygame.K_LCTRL)
BALL_KEYS = (pygame.K_c, pygame.K_v, pygame.K_b)
DIRS = ((1, 0), (-1, 0), (0, 1), (0, -1))


def roll_dog_damage():
    """Perros del laberinto: 3 corazones (40%), 2 (40%) o 1,5 (20%)."""
    r = random.random()
    return 3.0 if r < 0.40 else 2.0 if r < 0.80 else 1.5


def roll_human_damage():
    """Humano del laberinto: 4 corazones (40%), 2 (40%) o 3 (20%)."""
    r = random.random()
    return 4.0 if r < 0.40 else 2.0 if r < 0.80 else 3.0


# ----------------------------------------------------------------------------
#  SKINS DEL GATO (las 3 ultimas son tus dibujos)
# ----------------------------------------------------------------------------
SKINS = [
    dict(name="NARANJA", body=(240, 150, 50), dark=(190, 95, 25), belly=(255, 225, 170),
         eye=(255, 255, 255), iris=(0, 0, 0), stripes=True),
    dict(name="SOMBRA", body=(52, 52, 66), dark=(26, 26, 36), belly=(90, 90, 108),
         eye=(255, 240, 90), iris=(0, 0, 0)),
    dict(name="NIEVE", body=(245, 245, 250), dark=(200, 205, 222), belly=(255, 255, 255),
         eye=(130, 205, 255), iris=(20, 40, 100)),
    dict(name="SIAMÉS", body=(238, 218, 185), dark=(95, 65, 50), belly=(248, 235, 210),
         eye=(120, 195, 255), iris=(10, 30, 80), mask=True),
    dict(name="CENIZA", body=(150, 155, 172), dark=(100, 105, 128), belly=(205, 210, 222),
         eye=(255, 255, 255), iris=(0, 0, 0), stripes=True),
    dict(name="ESMOQUIN", body=(38, 38, 50), dark=(18, 18, 26), belly=(255, 255, 255),
         eye=(150, 255, 130), iris=(0, 0, 0), bib=True),
    dict(name="MANCHAS", body=(250, 250, 250), dark=(230, 140, 45), belly=(255, 240, 220),
         eye=(255, 255, 255), iris=(0, 0, 0), patches=((235, 140, 45), (45, 45, 55))),
    dict(name="GALAXIA", body=(95, 65, 190), dark=(55, 35, 130), belly=(175, 150, 255),
         eye=(255, 255, 120), iris=(30, 0, 60), stars=True),
]
N_BUILTIN = len(SKINS)
N_CUSTOM = 3
N_SKINS = N_BUILTIN + N_CUSTOM


def skin_name(i):
    return SKINS[i]["name"] if i < N_BUILTIN else "MI SKIN %d" % (i - N_BUILTIN + 1)


# ----------------------------------------------------------------------------
#  UTILIDADES
# ----------------------------------------------------------------------------
A = {}          # sprites generados
RAW_SIDE, RAW_TOP = [], []     # sprites sin contorno (plantillas del editor)
S = {}          # sonidos generados
MUTED = [False]
_fonts = {}

SAVE_PATH = os.path.join(os.path.expanduser("~"), "MeowMayhem_save.json")


def load_save():
    try:
        with open(SAVE_PATH, "r", encoding="utf-8") as f:
            d = json.load(f)
            return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def write_save(d):
    try:
        with open(SAVE_PATH, "w", encoding="utf-8") as f:
            json.dump(d, f)
    except Exception:
        pass


def clamp(v, a, b):
    return a if v < a else b if v > b else v


def surf(w, h):
    return pygame.Surface((w, h), pygame.SRCALPHA)


def font(size, title=False):
    key = (size, title)
    if key not in _fonts:
        name = "impact,arialblack,arial" if title else "arial"
        _fonts[key] = pygame.font.SysFont(name, size, bold=not title)
    return _fonts[key]


def txt(dst, s, size, color, x, y, center=False, shadow=True, title=False):
    f = font(size, title)
    img = f.render(s, True, color)
    if center:
        x -= img.get_width() // 2
    if shadow:
        sh = f.render(s, True, (0, 0, 0))
        dst.blit(sh, (x + 3, y + 3))
    dst.blit(img, (x, y))


def panel(dst, rect, color=(10, 10, 32), alpha=175, border=(90, 120, 255), radius=10):
    x, y, w, h = rect
    s = surf(w, h)
    pygame.draw.rect(s, color + (alpha,), (0, 0, w, h), border_radius=radius)
    if border:
        pygame.draw.rect(s, border + (255,), (0, 0, w, h), 2, border_radius=radius)
    dst.blit(s, (x, y))


def button(dst, cx, y, w, label, selected, h=52):
    x = cx - w // 2
    if selected:
        pygame.draw.rect(dst, (255, 150, 30), (x - 6, y - 6, w + 12, h + 12), border_radius=18)
        pygame.draw.rect(dst, (255, 215, 80), (x, y, w, h), border_radius=14)
        txt(dst, label, 28, (40, 20, 0), cx, y + 10, True, False)
    else:
        pygame.draw.rect(dst, (28, 34, 90), (x, y, w, h), border_radius=14)
        pygame.draw.rect(dst, (90, 120, 255), (x, y, w, h), 2, border_radius=14)
        txt(dst, label, 26, (230, 235, 255), cx, y + 11, True, False)


def small_button(dst, rect, label, active=False, hover=False, size=18):
    x, y, w, h = rect
    col = (255, 215, 80) if active else ((60, 74, 150) if hover else (30, 36, 96))
    pygame.draw.rect(dst, col, rect, border_radius=8)
    pygame.draw.rect(dst, (120, 150, 255) if not active else (255, 150, 30), rect, 2, border_radius=8)
    txt(dst, label, size, (30, 20, 0) if active else (235, 238, 255), x + w // 2,
        y + (h - size) // 2 - 2, True, False)


def banner(dst, y, title, sub=None, color=(255, 90, 90), h=118):
    ov = surf(W, h)
    ov.fill((0, 0, 0, 195))
    dst.blit(ov, (0, y))
    pygame.draw.rect(dst, color, (0, y, W, 4))
    pygame.draw.rect(dst, color, (0, y + h - 4, W, 4))
    txt(dst, title, 58, color, W // 2, y + 8, True, True, True)
    if sub:
        txt(dst, sub, 22, (255, 255, 255), W // 2, y + h - 40, True)


def make_tone(freq, ms, vol=0.25, slide=0.0, noise=0.0):
    n = int(22050 * ms / 1000)
    buf = array.array("h")
    ph = 0.0
    for i in range(n):
        f = freq + slide * i / n
        ph += 2 * math.pi * f / 22050
        v = math.sin(ph)
        if noise:
            v = v * (1 - noise) + random.uniform(-1, 1) * noise
        buf.append(int(v * vol * 32767 * (1 - i / n)))
    return pygame.mixer.Sound(buffer=buf.tobytes())


def init_sounds():
    try:
        S["jump"] = make_tone(300, 150, slide=350)
        S["hit"] = make_tone(180, 220, slide=-120, noise=0.5, vol=0.3)
        S["pick"] = make_tone(660, 180, slide=500)
        S["scratch"] = make_tone(900, 90, slide=-500, noise=0.6, vol=0.15)
        S["win"] = make_tone(440, 600, slide=660)
        S["boss"] = make_tone(120, 500, slide=-60, noise=0.3, vol=0.3)
        S["stomp"] = make_tone(250, 120, slide=-150, vol=0.3)
        S["menu"] = make_tone(520, 70, slide=200, vol=0.18)
        S["power"] = make_tone(400, 420, slide=900, vol=0.22)
        S["block"] = make_tone(160, 140, slide=120, vol=0.3)
        S["spring"] = make_tone(220, 200, slide=700, vol=0.22)
        S["throw"] = make_tone(500, 110, slide=-250, vol=0.18)
        S["run"] = make_tone(90, 260, slide=60, noise=0.2, vol=0.2)
    except Exception:
        S.clear()


def play(name):
    s = S.get(name)
    if s and not MUTED[0]:
        try:
            s.play()
        except Exception:
            pass


# ----------------------------------------------------------------------------
#  SPRITES POR CODIGO
# ----------------------------------------------------------------------------
OUT = (22, 14, 34)


def outlined(img, t=O, col=OUT):
    """Devuelve el sprite con un contorno oscuro (queda 2*t px mas grande)."""
    w, h = img.get_size()
    out = surf(w + 2 * t, h + 2 * t)
    sil = img.copy()
    sil.fill((0, 0, 0, 255), special_flags=pygame.BLEND_RGBA_MULT)
    sil.fill(col + (0,), special_flags=pygame.BLEND_RGBA_ADD)
    for dx in (-t, 0, t):
        for dy in (-t, 0, t):
            if dx or dy:
                out.blit(sil, (t + dx, t + dy))
    out.blit(img, (t, t))
    return out


def flipx(img):
    return pygame.transform.flip(img, True, False)


def shade(c, d):
    return tuple(max(0, min(255, v + d)) for v in c)


def heart_shape(s, color, size, grow=0):
    r = int(size * 0.23) + grow
    pygame.draw.circle(s, color, (int(size * 0.3), int(size * 0.36)), r)
    pygame.draw.circle(s, color, (int(size * 0.7), int(size * 0.36)), r)
    pygame.draw.polygon(s, color, [(int(size * 0.06) - grow, int(size * 0.45)),
                                   (int(size * 0.94) + grow, int(size * 0.45)),
                                   (size // 2, int(size * 0.93) + grow)])


def make_heart(size, kind):
    s = surf(size, size)
    heart_shape(s, (30, 10, 20), size, 2)
    if kind == "full":
        heart_shape(s, (235, 50, 70), size)
        pygame.draw.circle(s, (255, 150, 160), (int(size * 0.28), int(size * 0.3)), max(1, size // 10))
    elif kind == "empty":
        heart_shape(s, (75, 55, 75), size)
    else:
        heart_shape(s, (75, 55, 75), size)
        full = surf(size, size)
        heart_shape(full, (235, 50, 70), size)
        s.blit(full, (0, 0), pygame.Rect(0, 0, size // 2, size))
    return s


# ---- gato -------------------------------------------------------------------
def make_cat_top(dx, dy, sk):
    s = surf(32, 32)
    o, d = sk["body"], sk["dark"]
    pygame.draw.polygon(s, d, [(3, 12), (5, 1), (14, 7)])
    pygame.draw.polygon(s, d, [(29, 12), (27, 1), (18, 7)])
    pygame.draw.polygon(s, (255, 170, 170), [(6, 9), (7, 4), (11, 7)])
    pygame.draw.polygon(s, (255, 170, 170), [(26, 9), (25, 4), (21, 7)])
    pygame.draw.circle(s, o, (16, 18), 13)
    pygame.draw.ellipse(s, shade(o, 28), (8, 8, 16, 8))
    if sk.get("patches"):
        pygame.draw.circle(s, sk["patches"][0], (9, 12), 6)
        pygame.draw.circle(s, sk["patches"][1], (24, 13), 5)
    if sk.get("stars"):
        for px, py in ((8, 12), (22, 10), (24, 18), (12, 16)):
            pygame.draw.circle(s, (230, 220, 255), (px, py), 1)
    pygame.draw.circle(s, d if sk.get("mask") else sk["belly"], (16, 23), 7)
    for ex in (10, 22):
        pygame.draw.circle(s, sk["eye"], (ex + dx * 2, 16 + dy * 2), 4)
        pygame.draw.circle(s, sk["iris"], (ex + dx * 3, 16 + dy * 3), 2)
        pygame.draw.circle(s, (255, 255, 255), (ex + dx * 2 - 1, 15 + dy * 2), 1)
    pygame.draw.polygon(s, (255, 110, 140), [(14, 22), (18, 22), (16, 25)])
    for sx in (-1, 1):
        pygame.draw.line(s, (60, 40, 30), (16 + sx * 5, 24), (16 + sx * 14, 22), 1)
        pygame.draw.line(s, (60, 40, 30), (16 + sx * 5, 26), (16 + sx * 14, 28), 1)
    if sk.get("stripes"):
        for sx in (12, 16, 20):
            pygame.draw.line(s, d, (sx, 6), (sx, 10), 2)
    return s


def make_cat_side(frame, sk):
    s = surf(44, 34)
    o, d = sk["body"], sk["dark"]
    pygame.draw.lines(s, o, False, [(9, 22), (3, 18), (2, 10), (6, 4)], 5)
    pygame.draw.line(s, d, (6, 5), (6, 3), 5)
    xs = [(11, 16, 26, 31), (9, 18, 24, 33), (10, 17, 27, 33)][frame]
    for i, lx in enumerate(xs):
        if frame < 2:
            pygame.draw.rect(s, d if i % 2 == 0 else o, (lx, 24, 5, 9), border_radius=2)
        else:
            pygame.draw.rect(s, d if i % 2 == 0 else o, (lx, 25, 6, 5), border_radius=2)
    pygame.draw.ellipse(s, shade(o, -28), (7, 14, 28, 15))
    pygame.draw.ellipse(s, o, (7, 12, 28, 14))
    pygame.draw.ellipse(s, shade(o, 30), (11, 12, 18, 5))
    if sk.get("patches"):
        pygame.draw.ellipse(s, sk["patches"][0], (9, 12, 11, 9))
        pygame.draw.ellipse(s, sk["patches"][1], (22, 18, 9, 7))
    pygame.draw.ellipse(s, sk["belly"], (14, 21, 16, 6))
    if sk.get("stripes"):
        for sx in (14, 20, 26):
            pygame.draw.line(s, d, (sx, 13), (sx + 2, 18), 2)
    if sk.get("stars"):
        for px, py in ((12, 16), (20, 14), (28, 18), (24, 22)):
            pygame.draw.circle(s, (230, 220, 255), (px, py), 1)
    pygame.draw.circle(s, o, (34, 15), 9)
    pygame.draw.ellipse(s, shade(o, 30), (29, 8, 9, 5))
    if sk.get("mask"):
        pygame.draw.circle(s, d, (39, 17), 5)
    pygame.draw.polygon(s, d, [(27, 9), (28, 1), (34, 7)])
    pygame.draw.polygon(s, d, [(36, 7), (41, 1), (42, 10)])
    pygame.draw.polygon(s, (255, 170, 170), [(29, 7), (29, 3), (32, 6)])
    pygame.draw.circle(s, sk["eye"], (37, 13), 3)
    pygame.draw.circle(s, sk["iris"], (38, 13), 2)
    pygame.draw.circle(s, (255, 110, 140), (42, 17), 2)
    pygame.draw.line(s, (60, 40, 30), (40, 19), (44, 21), 1)
    return s


def grid_to_surface(grid, w, h, scale=2):
    s = surf(w * scale, h * scale)
    for y in range(h):
        for x in range(w):
            c = grid[y][x]
            if c:
                pygame.draw.rect(s, c, (x * scale, y * scale, scale, scale))
    return s


def sample_grid(img, w, h, scale=2):
    g = []
    for y in range(h):
        row = []
        for x in range(w):
            px = img.get_at((x * scale, y * scale))
            row.append((int(px[0]), int(px[1]), int(px[2])) if px[3] > 110 else None)
        g.append(row)
    return g


def install_skin(idx, side_frames, tops):
    """side_frames: 3 sprites sin contorno. tops: dict direccion -> sprite sin contorno."""
    for key in ("cat_top", "cat_side", "cat_parade"):
        A.setdefault(key, [])
        while len(A[key]) <= idx:
            A[key].append(None)
    A["cat_top"][idx] = {d: outlined(tops[d]) for d in tops}
    sides, parade = [], []
    for f in side_frames:
        o = outlined(f)
        sides.append({1: o, -1: flipx(o)})
        parade.append(pygame.transform.scale(o, (68, 53)))
    A["cat_side"][idx] = sides
    A["cat_parade"][idx] = parade


def install_custom(idx, side_grid, top_grid):
    """Crea los sprites de una skin dibujada por el jugador."""
    base = grid_to_surface(side_grid, 22, 17, 2)
    f1 = surf(44, 34)
    f1.blit(base, (0, 1))
    f2 = surf(44, 34)
    f2.blit(base, (0, -1))
    up = grid_to_surface(top_grid, 16, 16, 2)
    tops = {(0, -1): up, (1, 0): pygame.transform.rotate(up, -90),
            (-1, 0): pygame.transform.rotate(up, 90), (0, 1): pygame.transform.rotate(up, 180)}
    tops[(0, 0)] = tops[(1, 0)]
    install_skin(idx, [base, f1, f2], tops)


def template_grids(skin):
    skin = skin % N_BUILTIN
    return sample_grid(RAW_SIDE[skin], 22, 17), sample_grid(RAW_TOP[skin], 16, 16)


def decode_grid(rows, w, h):
    g = []
    for y in range(h):
        row = []
        for x in range(w):
            try:
                v = rows[y][x]
                row.append((int(v[0:2], 16), int(v[2:4], 16), int(v[4:6], 16)) if v else None)
            except Exception:
                row.append(None)
        g.append(row)
    return g


def encode_grid(g):
    return [["%02x%02x%02x" % c if c else "" for c in row] for row in g]


# ---- otros personajes -------------------------------------------------------
def make_mouse():
    s = surf(32, 32)
    g = (178, 178, 194)
    pygame.draw.lines(s, (240, 160, 170), False, [(26, 22), (31, 18), (30, 12)], 2)
    pygame.draw.ellipse(s, shade(g, -30), (5, 14, 22, 14))
    pygame.draw.ellipse(s, g, (5, 12, 22, 14))
    pygame.draw.circle(s, g, (9, 20), 7)
    pygame.draw.circle(s, (240, 160, 170), (11, 12), 5)
    pygame.draw.circle(s, (255, 200, 210), (11, 12), 3)
    pygame.draw.circle(s, (240, 160, 170), (18, 11), 5)
    pygame.draw.circle(s, (255, 200, 210), (18, 11), 3)
    pygame.draw.circle(s, (0, 0, 0), (8, 19), 2)
    pygame.draw.circle(s, (255, 255, 255), (7, 18), 1)
    pygame.draw.circle(s, (255, 110, 140), (3, 22), 2)
    return s


def make_dog_top(col):
    s = surf(32, 32)
    dark = shade(col, -60)
    light = shade(col, 60)
    pygame.draw.ellipse(s, dark, (1, 5, 9, 16))
    pygame.draw.ellipse(s, dark, (22, 5, 9, 16))
    pygame.draw.circle(s, col, (16, 15), 12)
    pygame.draw.ellipse(s, shade(col, 25), (8, 5, 16, 8))
    pygame.draw.ellipse(s, light, (9, 16, 14, 14))
    pygame.draw.circle(s, (0, 0, 0), (16, 25), 3)
    pygame.draw.circle(s, (255, 255, 255), (15, 24), 1)
    for ex in (11, 21):
        pygame.draw.circle(s, (255, 255, 255), (ex, 12), 3)
        pygame.draw.circle(s, (0, 0, 0), (ex, 12), 1)
    pygame.draw.line(s, (60, 20, 20), (10, 9), (13, 10), 2)
    pygame.draw.line(s, (60, 20, 20), (22, 9), (19, 10), 2)
    return s


def make_human_top():
    s = surf(32, 32)
    pygame.draw.ellipse(s, (170, 50, 44), (1, 11, 30, 20))
    pygame.draw.ellipse(s, (210, 70, 60), (1, 9, 30, 20))
    pygame.draw.circle(s, (240, 190, 150), (16, 16), 8)
    pygame.draw.ellipse(s, (70, 45, 30), (8, 6, 16, 12))
    pygame.draw.ellipse(s, (100, 66, 44), (11, 7, 8, 5))
    pygame.draw.circle(s, (240, 190, 150), (4, 25), 3)
    pygame.draw.circle(s, (240, 190, 150), (28, 25), 3)
    return s


def make_dog_side(col, frame, k):
    s = surf(64, 44)
    dark = shade(col, -60)
    light = shade(col, 60)
    pygame.draw.line(s, dark, (10, 16), (1, 6), 5)
    legs = [(12, 20, 38, 46), (8, 24, 34, 42)][frame % 2]
    for i, lx in enumerate(legs):
        pygame.draw.rect(s, dark if i % 2 else col, (lx, 30, 7, 14), border_radius=2)
    pygame.draw.ellipse(s, shade(col, -25), (6, 12, 42, 24))
    pygame.draw.ellipse(s, col, (6, 10, 42, 22))
    pygame.draw.ellipse(s, shade(col, 25), (12, 10, 26, 7))
    pygame.draw.ellipse(s, light, (14, 24, 26, 9))
    pygame.draw.circle(s, col, (50, 17), 11)
    pygame.draw.rect(s, light, (52, 17, 12, 10), border_radius=4)
    pygame.draw.circle(s, (0, 0, 0), (62, 18), 3)
    pygame.draw.ellipse(s, dark, (41, 6, 9, 17))
    pygame.draw.circle(s, (255, 255, 255), (54, 13), 3)
    pygame.draw.circle(s, (0, 0, 0), (55, 13), 2)
    pygame.draw.line(s, (50, 20, 20), (51, 9), (57, 11), 2)
    pygame.draw.line(s, (200, 30, 30), (44, 22), (50, 26), 4)
    pygame.draw.circle(s, (255, 210, 60), (47, 27), 2)
    pygame.draw.polygon(s, (255, 255, 255), [(56, 27), (58, 27), (57, 31)])
    return pygame.transform.scale(s, (int(64 * k), int(44 * k)))


def make_human_side(pose):
    s = surf(96, 128)
    skin, shirt, jeans, hair = (240, 190, 150), (210, 70, 60), (50, 70, 130), (70, 45, 30)
    hip = (40, 80)

    def leg(p0, p1):
        pygame.draw.line(s, jeans, p0, p1, 13)
        pygame.draw.line(s, shade(jeans, 25), (p0[0] - 3, p0[1]), (p1[0] - 3, p1[1]), 3)

    def shoe(p):
        pygame.draw.ellipse(s, (30, 30, 30), (p[0] - 8, p[1] - 4, 22, 11))
        pygame.draw.ellipse(s, (240, 240, 240), (p[0] - 6, p[1] + 2, 18, 4))

    if pose == "kick":
        leg(hip, (34, 118)); shoe((34, 120)); leg(hip, (78, 100)); shoe((80, 100))
    elif pose == "kickback":
        leg(hip, (36, 118)); shoe((36, 120)); leg(hip, (12, 104)); shoe((6, 106))
    elif pose == "run1":
        leg(hip, (24, 116)); shoe((22, 118)); leg(hip, (58, 112)); shoe((58, 114))
    elif pose == "run2":
        leg(hip, (34, 118)); shoe((34, 120)); leg(hip, (52, 98)); shoe((52, 100))
    else:
        leg(hip, (32, 118)); shoe((30, 120)); leg(hip, (48, 118)); shoe((46, 120))
    pygame.draw.rect(s, shade(shirt, -30), (24, 40, 34, 46), border_radius=8)
    pygame.draw.rect(s, shirt, (24, 38, 34, 44), border_radius=8)
    pygame.draw.rect(s, shade(shirt, 30), (28, 40, 10, 38), border_radius=4)
    pygame.draw.rect(s, (60, 40, 30), (24, 78, 34, 5))
    pygame.draw.circle(s, (240, 210, 80), (41, 80), 3)
    pygame.draw.line(s, shirt, (30, 48), (26, 78), 10)
    pygame.draw.circle(s, skin, (26, 80), 5)
    arm = {"idle": (54, 78), "reach": (90, 56), "throw": (72, 12), "kick": (60, 72),
           "kickback": (58, 74), "run1": (66, 70), "run2": (40, 72), "hurt": (66, 38),
           "tired": (54, 90)}.get(pose, (54, 78))
    pygame.draw.line(s, shirt, (50, 48), arm, 10)
    pygame.draw.circle(s, skin, arm, 6)
    pygame.draw.circle(s, shade(skin, -25), (42, 26), 16)
    pygame.draw.circle(s, skin, (42, 24), 16)
    pygame.draw.circle(s, (250, 150, 130), (52, 29), 4)
    pygame.draw.ellipse(s, hair, (26, 5, 34, 17))
    pygame.draw.ellipse(s, shade(hair, 30), (32, 6, 14, 6))
    if pose == "hurt":
        for ex in (38, 50):
            pygame.draw.line(s, (0, 0, 0), (ex - 3, 21), (ex + 3, 27), 2)
            pygame.draw.line(s, (0, 0, 0), (ex - 3, 27), (ex + 3, 21), 2)
    elif pose == "tired":
        pygame.draw.line(s, (0, 0, 0), (36, 24), (44, 24), 3)
        pygame.draw.line(s, (0, 0, 0), (50, 24), (58, 24), 3)
        pygame.draw.circle(s, (120, 30, 30), (49, 34), 4)
        for sx, sy in ((64, 6), (68, 18), (22, 14)):
            pygame.draw.ellipse(s, (130, 205, 255), (sx, sy, 6, 10))
    else:
        pygame.draw.line(s, (0, 0, 0), (36, 18), (46, 21), 3)
        pygame.draw.line(s, (0, 0, 0), (52, 21), (58, 18), 3)
        pygame.draw.circle(s, (255, 255, 255), (42, 25), 3)
        pygame.draw.circle(s, (255, 255, 255), (54, 25), 3)
        pygame.draw.circle(s, (0, 0, 0), (43, 25), 2)
        pygame.draw.circle(s, (0, 0, 0), (55, 25), 2)
    if pose != "tired":
        pygame.draw.line(s, (120, 30, 30), (44, 34), (56, 32), 2)
    return s


def make_vac():
    s = surf(32, 28)
    pygame.draw.rect(s, (150, 20, 34), (2, 8, 26, 14), border_radius=6)
    pygame.draw.rect(s, (214, 48, 58), (2, 6, 26, 14), border_radius=6)
    pygame.draw.rect(s, (255, 120, 120), (6, 7, 14, 4), border_radius=2)
    pygame.draw.rect(s, (60, 60, 70), (0, 12, 8, 8), border_radius=3)
    pygame.draw.circle(s, (30, 30, 30), (9, 24), 4)
    pygame.draw.circle(s, (30, 30, 30), (23, 24), 4)
    pygame.draw.circle(s, (180, 180, 190), (9, 24), 1)
    pygame.draw.circle(s, (180, 180, 190), (23, 24), 1)
    pygame.draw.circle(s, (255, 255, 255), (20, 12), 4)
    pygame.draw.circle(s, (0, 0, 0), (21, 12), 2)
    pygame.draw.line(s, (0, 0, 0), (15, 6), (25, 9), 3)
    return s


def make_bird(frame):
    s = surf(38, 28)
    pygame.draw.ellipse(s, (50, 70, 140), (6, 9, 24, 14))
    pygame.draw.ellipse(s, (90, 120, 200), (8, 9, 18, 8))
    pygame.draw.polygon(s, (50, 70, 140), [(8, 14), (0, 10), (4, 18)])
    if frame == 0:
        pygame.draw.polygon(s, (110, 150, 230), [(12, 12), (22, 12), (16, 0)])
    else:
        pygame.draw.polygon(s, (110, 150, 230), [(12, 16), (24, 16), (18, 27)])
    pygame.draw.circle(s, (50, 70, 140), (29, 12), 6)
    pygame.draw.polygon(s, (255, 170, 40), [(33, 11), (38, 13), (33, 15)])
    pygame.draw.circle(s, (255, 255, 255), (30, 11), 2)
    pygame.draw.circle(s, (0, 0, 0), (31, 11), 1)
    pygame.draw.line(s, (200, 30, 30), (28, 7), (33, 8), 2)
    return s


def make_spring(state):
    s = surf(32, 20)
    h = 8 if state == 0 else 16
    pygame.draw.rect(s, (90, 90, 110), (4, 17, 24, 3), border_radius=1)
    for i in range(4):
        y = 17 - int((i + 1) * h / 4)
        pygame.draw.line(s, (220, 220, 235), (7, y), (25, y + 2), 3)
    pygame.draw.rect(s, (230, 70, 70), (3, 17 - h - 3, 26, 5), border_radius=2)
    return s


ITEM_COL = {"life": (235, 60, 100), "heal": (225, 70, 70), "speed": (250, 190, 40),
            "shield": (60, 195, 240), "fly": (120, 185, 255), "sense": (170, 90, 230),
            "slow": (130, 110, 230), "ball": (90, 200, 100)}


def make_item_icon(kind, size=30):
    s = surf(30, 30)
    c = ITEM_COL[kind]
    wh = (255, 255, 255)
    pygame.draw.circle(s, (30, 20, 40), (15, 15), 15)
    pygame.draw.circle(s, wh, (15, 15), 14)
    pygame.draw.circle(s, c, (15, 15), 12)
    pygame.draw.circle(s, shade(c, 70), (11, 10), 4)
    if kind == "life":
        hs = surf(18, 18)
        heart_shape(hs, wh, 18)
        s.blit(hs, (6, 7))
    elif kind == "heal":
        pygame.draw.rect(s, wh, (13, 7, 4, 16))
        pygame.draw.rect(s, wh, (7, 13, 16, 4))
    elif kind == "speed":
        pygame.draw.polygon(s, wh, [(17, 4), (9, 17), (14, 17), (12, 27), (22, 13), (16, 13)])
    elif kind == "shield":
        pygame.draw.polygon(s, wh, [(15, 5), (24, 9), (22, 18), (15, 26), (8, 18), (6, 9)])
        pygame.draw.polygon(s, c, [(15, 9), (20, 11), (19, 17), (15, 21), (11, 17), (10, 11)])
    elif kind == "fly":
        pygame.draw.ellipse(s, wh, (3, 9, 13, 11))
        pygame.draw.ellipse(s, wh, (14, 9, 13, 11))
        pygame.draw.circle(s, (255, 230, 120), (15, 17), 4)
    elif kind == "sense":
        pygame.draw.ellipse(s, wh, (4, 9, 22, 13))
        pygame.draw.circle(s, (90, 40, 150), (15, 15), 5)
        pygame.draw.ellipse(s, (0, 0, 0), (14, 11, 3, 8))
    elif kind == "slow":
        pygame.draw.polygon(s, wh, [(8, 6), (22, 6), (15, 15)])
        pygame.draw.polygon(s, wh, [(15, 15), (8, 25), (22, 25)])
    elif kind == "ball":
        pygame.draw.circle(s, (240, 60, 60), (15, 15), 8)
        pygame.draw.circle(s, (255, 220, 60), (15, 15), 8, 2)
        pygame.draw.line(s, wh, (8, 15), (22, 15), 2)
    return s


def make_qblock(frame):
    s = surf(T, T)
    base = (250, 196, 44) if frame == 0 else (255, 224, 90)
    s.fill(base)
    pygame.draw.rect(s, (130, 80, 10), (0, 0, T, T), 3)
    pygame.draw.rect(s, shade(base, 40), (3, 3, T - 6, 4))
    for rx, ry in ((4, 4), (T - 7, 4), (4, T - 7), (T - 7, T - 7)):
        pygame.draw.circle(s, (130, 80, 10), (rx + 1, ry + 1), 2)
    f = font(24, True)
    t1 = f.render("?", True, (110, 60, 0))
    t2 = f.render("?", True, (255, 250, 220))
    s.blit(t1, (T // 2 - t1.get_width() // 2 + 1, 5))
    s.blit(t2, (T // 2 - t2.get_width() // 2, 3))
    return s


def make_used_block():
    s = surf(T, T)
    s.fill((120, 92, 74))
    pygame.draw.rect(s, (70, 50, 40), (0, 0, T, T), 3)
    pygame.draw.rect(s, (150, 120, 98), (3, 3, T - 6, 4))
    for rx, ry in ((4, 4), (T - 7, 4), (4, T - 7), (T - 7, T - 7)):
        pygame.draw.circle(s, (70, 50, 40), (rx + 1, ry + 1), 2)
    return s


def make_fish():
    s = surf(20, 14)
    pygame.draw.ellipse(s, (90, 190, 250), (2, 2, 14, 10))
    pygame.draw.polygon(s, (60, 150, 230), [(14, 7), (20, 1), (20, 13)])
    pygame.draw.circle(s, (255, 255, 255), (6, 6), 2)
    pygame.draw.circle(s, (0, 0, 0), (6, 6), 1)
    pygame.draw.line(s, (200, 240, 255), (8, 4), (12, 4), 1)
    return s


# ---- temas de nivel ---------------------------------------------------------
THEMES = [
    dict(name="JARDÍN", sky=((90, 160, 240), (200, 235, 255)), sky2=((50, 40, 110), (240, 150, 100)),
         dirt=(112, 74, 42), top=(72, 176, 72), top2=(120, 214, 104), bg=(70, 150, 90), slip=False),
    dict(name="DESIERTO", sky=((235, 150, 70), (255, 225, 150)), sky2=((20, 20, 60), (130, 80, 100)),
         dirt=(196, 150, 84), top=(236, 206, 118), top2=(252, 232, 160), bg=(205, 150, 90), slip=False),
    dict(name="NIEVE", sky=((120, 165, 220), (225, 238, 255)), sky2=((15, 25, 60), (90, 110, 170)),
         dirt=(110, 128, 160), top=(238, 246, 255), top2=(255, 255, 255), bg=(150, 170, 210), slip=True),
    dict(name="CAVERNA", sky=((30, 24, 48), (70, 52, 90)), sky2=((20, 32, 44), (44, 78, 88)),
         dirt=(78, 68, 92), top=(122, 112, 142), top2=(164, 154, 184), bg=(50, 40, 70), slip=False),
    dict(name="VOLCÁN", sky=((60, 16, 22), (210, 84, 34)), sky2=((30, 6, 12), (150, 44, 22)),
         dirt=(78, 40, 40), top=(196, 66, 38), top2=(255, 140, 50), bg=(60, 25, 25), slip=False),
]


def theme_of(n):
    """Nivel n (1-10) -> (tema, es_la_version_nocturna)."""
    return min(4, (n - 1) // 2), (n - 1) % 2 == 1


_sky_cache = {}


def sky_surface(top, bot):
    key = (top, bot)
    if key not in _sky_cache:
        s = pygame.Surface((W, H))
        for y in range(H):
            t = y / H
            pygame.draw.line(s, tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(3)), (0, y), (W, y))
        _sky_cache[key] = s
    return _sky_cache[key]


def make_tiles(th):
    dirt = surf(T, T)
    dirt.fill(th["dirt"])
    rnd = random.Random(5)
    for _ in range(11):
        pygame.draw.circle(dirt, shade(th["dirt"], -26), (rnd.randint(2, 29), rnd.randint(2, 29)), rnd.randint(1, 3))
    for _ in range(4):
        pygame.draw.circle(dirt, shade(th["dirt"], 22), (rnd.randint(2, 29), rnd.randint(2, 29)), 1)
    top = dirt.copy()
    pygame.draw.rect(top, th["top"], (0, 0, T, 9))
    pygame.draw.rect(top, th["top2"], (0, 0, T, 3))
    for gx in range(0, T, 6):
        pygame.draw.polygon(top, th["top"], [(gx, 8), (gx + 3, 14), (gx + 6, 8)])
    crate = surf(T, T)
    crate.fill((170, 120, 60))
    pygame.draw.rect(crate, (90, 55, 25), (0, 0, T, T), 3)
    pygame.draw.line(crate, (90, 55, 25), (2, 2), (T - 3, T - 3), 3)
    pygame.draw.line(crate, (90, 55, 25), (T - 3, 2), (2, T - 3), 3)
    pygame.draw.rect(crate, (210, 160, 90), (4, 4, T - 8, 3))
    plank = surf(T, T)
    pygame.draw.rect(plank, (150, 100, 55), (0, 0, T, 16))
    pygame.draw.rect(plank, (190, 140, 80), (0, 0, T, 4))
    pygame.draw.rect(plank, (95, 60, 30), (0, 0, T, 16), 2)
    pygame.draw.line(plank, (95, 60, 30), (T // 2, 2), (T // 2, 14), 1)
    return dict(dirt=dirt, top=top, crate=crate, plank=plank)


def make_spike():
    spike = surf(T, T)
    for sx in (2, 17):
        pygame.draw.polygon(spike, (215, 220, 232), [(sx, T), (sx + 6, T - 20), (sx + 13, T)])
        pygame.draw.polygon(spike, (110, 116, 134), [(sx + 6, T - 20), (sx + 13, T), (sx + 6, T)])
    return spike


def make_mover():
    s = surf(96, 16)
    pygame.draw.rect(s, (110, 74, 40), (0, 0, 96, 16), border_radius=4)
    pygame.draw.rect(s, (170, 120, 70), (0, 0, 96, 5), border_radius=4)
    for x in (8, 48, 88):
        pygame.draw.circle(s, (60, 60, 70), (x, 9), 3)
    pygame.draw.rect(s, (60, 60, 70), (0, 0, 96, 16), 2, border_radius=4)
    return s


# ---- laberinto --------------------------------------------------------------
MAZE_PALS = [
    ((14, 24, 84), (70, 150, 255), (30, 70, 200), (10, 8, 28)),
    ((10, 60, 40), (80, 235, 140), (30, 150, 90), (6, 18, 14)),
    ((60, 20, 90), (210, 130, 255), (130, 60, 200), (16, 8, 28)),
    ((90, 50, 10), (255, 190, 80), (200, 120, 30), (24, 14, 6)),
    ((90, 16, 28), (255, 110, 130), (200, 50, 70), (26, 6, 10)),
    ((10, 62, 80), (90, 230, 255), (30, 150, 190), (6, 20, 26)),
    ((70, 70, 20), (240, 240, 100), (170, 170, 40), (22, 22, 6)),
    ((60, 30, 70), (255, 140, 220), (190, 70, 150), (20, 8, 24)),
    ((20, 40, 100), (140, 190, 255), (70, 110, 230), (8, 12, 32)),
    ((70, 10, 70), (255, 80, 255), (190, 30, 190), (22, 4, 22)),
]


def make_maze_tiles(pal):
    fill, edge, glow, floor = MAZE_PALS[pal % len(MAZE_PALS)]
    d = {}
    fl = pygame.Surface((T, T))
    fl.fill(floor)
    pygame.draw.circle(fl, shade(floor, 30), (16, 16), 2)
    d["floor"] = fl
    for mask in range(16):
        s = pygame.Surface((T, T))
        s.fill(fill)
        pygame.draw.rect(s, shade(fill, 14), (5, 5, T - 10, T - 10), 1)
        if mask & 1:
            pygame.draw.rect(s, glow, (0, 0, T, 6)); pygame.draw.rect(s, edge, (0, 0, T, 3))
        if mask & 2:
            pygame.draw.rect(s, glow, (T - 6, 0, 6, T)); pygame.draw.rect(s, edge, (T - 3, 0, 3, T))
        if mask & 4:
            pygame.draw.rect(s, glow, (0, T - 6, T, 6)); pygame.draw.rect(s, edge, (0, T - 3, T, 3))
        if mask & 8:
            pygame.draw.rect(s, glow, (0, 0, 6, T)); pygame.draw.rect(s, edge, (0, 0, 3, T))
        d[mask] = s
    return d


def build_fog():
    big = surf(2 * W, 2 * H)
    big.fill((4, 4, 18, 238))
    for rad in range(560, 150, -6):
        a = int(238 * max(0.0, (rad - 250) / (560 - 250)))
        pygame.draw.circle(big, (4, 4, 18, a), (W, H), rad)
    return big


# ---- icono de la ventana ----------------------------------------------------
def make_window_icon(size=64):
    s = surf(64, 64)
    pygame.draw.rect(s, (60, 40, 130), (0, 0, 64, 64), border_radius=14)
    pygame.draw.rect(s, (30, 80, 180), (0, 32, 64, 32), border_radius=14)
    pygame.draw.rect(s, (60, 40, 130), (0, 32, 64, 14))
    pygame.draw.circle(s, (255, 244, 200), (50, 14), 6)
    o, d = (245, 150, 50), (190, 95, 25)
    pygame.draw.polygon(s, d, [(10, 30), (13, 8), (28, 22)])
    pygame.draw.polygon(s, d, [(54, 30), (51, 8), (36, 22)])
    pygame.draw.polygon(s, (255, 170, 170), [(14, 24), (15, 14), (22, 21)])
    pygame.draw.polygon(s, (255, 170, 170), [(50, 24), (49, 14), (42, 21)])
    pygame.draw.ellipse(s, o, (8, 18, 48, 40))
    pygame.draw.ellipse(s, (255, 225, 170), (20, 38, 24, 16))
    for ex in (21, 43):
        pygame.draw.ellipse(s, (255, 255, 255), (ex - 6, 28, 12, 13))
        pygame.draw.ellipse(s, (90, 210, 90), (ex - 4, 30, 8, 10))
        pygame.draw.ellipse(s, (0, 0, 0), (ex - 1, 30, 3, 10))
    pygame.draw.polygon(s, (255, 110, 140), [(29, 42), (35, 42), (32, 46)])
    for sx in (-1, 1):
        pygame.draw.line(s, (60, 40, 30), (32 + sx * 6, 47), (32 + sx * 22, 44), 1)
        pygame.draw.line(s, (60, 40, 30), (32 + sx * 6, 50), (32 + sx * 22, 52), 1)
    for sx in (24, 32, 40):
        pygame.draw.line(s, d, (sx, 20), (sx, 26), 2)
    return s


# ---- construccion de todo el arte -------------------------------------------
def build_art():
    for kind in ("full", "half", "empty"):
        A["heart_" + kind] = make_heart(26, kind)
        A["hearts_" + kind] = make_heart(15, kind)
    first_sides = None
    for i, sk in enumerate(SKINS):
        raw_sides = [make_cat_side(f, sk) for f in range(3)]
        tops = {d: make_cat_top(d[0], d[1], sk) for d in DIRS}
        tops[(0, 0)] = tops[(1, 0)]
        RAW_SIDE.append(raw_sides[0])
        RAW_TOP.append(make_cat_top(0, -1, sk))
        install_skin(i, raw_sides, tops)
        if first_sides is None:
            first_sides = (raw_sides, tops)
    for i in range(N_CUSTOM):
        install_skin(N_BUILTIN + i, first_sides[0], first_sides[1])
    m = outlined(make_mouse())
    A["mouse"] = m
    A["mouse_r"] = flipx(m)
    A["mouse_small"] = pygame.transform.scale(make_mouse(), (22, 22))
    dim = A["mouse_small"].copy()
    dim.set_alpha(55)
    A["mouse_dim"] = dim
    cols = {"dog0": (170, 110, 60), "dog1": (120, 120, 135)}
    A["dog_top"] = {k: outlined(make_dog_top(c)) for k, c in cols.items()}
    A["human_top"] = outlined(make_human_top())
    A["dog_side"] = []
    for c in cols.values():
        frames = []
        for f in range(2):
            sp = outlined(make_dog_side(c, f, 1.5))
            frames.append({1: sp, -1: flipx(sp)})
        A["dog_side"].append(frames)
    A["human_side"] = {}
    for p in ("idle", "reach", "throw", "kick", "kickback", "run1", "run2", "hurt", "tired"):
        sp = outlined(make_human_side(p))
        A["human_side"][p] = {1: sp, -1: flipx(sp)}
    A["parade_dog"] = [pygame.transform.scale(A["dog_side"][i][0][1], (72, 50)) for i in (0, 1)]
    A["parade_human"] = pygame.transform.scale(A["human_side"]["run1"][1], (72, 96))
    v = outlined(make_vac())
    A["vac"] = {1: v, -1: flipx(v)}
    A["bird"] = []
    for f in range(2):
        b = outlined(make_bird(f))
        A["bird"].append({1: b, -1: flipx(b)})
    A["spring"] = [outlined(make_spring(0)), outlined(make_spring(1))]
    A["items"] = {k: make_item_icon(k) for k in ITEM_KINDS}
    A["qblock"] = [make_qblock(0), make_qblock(1)]
    A["used"] = make_used_block()
    A["fish"] = outlined(make_fish())
    A["tiles"] = [make_tiles(th) for th in THEMES]
    A["spike"] = make_spike()
    A["mover"] = make_mover()
    ball = surf(22, 22)
    pygame.draw.circle(ball, (240, 60, 60), (11, 11), 10)
    pygame.draw.circle(ball, (255, 220, 60), (11, 11), 10, 3)
    pygame.draw.line(ball, (255, 255, 255), (3, 11), (19, 11), 2)
    A["ball"] = outlined(ball)
    A["catball"] = A["ball"]
    fb = surf(26, 26)
    pygame.draw.circle(fb, (250, 250, 250), (13, 13), 12)
    pygame.draw.polygon(fb, (30, 30, 30), [(13, 7), (19, 11), (17, 18), (9, 18), (7, 11)])
    pygame.draw.circle(fb, (30, 30, 30), (13, 13), 12, 2)
    A["football"] = outlined(fb)
    flag = surf(40, 100)
    pygame.draw.rect(flag, (220, 220, 230), (6, 0, 4, 100))
    pygame.draw.polygon(flag, (230, 60, 80), [(10, 4), (38, 16), (10, 30)])
    pygame.draw.circle(flag, (255, 255, 255), (20, 17), 4)
    pygame.draw.circle(flag, (255, 255, 255), (4, 2), 4)
    A["flag"] = outlined(flag)
    A["fog"] = build_fog()
    A["mz"] = {}
    rnd = random.Random(3)
    towers, x = [], 0
    while x < 1600:
        w, h = rnd.randint(50, 110), rnd.randint(90, 280)
        towers.append((x, w, h, [(rnd.randint(6, w - 14), rnd.randint(8, h - 14)) for _ in range(7)]))
        x += w + rnd.randint(0, 24)
    A["menu_towers"] = towers


def maze_tiles(stage):
    if stage not in A["mz"]:
        A["mz"][stage] = make_maze_tiles(stage)
    return A["mz"][stage]


# ----------------------------------------------------------------------------
#  FONDOS
# ----------------------------------------------------------------------------
def draw_theme_bg(dst, theme, dark, camx, t):
    th = THEMES[theme]
    top, bot = th["sky2"] if dark else th["sky"]
    dst.blit(sky_surface(top, bot), (0, 0))
    base = th["bg"]
    # sol / luna / estrellas
    if dark or theme == 3:
        for i in range(48):
            b = 150 + int(90 * abs(math.sin((t + i * 17) * 0.03)))
            pygame.draw.circle(dst, (b, b, min(255, b + 20)), ((i * 167 - int(camx * 0.03)) % W, (i * 53) % 300), 1)
    if theme != 3:
        if dark:
            pygame.draw.circle(dst, (255, 250, 215), (650, 90), 36)
            pygame.draw.circle(dst, (235, 230, 195), (638, 82), 7)
        else:
            pygame.draw.circle(dst, (255, 240, 150), (650, 90), 52)
            pygame.draw.circle(dst, (255, 252, 210), (650, 90), 34)
    far = shade(base, -45 if dark else -15)
    near = shade(base, -70 if dark else -40)

    def rep(period, speed, fn):
        off = int(camx * speed)
        n = W // period + 3
        for i in range(-1, n):
            fn(i * period - off % period, i)

    if theme == 0:        # colinas, arboles, nubes
        rep(260, 0.08, lambda x, i: pygame.draw.ellipse(dst, shade((255, 255, 255), -60 if dark else 0),
                                                         (x, 60 + (i * 37) % 70, 120, 36)))
        rep(300, 0.2, lambda x, i: pygame.draw.ellipse(dst, far, (x - 60, 360 + (i * 41) % 30, 340, 260)))
        rep(220, 0.4, lambda x, i: pygame.draw.ellipse(dst, near, (x - 40, 400 + (i * 29) % 25, 260, 220)))
        def tree(x, i):
            pygame.draw.rect(dst, (90, 60, 40), (x + 18, 410, 8, 70))
            pygame.draw.circle(dst, shade(near, 20), (x + 22, 400), 26)
        rep(190, 0.55, tree)
    elif theme == 1:      # dunas y cactus
        rep(340, 0.15, lambda x, i: pygame.draw.ellipse(dst, far, (x - 80, 380 + (i * 31) % 40, 460, 300)))
        rep(260, 0.3, lambda x, i: pygame.draw.ellipse(dst, near, (x - 50, 420 + (i * 23) % 30, 340, 240)))
        def cactus(x, i):
            c = (60, 130, 70)
            pygame.draw.rect(dst, c, (x, 400, 12, 80), border_radius=5)
            pygame.draw.rect(dst, c, (x - 12, 425, 10, 8), border_radius=3)
            pygame.draw.rect(dst, c, (x - 12, 410, 8, 22), border_radius=3)
            pygame.draw.rect(dst, c, (x + 14, 435, 12, 8), border_radius=3)
            pygame.draw.rect(dst, c, (x + 20, 420, 8, 24), border_radius=3)
        rep(330, 0.5, cactus)
    elif theme == 2:      # montañas, pinos, nieve cayendo
        def mount(x, i):
            h = 190 + (i * 53) % 80
            pygame.draw.polygon(dst, far, [(x - 120, 480), (x + 40, 480 - h), (x + 200, 480)])
            pygame.draw.polygon(dst, (245, 250, 255), [(x - 10, 480 - h + 52), (x + 40, 480 - h), (x + 90, 480 - h + 52)])
        rep(280, 0.12, mount)
        def pine(x, i):
            for k in range(3):
                pygame.draw.polygon(dst, shade(near, -10), [(x, 470 - k * 30), (x + 20, 440 - k * 30), (x + 40, 470 - k * 30)])
        rep(150, 0.45, pine)
        for i in range(40):
            fx = (i * 83 + t * (1 + i % 3) * 0.4) % W
            fy = (i * 47 + t * (1 + i % 2)) % H
            pygame.draw.circle(dst, (255, 255, 255), (int(fx), int(fy)), 2)
    elif theme == 3:      # estalactitas y cristales
        def stal(x, i):
            h = 70 + (i * 41) % 90
            pygame.draw.polygon(dst, far, [(x, 0), (x + 46, 0), (x + 23, h)])
        rep(110, 0.25, stal)
        def stag(x, i):
            h = 60 + (i * 37) % 70
            pygame.draw.polygon(dst, near, [(x, 480), (x + 50, 480), (x + 25, 480 - h)])
        rep(160, 0.5, stag)
        def crystal(x, i):
            b = 150 + int(90 * abs(math.sin((t + i * 40) * 0.05)))
            pygame.draw.polygon(dst, (b // 2, b, 255), [(x, 300 + (i * 31) % 90), (x + 8, 288 + (i * 31) % 90),
                                                       (x + 16, 300 + (i * 31) % 90), (x + 8, 318 + (i * 31) % 90)])
        rep(210, 0.35, crystal)
    else:                 # volcan, brasas
        def volc(x, i):
            pygame.draw.polygon(dst, far, [(x - 140, 480), (x - 40, 250), (x + 40, 250), (x + 140, 480)])
            pygame.draw.polygon(dst, (255, 120, 30), [(x - 38, 250), (x, 232), (x + 38, 250), (x, 262)])
        rep(520, 0.12, volc)
        rep(240, 0.3, lambda x, i: pygame.draw.ellipse(dst, near, (x - 60, 430 + (i * 29) % 20, 340, 230)))
        for i in range(36):
            ex = (i * 97 + int(camx * 0.2)) % W
            ey = (H - (i * 61 + t * (1 + i % 3)) % H)
            pygame.draw.circle(dst, (255, 150 + (i * 7) % 90, 40), (int(ex), int(ey)), 2)


def draw_menu_bg(dst, t, skin):
    dst.blit(sky_surface((15, 15, 40), (60, 50, 100)), (0, 0))
    for i in range(55):
        x, y = (i * 149) % W, (i * 71) % 330
        b = 140 + int(100 * abs(math.sin((t + i * 13) * 0.03)))
        pygame.draw.circle(dst, (b, b, min(255, b + 20)), (x, y), 1 + (i % 2))
    pygame.draw.circle(dst, (255, 250, 215), (650, 100), 44)
    pygame.draw.circle(dst, (235, 230, 195), (636, 90), 8)
    pygame.draw.circle(dst, (235, 230, 195), (664, 114), 6)
    off = int(t * 0.4) % 1600
    col = shade((60, 50, 100), -50)
    for rep in (-1, 0, 1):
        for x, w, h, wins in A["menu_towers"]:
            sx = x - off + rep * 1600
            if sx > W or sx + w < 0:
                continue
            pygame.draw.rect(dst, col, (sx, 520 - h, w, h + 4))
            for wx, wy in wins:
                pygame.draw.rect(dst, (255, 230, 120), (sx + wx, 520 - h + wy, 6, 8))
    pygame.draw.rect(dst, (38, 34, 66), (0, 520, W, 88))
    pygame.draw.rect(dst, (90, 80, 140), (0, 520, W, 4))
    px = (t * 2.6) % (W + 760)
    frame = (t // 6) % 2
    items = [(A["mouse_r"], 0, 520 - 34), (A["cat_parade"][skin][frame], 95, 520 - 53),
             (A["parade_dog"][0], 205, 520 - 50), (A["parade_dog"][1], 290, 520 - 50),
             (A["parade_human"], 400, 520 - 96)]
    for img, dx, y in items:
        x = px - dx - 40
        if -120 < x < W + 20:
            dst.blit(img, (x, y + (3 if (t // 6) % 2 else 0)))


# ----------------------------------------------------------------------------
#  HUD
# ----------------------------------------------------------------------------
def draw_hearts(dst, x, y, hp, maxh=5):
    for i in range(maxh):
        kind = "full" if hp >= i + 1 else ("half" if hp >= i + 0.5 else "empty")
        dst.blit(A["heart_" + kind], (x + i * 29, y))


def hearts_count(hp):
    return max(MAX_HEARTS_NORMAL, int(math.ceil(hp - 0.001)))


def draw_powers(dst, g, x, y):
    i = 0
    for k, v in g.powers.items():
        dst.blit(A["items"][k], (x + i * 38, y))
        pygame.draw.rect(dst, (20, 20, 40), (x + i * 38, y + 32, 30, 5))
        pygame.draw.rect(dst, (120, 255, 150) if v > 120 else (255, 90, 90),
                         (x + i * 38, y + 32, int(30 * min(1.0, v / POWER_DUR[k])), 5))
        i += 1
    if g.ball_ammo > 0:
        dst.blit(A["items"]["ball"], (x + i * 38, y))
        txt(dst, "x%d" % g.ball_ammo, 16, (255, 255, 255), x + i * 38 + 6, y + 30)


# ----------------------------------------------------------------------------
#  PARTICULAS Y TEXTOS FLOTANTES
# ----------------------------------------------------------------------------
class Parts:
    def __init__(self):
        self.p = []
        self.texts = []

    def burst(self, x, y, color, n=10, spd=3.0, life=30, grav=0.12, size=3):
        for _ in range(n):
            a = random.uniform(0, 6.283)
            v = random.uniform(0.3, 1.0) * spd
            self.p.append([x, y, math.cos(a) * v, math.sin(a) * v - 1, life, color, size, grav])

    def text(self, x, y, s, color=(255, 255, 255)):
        self.texts.append([x, y, s, 55, color])

    def update(self):
        for q in self.p:
            q[0] += q[2]
            q[1] += q[3]
            q[3] += q[7]
            q[4] -= 1
        self.p = [q for q in self.p if q[4] > 0]
        for tx in self.texts:
            tx[1] -= 0.8
            tx[3] -= 1
        self.texts = [tx for tx in self.texts if tx[3] > 0]

    def draw(self, dst, camx=0, camy=0):
        for q in self.p:
            pygame.draw.circle(dst, q[5], (int(q[0] - camx), int(q[1] - camy)), max(1, int(q[6] * q[4] / 30) + 1))
        for tx in self.texts:
            txt(dst, tx[2], 24, tx[4], int(tx[0] - camx), int(tx[1] - camy), True)


# ----------------------------------------------------------------------------
#  GATO DE PLATAFORMAS
# ----------------------------------------------------------------------------
class Cat:
    w, h = 26, 26

    def __init__(self, x, y, game):
        self.x, self.y = float(x), float(y)
        self.game = game
        self.skin = game.skin
        self.vx = self.vy = 0.0
        self.on_ground = False
        self.face = 1
        self.inv = 0
        self.coyote = 0
        self.buf = 0
        self.atk = 0
        self.atk_cd = 0
        self.mode = "free"        # free / grabbed / thrown
        self.thrown_t = 0
        self.thrown_end = False
        self.hit_wall = False
        self.anim = 0.0
        self.ride = None
        self.bump = None
        self.trail = []
        self.tick = 0

    @property
    def rect(self):
        return pygame.Rect(int(self.x), int(self.y), self.w, self.h)

    def atk_rect(self):
        if self.atk <= 0:
            return None
        x = self.x + self.w if self.face > 0 else self.x - 36
        return pygame.Rect(int(x), int(self.y) - 8, 36, self.h + 16)

    def hurt(self, game, dmg, kb=0):
        if self.inv > 0 or self.mode == "grabbed" or game.has("shield"):
            return False
        game.damage(dmg)
        self.inv = 90
        self.vy = -7
        self.vx = kb * 7
        play("hit")
        return True

    def update(self, world, events):
        g = self.game
        keys = pygame.key.get_pressed()
        if self.inv > 0:
            self.inv -= 1
        if self.atk > 0:
            self.atk -= 1
        if self.atk_cd > 0:
            self.atk_cd -= 1
        if self.mode == "grabbed":
            return
        for e in events:
            if e.type == pygame.KEYDOWN:
                if e.key in JUMP_KEYS:
                    self.buf = 8
                if e.key in ATK_KEYS and self.atk_cd == 0 and self.mode == "free":
                    self.atk, self.atk_cd = 12, ATK_CD
                    play("scratch")
                if e.key in BALL_KEYS and self.mode == "free":
                    world.throw_ball(self)
        fly = g.has("fly") and self.mode == "free"
        if self.mode == "free":
            held = keys[pygame.K_SPACE] or keys[pygame.K_UP] or keys[pygame.K_w]
            d = int(bool(keys[pygame.K_RIGHT] or keys[pygame.K_d])) - int(bool(keys[pygame.K_LEFT] or keys[pygame.K_a]))
            maxv = 5.0 * (1.6 if g.has("speed") else 1.0)
            acc = 0.4 if self.on_ground else 0.22
            if getattr(world, "slippery", False) and self.on_ground:
                acc = 0.06
            self.vx += (d * maxv - self.vx) * acc
            if d:
                self.face = 1 if d > 0 else -1
            if fly:
                down = keys[pygame.K_DOWN] or keys[pygame.K_s]
                ay = -0.8 if held else (0.8 if down else 0.0)
                self.vy = clamp(self.vy * 0.9 + ay, -6.5, 6.5)
                self.coyote = 7
                self.buf = 0
            else:
                self.coyote = 7 if self.on_ground else max(0, self.coyote - 1)
                if self.buf > 0:
                    self.buf -= 1
                    if self.coyote > 0:
                        self.vy = -13.2
                        self.coyote = self.buf = 0
                        play("jump")
                if not held and self.vy < -5:
                    self.vy = -5
        else:
            self.thrown_t += 1
        if not fly:
            self.vy = min(self.vy + 0.62, 16)
        self.hit_wall = False
        self.move(world, self.vx, 0)
        self.move(world, 0, self.vy)
        self.x = max(0, min(self.x, world.world_w - self.w))
        self.anim += abs(self.vx) * 0.06
        if self.mode == "thrown" and self.thrown_t > 4 and (self.on_ground or self.hit_wall):
            self.mode = "free"
            self.thrown_end = True
            self.vx = 0
        self.ride = None
        if self.on_ground:
            rr = self.rect
            for mv in world.movers:
                m = mv.rect
                if rr.bottom == m.top and rr.right > m.left and rr.left < m.right:
                    self.ride = mv
                    break
        self.tick += 1
        self.trail.append((self.x, self.y))
        if len(self.trail) > 7:
            self.trail.pop(0)

    def move(self, world, dx, dy):
        if dx:
            self.x += dx
            r = self.rect
            for t in world.solids(r):
                if r.colliderect(t):
                    self.x = t.left - self.w if dx > 0 else t.right
                    self.vx = 0
                    self.hit_wall = True
                    r = self.rect
        if dy:
            self.y += dy
            self.on_ground = False
            r = self.rect
            for t in world.solids(r):
                if r.colliderect(t):
                    if dy > 0:
                        self.y = t.top - self.h
                        self.on_ground = True
                    else:
                        self.y = t.bottom
                        self.bump = (t.left // T, t.top // T)
                    self.vy = 0
                    r = self.rect
            if dy >= 0 and not self.on_ground:
                probe = pygame.Rect(int(self.x), int(self.y) + 1, self.w, self.h)
                for t in world.solids(probe):
                    if probe.colliderect(t) and t.top >= int(self.y) + self.h - 1:
                        self.y = t.top - self.h
                        self.vy = 0
                        self.on_ground = True
                        break

    def draw(self, dst, camx):
        g = self.game
        r = self.rect
        cx, cy = r.centerx - int(camx), r.centery
        if g.has("speed"):
            for i in range(len(self.trail) - 1):
                a, b = self.trail[i], self.trail[i + 1]
                pygame.draw.line(dst, (255, 225, 90), (int(a[0]) + 13 - int(camx), int(a[1]) + 13 + i % 3 * 4 - 4),
                                 (int(b[0]) + 13 - int(camx), int(b[1]) + 13 + i % 3 * 4 - 4), 2)
        if g.has("fly") and self.mode == "free":
            fl = (self.tick // 6) % 2
            wy = -8 if fl else 2
            pygame.draw.polygon(dst, (255, 255, 255), [(cx - 4 * self.face, cy - 2), (cx - 22 * self.face, cy + wy - 12),
                                                       (cx - 10 * self.face, cy + 6)])
            pygame.draw.polygon(dst, (200, 230, 255), [(cx - 4 * self.face, cy), (cx - 26 * self.face, cy + wy - 4),
                                                       (cx - 12 * self.face, cy + 8)], 2)
        if not (self.inv > 0 and (self.inv // 4) % 2 == 0 and self.mode == "free" and not g.has("shield")):
            frame = 2 if not self.on_ground else (int(self.anim) % 2 if abs(self.vx) > 0.6 else 0)
            if g.has("fly") and self.mode == "free":
                frame = 2
            img = A["cat_side"][self.skin][frame][self.face]
            dst.blit(img, (r.centerx - 22 - O - int(camx), r.bottom - 34 - O))
        if self.atk > 0:
            ar = self.atk_rect()
            for i in range(3):
                x0 = ar.left - int(camx) + (6 + i * 9 if self.face > 0 else 30 - i * 9)
                pygame.draw.line(dst, (255, 255, 255), (x0, ar.top + 2), (x0 + 6 * self.face, ar.bottom - 2), 3)
        if g.has("shield"):
            ph = self.tick * 0.15
            col = (int(140 + 115 * math.sin(ph)), int(140 + 115 * math.sin(ph + 2.1)), int(140 + 115 * math.sin(ph + 4.2)))
            pygame.draw.circle(dst, col, (cx, cy), 26, 3)
            pygame.draw.circle(dst, (255, 255, 255), (cx, cy), 30, 1)
        elif self.inv > 90 and self.mode == "free":
            pygame.draw.circle(dst, (120, 220, 255), (cx, cy), 24, 2)
        if g.has("sense"):
            pygame.draw.circle(dst, (200, 120, 255), (cx + 6 * self.face, cy - 6), 5, 1)


# ----------------------------------------------------------------------------
#  OBJETOS DE NIVEL
# ----------------------------------------------------------------------------
class CatBall:
    """Pelota que lanza el gato."""

    def __init__(self, x, y, vx, vy):
        self.x, self.y, self.vx, self.vy = float(x), float(y), vx, vy
        self.life, self.bn, self.dead = 160, 0, False

    @property
    def rect(self):
        return pygame.Rect(int(self.x) - 9, int(self.y) - 9, 18, 18)

    def update(self, world):
        self.vy += 0.4
        self.x += self.vx
        r = self.rect
        for t in world.solids(r):
            if r.colliderect(t):
                self.x -= self.vx
                self.vx = -self.vx * 0.6
                break
        self.y += self.vy
        r = self.rect
        for t in world.solids(r):
            if r.colliderect(t):
                if self.vy > 0:
                    self.y = t.top - 9
                    self.vy = -5
                    self.bn += 1
                else:
                    self.y = t.bottom + 9
                    self.vy = 1
                break
        self.life -= 1
        if self.life <= 0 or self.bn > 3 or self.y > H + 120:
            self.dead = True


class Item:
    """Power-up que sale de un bloque."""

    def __init__(self, kind, x, y):
        self.kind = kind
        self.x, self.y = float(x), float(y)
        self.vx = random.choice((-1.3, 1.3))
        self.vy = -6.5
        self.age = 0
        self.dead = False

    @property
    def rect(self):
        return pygame.Rect(int(self.x) - 13, int(self.y) - 13, 26, 26)

    def update(self, world):
        self.age += 1
        self.vy = min(self.vy + 0.35, 9)
        self.x += self.vx
        r = self.rect
        for t in world.solids(r):
            if r.colliderect(t):
                self.x -= self.vx
                self.vx = -self.vx
                break
        self.y += self.vy
        r = self.rect
        for t in world.solids(r):
            if r.colliderect(t):
                if self.vy > 0:
                    self.y = t.top - 13
                    self.vy = 0
                    self.vx *= 0.96
                else:
                    self.y = t.bottom + 13
                    self.vy = 0
                break
        if self.y > H + 120:
            self.dead = True


class Vac:
    def __init__(self, l, r, y):
        self.l, self.r = l, r
        self.x = float(l)
        self.y = y - 28
        self.dir = 1
        self.alive = True

    @property
    def rect(self):
        return pygame.Rect(int(self.x), int(self.y), 32, 28)

    def update(self):
        self.x += self.dir * 1.6
        if self.x < self.l:
            self.x, self.dir = self.l, 1
        elif self.x > self.r:
            self.x, self.dir = self.r, -1


class Bird:
    def __init__(self, x0, x1, cy, amp=22):
        self.x0, self.x1 = x0, x1
        self.x = float(x0)
        self.cy, self.amp = cy, amp
        self.y = float(cy)
        self.dir = 1
        self.t = random.uniform(0, 6)
        self.alive = True

    @property
    def rect(self):
        return pygame.Rect(int(self.x) + 2, int(self.y) + 3, 32, 20)

    def update(self):
        self.t += 0.06
        self.x += self.dir * 1.5
        if self.x < self.x0:
            self.x, self.dir = self.x0, 1
        elif self.x > self.x1:
            self.x, self.dir = self.x1, -1
        self.y = self.cy + math.sin(self.t) * self.amp


class MovingPlat:
    def __init__(self, x0, x1, y):
        self.x0, self.x1 = x0, x1
        self.x = float(x0)
        self.y = y
        self.dir = 1
        self.fdx = self.fdy = 0.0

    @property
    def rect(self):
        return pygame.Rect(int(self.x), int(self.y), 96, 16)

    def update(self):
        old = self.x
        self.x += self.dir * 1.6
        if self.x <= self.x0:
            self.x, self.dir = float(self.x0), 1
        elif self.x >= self.x1:
            self.x, self.dir = float(self.x1), -1
        self.fdx += self.x - old


# ----------------------------------------------------------------------------
#  BASE DE ESCENAS DE PLATAFORMAS
# ----------------------------------------------------------------------------
class PlatBase:
    ticks_powers = True

    def __init__(self, game, theme=0, dark=False):
        self.game = game
        self.grid = {}
        self.cat = None
        self.camx = 0.0
        self.world_w = W
        self.theme = theme
        self.dark = dark
        self.slippery = THEMES[theme]["slip"]
        self.movers = []
        self.cat_balls = []
        self.parts = Parts()
        self.acc = 0.0
        self.anim_t = 0
        self.tiles = A["tiles"][theme]

    def solids(self, r):
        res = []
        for tx in range(r.left // T - 1, r.right // T + 2):
            for ty in range(r.top // T - 1, r.bottom // T + 2):
                if (tx, ty) in self.grid:
                    res.append(pygame.Rect(tx * T, ty * T, T, T))
        for mv in self.movers:
            m = mv.rect
            if m.right > r.left - 2 and m.left < r.right + 2 and m.bottom > r.top - 2 and m.top < r.bottom + 2:
                res.append(m)
        return res

    def follow(self, x):
        self.camx = max(0.0, min(x - W * 0.38, self.world_w - W))

    def world_steps(self):
        """Cuantos pasos avanza el mundo este frame (camara lenta = menos)."""
        self.acc += self.game.time_scale()
        n = int(self.acc)
        self.acc -= n
        return n

    def throw_ball(self, cat):
        g = self.game
        if g.ball_ammo <= 0:
            return
        g.ball_ammo -= 1
        self.cat_balls.append(CatBall(cat.x + 13 + cat.face * 14, cat.y + 6, cat.face * 9 + cat.vx * 0.3, -3))
        play("throw")

    def update_balls(self, hit):
        for b in list(self.cat_balls):
            b.update(self)
            if not b.dead and hit(b.rect):
                b.dead = True
                self.parts.burst(b.x, b.y, (255, 220, 80), 10, 3)
            if b.dead:
                self.cat_balls.remove(b)

    def draw_balls(self, dst, cam):
        for b in self.cat_balls:
            dst.blit(A["catball"], (int(b.x) - 12 - cam, int(b.y) - 12))

    def draw_bg(self, dst):
        self.anim_t += 1
        draw_theme_bg(dst, self.theme, self.dark, self.camx, self.anim_t)

    def draw_tiles(self, dst):
        tl = self.tiles
        x0 = int(self.camx) // T
        qf = (self.anim_t // 20) % 2
        for tx in range(x0, x0 + W // T + 2):
            for ty in range(0, H // T + 1):
                k = self.grid.get((tx, ty))
                if not k:
                    continue
                if k == "g":
                    img = tl["top"] if (tx, ty - 1) not in self.grid else tl["dirt"]
                elif k == "c":
                    img = tl["crate"]
                elif k == "q":
                    img = A["qblock"][qf]
                elif k == "u":
                    img = A["used"]
                else:
                    img = tl["plank"]
                dst.blit(img, (tx * T - int(self.camx), ty * T))
        for mv in self.movers:
            dst.blit(A["mover"], (int(mv.x) - int(self.camx), int(mv.y)))

    def draw_hud(self, dst, right=""):
        g = self.game
        n = hearts_count(g.hp)
        panel(dst, (6, 6, n * 29 + 14, 40))
        draw_hearts(dst, 12, 12, g.hp, n)
        c = self.cat
        if c:
            frac = 1 - c.atk_cd / ATK_CD
            panel(dst, (6, 50, 104, 18), alpha=150, radius=8)
            pygame.draw.rect(dst, (50, 50, 80), (11, 55, 94, 8), border_radius=4)
            ready = c.atk_cd == 0
            pygame.draw.rect(dst, (120, 255, 140) if ready else (255, 190, 60),
                             (11, 55, int(94 * max(0.0, min(1.0, frac))), 8), border_radius=4)
            txt(dst, "ARAÑAR (X)", 13, (255, 255, 255) if ready else (200, 200, 210), 116, 51, False, True)
        draw_powers(dst, g, 8, 74)
        if right:
            wd = font(22).size(right)[0] + 24
            panel(dst, (W - wd - 8, 6, wd, 36))
            txt(dst, right, 22, (255, 255, 255), W - wd + 4, 10)
        fw = 62 if g.fish < 100 else 74
        panel(dst, (W - fw - 8, 46, fw, 26), alpha=150, radius=8)
        dst.blit(A["fish"], (W - fw - 2, 50))
        txt(dst, str(g.fish), 18, (255, 255, 255), W - fw + 26, 49)


# ----------------------------------------------------------------------------
#  NIVELES DE PLATAFORMAS (grandes, con terreno variable, generados por codigo)
# ----------------------------------------------------------------------------
def pick_item(rnd):
    return rnd.choices(ITEM_KINDS, weights=ITEM_WEIGHTS)[0]


def fmt_num(v):
    return ("%g" % round(v, 1))


def gen_level(n):
    rnd = random.Random(n * 7919 + 13)
    diff = n / 10.0
    heights, spikes, vacs, birds, movers, springs, fish = {}, [], [], [], [], [], []
    crates, planks, qb, hid = set(), set(), {}, {}
    gh = 15

    def ground(a, b, h):
        for tx in range(a, b):
            heights[tx] = h

    def fish_row(x0, count, row):
        for i in range(count):
            fish.append(((x0 + i) * T + 6, row * T + 8))

    ground(0, 14, gh)
    qb[(8, gh - 3)] = rnd.choice(["heal", "speed", "ball", "shield"])
    x = 14
    total = 140 + n * 24
    kinds = ["flat", "flat", "gap", "spikes", "pillar", "stairs", "plat_q", "hidden"]
    if n >= 2:
        kinds += ["vac", "spring", "hill"]
    if n >= 3:
        kinds += ["bird", "mover"]
    if n >= 5:
        kinds += ["gap", "spikes", "vac", "bird", "mover", "hill"]
    if n >= 8:
        kinds += ["spikes", "vac", "bird"]
    last = None
    while x < total:
        k = rnd.choice(kinds)
        if k == last and k in ("mover", "hidden", "plat_q", "spring"):
            continue
        last = k
        if k == "flat":
            l = rnd.randint(4, 8)
            ground(x, x + l, gh)
            if rnd.random() < 0.45:
                fish_row(x + 1, l - 2, gh - 2)
            x += l
        elif k == "gap":
            gl = rnd.randint(2, 2 + min(2, int(diff * 3.5)))
            fish_row(x - 1, gl + 2, gh - 4)
            x += gl
            ground(x, x + 5, gh)
            x += 5
        elif k == "spikes":
            cnt = rnd.randint(1, 1 + min(2, int(diff * 3)))
            ground(x, x + cnt + 7, gh)
            for i in range(cnt):
                spikes.append((x + 3 + i, gh - 1))
            fish_row(x + 2, cnt + 2, gh - 4)
            x += cnt + 7
        elif k == "pillar":
            ground(x, x + 7, gh)
            for j in range(rnd.randint(1, 2 + (1 if diff > 0.5 else 0))):
                crates.add((x + 3, gh - 1 - j))
            x += 7
        elif k == "stairs":
            up = gh > 12 and (gh >= 15 or rnd.random() < 0.5)
            step = rnd.choice([1, 1, 2, 3])
            ngh = max(11, gh - step) if up else min(16, gh + step)
            ground(x, x + 7, ngh)
            gh = ngh
            x += 7
        elif k == "hill":
            top = max(10, gh - rnd.randint(2, 3))
            ground(x, x + 9, top)
            fish_row(x + 1, 7, top - 2)
            x += 9
        elif k == "vac":
            ground(x, x + 11, gh)
            vacs.append(((x + 1) * T, (x + 10) * T - 32, gh * T))
            x += 11
        elif k == "bird":
            ground(x, x + 11, gh)
            birds.append(((x + 1) * T, (x + 10) * T, gh * T - 92))
            x += 11
        elif k == "spring":
            ground(x, x + 10, gh)
            springs.append((x + 3, gh - 1))
            if gh - 8 >= 2:
                for i in range(5):
                    planks.add((x + 4 + i, gh - 8))
                fish_row(x + 4, 5, gh - 10)
                if gh - 11 >= 1:
                    qb[(x + 6, gh - 11)] = pick_item(rnd)
            x += 10
        elif k == "plat_q":
            ground(x, x + 9, gh)
            planks.add((x + 3, gh - 3))
            qb[(x + 4, gh - 3)] = pick_item(rnd)
            planks.add((x + 5, gh - 3))
            fish_row(x + 2, 5, gh - 5)
            x += 9
        elif k == "hidden":
            ground(x, x + 9, gh)
            hid[(x + 4, gh - 3)] = pick_item(rnd)
            fish_row(x + 3, 3, gh - 5)
            x += 9
        else:  # mover: foso ancho que solo se cruza sobre la plataforma movil
            pw = rnd.randint(7, 9)
            movers.append((x * T, (x + pw - 3) * T, gh * T))
            fish_row(x + 1, pw - 2, gh - 3)
            x += pw
            ground(x, x + 6, gh)
            x += 6
    ground(x, x + 18, gh)
    goal = pygame.Rect((x + 12) * T, gh * T - 100, 40, 100)
    grid = {}
    for tx, h in heights.items():
        for ty in range(h, h + 9):
            grid[(tx, ty)] = "g"
    for t in crates:
        grid[t] = "c"
    for t in planks:
        grid[t] = "p"
    for t in qb:
        grid[t] = "q"
    return dict(grid=grid, spikes=spikes, vacs=vacs, birds=birds, movers=movers, springs=springs,
                fish=fish, qb=qb, hid=hid, goal=goal, world_w=(x + 18) * T, start_y=15 * T - Cat.h)


class LevelScene(PlatBase):
    def __init__(self, game, n):
        theme, dark = theme_of(n)
        super().__init__(game, theme, dark)
        self.n = n
        L = gen_level(n)
        self.grid = L["grid"]
        self.world_w = L["world_w"]
        self.goal = L["goal"]
        self.spikes = L["spikes"]
        self.spike_rects = [pygame.Rect(tx * T + 4, row * T + 10, T - 8, T - 10) for tx, row in self.spikes]
        self.vacs = [Vac(l, r, y) for l, r, y in L["vacs"]]
        self.birds = [Bird(x0, x1, cy) for x0, x1, cy in L["birds"]]
        self.movers = [MovingPlat(x0, x1, y) for x0, x1, y in L["movers"]]
        self.springs = [[pygame.Rect(tx * T, row * T + 12, T, 20), 0] for tx, row in L["springs"]]
        self.fish = [pygame.Rect(fx, fy, 18, 14) for fx, fy in L["fish"]]
        self.contents = dict(L["qb"])
        self.hidden = dict(L["hid"])
        self.items = []
        self.cat = Cat(3 * T, L["start_y"], game)
        self.safe = (self.cat.x, self.cat.y)
        self.safe_t = 0
        self.intro = 130
        self.done = 0

    # -- bloques e items
    def spawn_item(self, tile, kind):
        g = self.game
        if kind == "heal" and g.hp >= MAX_HEARTS_NORMAL:
            kind = "ball"
        self.items.append(Item(kind, tile[0] * T + 16, tile[1] * T - 6))
        self.parts.burst(tile[0] * T + 16, tile[1] * T, (255, 230, 120), 12, 3)
        play("block")

    def open_block(self, tile):
        kind = self.contents.pop(tile, "ball")
        self.grid[tile] = "u"
        self.spawn_item(tile, kind)

    def respawn(self, dmg):
        g = self.game
        if not g.has("shield"):
            g.damage(dmg)
            play("hit")
        if g.hp <= 0:
            g.go(GameOverScene(g))
            return
        c = self.cat
        c.x, c.y = self.safe
        c.vx = c.vy = 0
        c.inv = 120
        for v in self.vacs:
            if abs(v.x - c.x) < 120:
                v.alive = False
        for b in self.birds:
            if abs(b.x - c.x) < 120:
                b.alive = False

    def ball_hit(self, rect):
        for v in self.vacs:
            if v.alive and rect.colliderect(v.rect):
                v.alive = False
                self.parts.burst(v.x + 16, v.y + 12, (255, 120, 80), 12, 3)
                return True
        for b in self.birds:
            if b.alive and rect.colliderect(b.rect):
                b.alive = False
                self.parts.burst(b.x + 16, b.y + 12, (120, 160, 255), 12, 3)
                return True
        return False

    def update(self, events):
        g = self.game
        for e in events:
            if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                g.pause(self)
                return
        if self.intro > 0:
            self.intro -= 1
            return
        if self.done > 0:
            self.done -= 1
            if self.done == 0:
                g.level_done(self.n)
            return
        c = self.cat
        for mv in self.movers:
            mv.fdx = 0.0
        if self.world_steps():
            for v in self.vacs:
                if v.alive:
                    v.update()
            for b in self.birds:
                if b.alive:
                    b.update()
            for mv in self.movers:
                mv.update()
        if c.ride:
            c.x += c.ride.fdx
        c.update(self, events)
        self.parts.update()
        self.follow(c.x)
        r = c.rect
        if g.hit_event:
            self.parts.text(c.x + 13, c.y - 8, "-" + fmt_num(g.hit_event), (255, 90, 90))
            g.hit_event = 0
        # bloques ?
        if c.bump:
            tile, c.bump = c.bump, None
            if self.grid.get(tile) == "q":
                self.open_block(tile)
        # bloques secretos (invisibles) tipo Mario
        if c.vy < 0:
            for tile in list(self.hidden):
                tr = pygame.Rect(tile[0] * T, tile[1] * T, T, T)
                if r.colliderect(tr) and r.top > tr.top:
                    kind = self.hidden.pop(tile)
                    self.grid[tile] = "u"
                    c.y = float(tr.bottom)
                    c.vy = 0
                    self.spawn_item(tile, kind)
                    break
        # items
        for it in list(self.items):
            it.update(self)
            if it.dead:
                self.items.remove(it)
            elif it.age > 12 and r.colliderect(it.rect):
                self.items.remove(it)
                g.give(it.kind)
                self.parts.burst(it.x, it.y, ITEM_COL[it.kind], 16, 4)
                self.parts.text(it.x, it.y - 20, POWER_NAMES.get(it.kind, ITEM_TEXT.get(it.kind, "")), (255, 255, 160))
                play("power")
        # pescados
        for f in list(self.fish):
            if r.colliderect(f):
                self.fish.remove(f)
                g.add_fish()
                self.parts.burst(f.x + 9, f.y + 7, (120, 210, 255), 5, 2)
                play("pick")
        # resortes
        for sp in self.springs:
            if sp[1] > 0:
                sp[1] -= 1
            if c.vy > 0 and r.colliderect(sp[0]) and r.bottom <= sp[0].top + 14:
                c.vy = -19
                sp[1] = 12
                play("spring")
        # punto de reaparicion
        if c.on_ground and c.ride is None:
            self.safe_t += 1
            ty = r.bottom // T
            if (self.safe_t > 25 and (r.left // T, ty) in self.grid and (r.right // T, ty) in self.grid
                    and all(abs(sp.centerx - r.centerx) > 90 for sp in self.spike_rects)
                    and all(abs(v.x - c.x) > 90 for v in self.vacs if v.alive)
                    and all(abs(b.x - c.x) > 90 for b in self.birds if b.alive)):
                self.safe = (c.x, c.y)
        else:
            self.safe_t = 0
        if not g.has("shield"):
            for sp in self.spike_rects:
                if r.colliderect(sp):
                    self.respawn(1)
                    return
        if c.y > H + 60:
            self.respawn(1)
            return
        # enemigos
        ar = c.atk_rect()
        for foe, kind in [(v, "vac") for v in self.vacs] + [(b, "bird") for b in self.birds]:
            if not foe.alive:
                continue
            fr = foe.rect
            hit = False
            if r.colliderect(fr):
                if g.has("shield") or (c.vy > 0 and r.bottom - fr.top < 18):
                    hit = True
                    if not g.has("shield"):
                        c.vy = -9
                else:
                    c.hurt(g, 1, -1 if fr.centerx > r.centerx else 1)
            if ar and ar.colliderect(fr):
                hit = True
            if hit:
                foe.alive = False
                self.parts.burst(fr.centerx, fr.centery, (255, 230, 120), 12, 3)
                play("stomp")
        self.update_balls(self.ball_hit)
        if g.hp <= 0:
            g.go(GameOverScene(g))
            return
        if r.colliderect(self.goal):
            self.done = 90
            play("win")

    def draw(self, dst):
        self.draw_bg(dst)
        self.draw_tiles(dst)
        cam = int(self.camx)
        g = self.game
        if self.theme == 4:
            pygame.draw.rect(dst, (255, 110, 30), (0, H - 14, W, 14))
            pygame.draw.rect(dst, (255, 190, 70), (0, H - 14, W, 4))
        if g.has("sense"):
            pulse = 120 + int(100 * abs(math.sin(self.anim_t * 0.12)))
            for tile in self.hidden:
                pygame.draw.rect(dst, (pulse, 90, 255), (tile[0] * T - cam, tile[1] * T, T, T), 2, border_radius=4)
                txt(dst, "?", 20, (pulse, 140, 255), tile[0] * T - cam + 16, tile[1] * T + 4, True, False)
        for tx, row in self.spikes:
            dst.blit(A["spike"], (tx * T - cam, row * T))
        for sp in self.springs:
            img = A["spring"][1 if sp[1] > 0 else 0]
            dst.blit(img, (sp[0].x - cam - O, sp[0].bottom - img.get_height() + O))
        bob = int(math.sin(self.anim_t * 0.15) * 2)
        for f in self.fish:
            if -30 < f.x - cam < W + 30:
                dst.blit(A["fish"], (f.x - cam - O, f.y - O + bob))
        dst.blit(A["flag"], (self.goal.left - cam - O, self.goal.top - O))
        for it in self.items:
            dst.blit(A["items"][it.kind], (int(it.x) - 15 - cam, int(it.y) - 15 + int(math.sin(self.anim_t * 0.2) * 2)))
        for v in self.vacs:
            if v.alive:
                dst.blit(A["vac"][v.dir], (int(v.x) - cam - O, int(v.y) - O))
        for b in self.birds:
            if b.alive:
                dst.blit(A["bird"][(self.anim_t // 8) % 2][b.dir], (int(b.x) - cam - O, int(b.y) - O))
                if g.has("sense"):
                    pygame.draw.rect(dst, (255, 120, 255), (int(b.x) - cam, int(b.y), 36, 26), 1)
        self.draw_balls(dst, cam)
        self.cat.draw(dst, cam)
        self.parts.draw(dst, cam)
        self.draw_hud(dst, "NIVEL %d/10 · %s" % (self.n, THEMES[self.theme]["name"]))
        if self.intro > 0:
            ov = surf(W, H)
            ov.fill((0, 0, 0, min(150, self.intro * 3)))
            dst.blit(ov, (0, 0))
            boss = {3: "Al final te espera el PERRO 1", 6: "Al final te espera el PERRO 2",
                    10: "Al final te espera EL HUMANO"}.get(self.n)
            banner(dst, 200, "NIVEL %d · %s" % (self.n, THEMES[self.theme]["name"]),
                   boss or "Golpea los bloques ? desde abajo. ¡Hay secretos!", (255, 220, 80))
        if self.done > 0:
            banner(dst, 220, "¡NIVEL COMPLETADO!", "+1 corazón", (120, 255, 150), 110)


# ----------------------------------------------------------------------------
#  JEFE PERRO
# ----------------------------------------------------------------------------
class Dog:
    def __init__(self, idx, x):
        self.idx = idx
        self.w, self.h = 96, 66
        self.x, self.y = float(x), float(GY - self.h)
        self.vx = self.vy = 0.0
        self.face = -1
        self.maxhp = [5, 7][idx]
        self.hp = self.maxhp
        self.sp = [1.0, 1.3][idx]
        self.st = "idle"
        self.t = 90
        self.inv = 0
        self.anim = 0.0
        self.dead_t = 0

    @property
    def rect(self):
        return pygame.Rect(int(self.x), int(self.y), self.w, self.h)

    def hit(self):
        self.hp -= 1
        self.inv = 30
        if self.hp <= 0:
            self.st = "dead"
            self.vy = -9
            self.vx = 0

    def rest(self):
        self.vx = 0
        self.st, self.t = "idle", DOG_REST      # 1,2 s entre ataques

    def update(self, cat, world_w):
        if self.st == "dead":
            self.dead_t += 1
            self.vy += 0.5
            self.y += self.vy
            return
        self.anim += abs(self.vx) * 0.04 + 0.02
        self.vy += 0.7
        self.x += self.vx
        self.y += self.vy
        landed = wall = False
        if self.y >= GY - self.h:
            self.y, self.vy, landed = GY - self.h, 0.0, True
        if self.x < 0:
            self.x, wall = 0.0, True
        if self.x > world_w - self.w:
            self.x, wall = float(world_w - self.w), True
        st = self.st
        if st == "idle":
            self.vx = 0
            self.t -= 1
            self.face = 1 if cat.x + 13 > self.x + self.w / 2 else -1
            if self.t <= 0:
                if random.random() < 0.6:
                    self.st, self.t = "cw", int(26 / self.sp)
                else:
                    self.st, self.t = "lw", int(22 / self.sp)
        elif st == "cw":
            self.vx = 0
            self.t -= 1
            if self.t <= 0:
                self.st, self.t = "charge", 100
                self.vx = self.face * 6.0 * self.sp
        elif st == "charge":
            self.t -= 1
            if wall or self.t <= 0:
                self.rest()
        elif st == "lw":
            self.vx = 0
            self.t -= 1
            if self.t <= 0:
                self.st, self.t = "leap", 0
                self.vy = -15
                self.vx = max(-9, min(9, (cat.x - self.x) / 43))
                self.face = 1 if self.vx >= 0 else -1
        elif st == "leap":
            self.t += 1
            if landed and self.t > 5:
                self.rest()

    def draw(self, dst, camx):
        if self.inv > 0 and (self.inv // 3) % 2 == 0 and self.st != "dead":
            return
        img = A["dog_side"][self.idx][int(self.anim) % 2][self.face]
        x, y = int(self.x) - int(camx) - 2 - O, int(self.y) - 4 - O
        if self.st == "dead":
            img = pygame.transform.rotate(img, self.dead_t * 9)
        elif self.st in ("cw", "lw"):
            x += random.randint(-2, 2)
        dst.blit(img, (x, y))


class BossDogScene(PlatBase):
    def __init__(self, game, idx):
        super().__init__(game, theme=[0, 4][idx], dark=[True, False][idx])
        self.idx = idx
        self.world_w = 40 * T
        for tx in range(40):
            for ty in range(GROUND_ROW, GROUND_ROW + 4):
                self.grid[(tx, ty)] = "g"
        for tx in list(range(7, 12)) + list(range(28, 33)):
            self.grid[(tx, 11)] = "p"
        self.cat = Cat(120, GY - Cat.h, game)
        self.dog = Dog(idx, 30 * T)
        self.intro = 130
        self.dmg0 = game.dmg_total
        self.finished = False
        play("boss")

    def ball_hit(self, rect):
        d = self.dog
        if d.st != "dead" and d.inv == 0 and rect.colliderect(d.rect):
            d.hit()
            self.parts.burst(d.x + 48, d.y + 20, (255, 220, 80), 12, 3)
            play("stomp")
            return True
        return False

    def update(self, events):
        g = self.game
        for e in events:
            if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                g.pause(self)
                return
        if self.intro > 0:
            self.intro -= 1
            return
        c, d = self.cat, self.dog
        c.update(self, events)
        self.parts.update()
        self.follow(c.x)
        if g.hit_event:
            self.parts.text(c.x + 13, c.y - 8, "-" + fmt_num(g.hit_event), (255, 90, 90))
            g.hit_event = 0
        if d.inv > 0:
            d.inv -= 1
        if self.world_steps():
            d.update(c, self.world_w)
        if d.st == "dead":
            if d.dead_t > 100 and not self.finished:
                self.finished = True
                g.dog_defeated(self.idx, g.dmg_total == self.dmg0)
            return
        self.update_balls(self.ball_hit)
        hr, cr = d.rect, c.rect
        ar = c.atk_rect()
        hit = False
        if d.inv == 0:
            if cr.colliderect(hr) and c.vy > 0 and cr.bottom - hr.top < 28:
                d.hit()
                c.vy = -11
                c.inv = max(c.inv, STOMP_INV)      # 3 s sin daño tras saltarle encima
                hit = True
                play("stomp")
                self.parts.burst(cr.centerx, hr.top, (255, 230, 120), 12, 3)
            elif ar and ar.colliderect(hr):
                d.hit()
                hit = True
                play("stomp")
        if not hit and cr.colliderect(hr) and d.st != "dead":
            if g.has("shield") and d.inv == 0:
                d.hit()
                play("stomp")
            else:
                c.hurt(g, 1, -1 if hr.centerx > cr.centerx else 1)
        if c.y > H + 60:
            c.x, c.y, c.vy = 120.0, GY - Cat.h, 0
        if g.hp <= 0:
            g.go(GameOverScene(g))

    def draw(self, dst):
        self.draw_bg(dst)
        self.draw_tiles(dst)
        cam = int(self.camx)
        self.dog.draw(dst, cam)
        self.draw_balls(dst, cam)
        self.cat.draw(dst, cam)
        self.parts.draw(dst, cam)
        self.draw_hud(dst, "")
        d = self.dog
        bw = 300
        x = (W - bw) // 2
        panel(dst, (x - 10, 50, bw + 20, 50), alpha=190)
        pygame.draw.rect(dst, (70, 20, 30), (x, 78, bw, 14), border_radius=6)
        pygame.draw.rect(dst, (235, 60, 70), (x, 78, int(bw * max(0, d.hp) / d.maxhp), 14), border_radius=6)
        txt(dst, "JEFE: PERRO %d" % (self.idx + 1), 18, (255, 255, 255), W // 2, 54, True)
        if self.cat.inv > 90 and self.cat.mode == "free" and self.intro <= 0:
            txt(dst, "¡INVULNERABLE!", 18, (130, 225, 255), W // 2, 104, True)
        if self.intro > 0:
            banner(dst, 190, "¡JEFE: PERRO %d!" % (self.idx + 1),
                   "Salta sobre su cabeza (3 s sin daño) o arañalo con X")


# ----------------------------------------------------------------------------
#  JEFE FINAL: EL HUMANO
# ----------------------------------------------------------------------------
class BossHumanScene(PlatBase):
    AW = 2400      # arena normal
    CW = 3600      # mapa grande durante la persecucion

    def __init__(self, game):
        super().__init__(game, theme=4, dark=True)
        self.world_w = self.AW
        for tx in range(self.AW // T):
            for ty in range(GROUND_ROW, GROUND_ROW + 4):
                self.grid[(tx, ty)] = "g"
        for a, b in ((8, 13), (34, 40), (62, 68)):
            for tx in range(a, b):
                self.grid[(tx, 11)] = "p"
        self.base = dict(self.grid)
        self.cat = Cat(300, GY - Cat.h, game)
        self.hw, self.hh = 56, 112
        self.hx, self.hy = 1700.0, float(GY - self.hh)
        self.face = -1
        self.hp = 25
        self.maxhp = 25
        self.st = "walk"
        self.t = 0
        self.cool = 150
        self.queue = []
        self.balls = []
        self.footballs = []
        self.inv = 0
        self.intro = 170
        self.dead_t = 0
        self.last_phase = 0
        self.banner = ""
        self.banner_t = 0
        self.grab_mode = "punch"
        self.balls_left = 0
        self.balls_tick = 0
        self.chase_active = False
        self.chase_t = 0
        self.chase_added = []
        self.chase_removed = {}
        self.anim = 0.0
        self.shake = 0
        self.dmg0 = game.dmg_total
        play("boss")

    # -- utilidades
    def phase(self):
        return 0 if self.hp >= 20 else 1 if self.hp >= 13 else 2 if self.hp >= 6 else 3

    def sp(self):
        return [1.0, 1.15, 1.45, 1.8][self.phase()]

    @property
    def hrect(self):
        return pygame.Rect(int(self.hx), int(self.hy), self.hw, self.hh)

    def face_cat(self):
        self.face = 1 if self.cat.x + 13 > self.hx + self.hw / 2 else -1

    def say(self, s, t=100):
        self.banner, self.banner_t = s, t

    def ball_hit(self, rect):
        if self.st != "dead" and self.inv == 0 and rect.colliderect(self.hrect):
            self.hp -= 2 if self.st == "tired" else 1
            self.inv = 16
            self.shake = 8
            play("stomp")
            return True
        return False

    # -- ataques
    def start_next(self):
        ph = self.phase()
        if not self.queue:
            names = ["grab", "balls", "kick", "chase"]
            if ph == 3:
                q = names[:]
                random.shuffle(q)
            else:
                q = random.sample(names, [1, 2, 2, 4][ph])
            self.queue = q
        a = self.queue.pop(0)
        self.face_cat()
        if a == "grab":
            self.st, self.t = "grab_wind", int(34 / self.sp())
        elif a == "balls":
            self.st, self.t = "balls_wind", int(30 / self.sp())
        elif a == "kick":
            self.st, self.t = "kick_wind", int(38 / self.sp())
        else:
            self.begin_chase()

    def end_attack(self, frames):
        self.st, self.t = "recover", frames

    # -- persecucion: el mapa se hace mas grande
    def begin_chase(self):
        self.st, self.t = "chase_wind", 70
        self.chase_active = True
        self.chase_t = 0
        self.chase_added, self.chase_removed = [], {}
        c = self.cat
        self.world_w = self.CW
        for tx in range(self.AW // T, self.CW // T):
            for ty in range(GROUND_ROW, GROUND_ROW + 4):
                self.grid[(tx, ty)] = "g"
                self.chase_added.append((tx, ty))
        c.mode = "free"
        c.x, c.y, c.vx, c.vy = 420.0, GY - Cat.h - 1.0, 0.0, 0.0
        self.hx, self.hy = 0.0, float(GY - self.hh)
        self.face = 1
        self.balls, self.footballs = [], []
        tiles = self.CW // T
        tx = 20
        while tx < tiles - 14:
            k = random.choice(["pit", "pit", "crate", "crate2", "plank", "none"])
            if k == "pit":
                wd = random.randint(2, 3)
                for dx in range(wd):
                    for ty in range(GROUND_ROW, GROUND_ROW + 4):
                        key = (tx + dx, ty)
                        if key in self.grid:
                            self.chase_removed[key] = self.grid.pop(key)
                tx += wd + 5
            elif k == "crate":
                self.grid[(tx, GROUND_ROW - 1)] = "c"
                self.chase_added.append((tx, GROUND_ROW - 1))
                tx += 5
            elif k == "crate2":
                for j in (1, 2):
                    self.grid[(tx, GROUND_ROW - j)] = "c"
                    self.chase_added.append((tx, GROUND_ROW - j))
                tx += 5
            elif k == "plank":
                for dx in range(3):
                    key = (tx + dx, 12)
                    if key not in self.grid:
                        self.grid[key] = "p"
                        self.chase_added.append(key)
                tx += 6
            else:
                tx += 4
        self.shake = 25
        self.say("¡PERSECUCIÓN! ¡Corre hasta la meta!", 110)
        self.game.fade = 255
        play("boss")

    def restore_world(self):
        if not self.chase_active:
            return
        self.chase_active = False
        for k in self.chase_added:
            if k not in self.base:
                self.grid.pop(k, None)
        for k, v in self.chase_removed.items():
            if k in self.base:
                self.grid[k] = v
        self.chase_added, self.chase_removed = [], {}
        self.world_w = self.AW
        c = self.cat
        c.x, c.y, c.vx, c.vy = 1000.0, GY - Cat.h - 1.0, 0.0, 0.0
        c.mode = "free"
        self.hx, self.hy = 1500.0, float(GY - self.hh)
        self.balls, self.footballs = [], []
        self.game.fade = 255

    def finish_chase(self, tired):
        self.restore_world()
        if tired:
            self.st, self.t = "tired", TIRED_T
            self.face_cat()
            self.say("¡EL HUMANO SE CANSÓ! Daño x2", 150)
            play("win")
        else:
            self.end_attack(70)

    def pit_respawn(self):
        g = self.game
        c = self.cat
        if not g.has("shield"):
            g.damage(1)
            play("hit")
        if g.hp <= 0:
            g.go(GameOverScene(g))
            return
        tx0 = int(c.x) // T
        for off in range(0, 200):
            for tx in (tx0 - off, tx0 + off):
                if (tx, GROUND_ROW) in self.grid and (tx + 1, GROUND_ROW) in self.grid \
                        and (tx, GROUND_ROW - 1) not in self.grid:
                    c.x, c.y, c.vx, c.vy = tx * T + 3.0, GY - Cat.h - 1.0, 0, 0
                    c.inv = 110
                    return

    # -- bucle
    def update(self, events):
        g = self.game
        for e in events:
            if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                g.pause(self)
                return
        if self.banner_t > 0:
            self.banner_t -= 1
        if self.shake > 0:
            self.shake -= 1
        self.anim += 0.15
        c = self.cat
        if self.intro > 0:
            self.intro -= 1
            self.follow(c.x)
            return
        if self.st == "dead":
            self.dead_t += 1
            self.hy = min(self.hy + 1.5, GY - self.hh + 40)
            if self.dead_t > 150:
                g.go(WinScene(g, g.dmg_total == self.dmg0))
            return
        if self.inv > 0:
            self.inv -= 1
        c.update(self, events)
        self.parts.update()
        self.follow(c.x)
        if g.hit_event:
            self.parts.text(c.x + 13, c.y - 8, "-" + fmt_num(g.hit_event), (255, 90, 90))
            g.hit_event = 0
        if c.thrown_end:
            c.thrown_end = False
            c.inv = 0
            c.hurt(g, 1, 0)
        if self.world_steps():
            self.update_human()
            self.update_projectiles()
        self.update_balls(self.ball_hit)
        self.damage_human()
        if c.y > H + 60:
            self.pit_respawn()
        if self.hp <= 0 and self.st != "dead":
            self.restore_world()
            self.st = "dead"
            self.balls, self.footballs = [], []
            play("win")
            return
        if g.hp <= 0:
            g.go(GameOverScene(g))
            return
        ph = self.phase()
        if ph != self.last_phase:
            self.last_phase = ph
            self.say("¡FASE %d!" % (ph + 1), 110)
            play("boss")

    def update_human(self):
        c = self.cat
        sp = self.sp()
        st = self.st
        self.t -= 1
        if st == "walk":
            self.face_cat()
            dx = (c.x + 13) - (self.hx + self.hw / 2)
            if abs(dx) > 170:
                self.hx += (1.4 if dx > 0 else -1.4) * sp
            self.hx = max(0, min(self.hx, self.world_w - self.hw))
            self.cool -= 1
            if self.cool <= 0:
                self.start_next()
        elif st == "grab_wind":
            self.face_cat()
            if self.t <= 0:
                self.st, self.t = "grab_lunge", 22
        elif st == "grab_lunge":
            self.hx += self.face * 10 * sp
            self.hx = max(0, min(self.hx, self.world_w - self.hw))
            reach = pygame.Rect(int(self.hx + (self.hw if self.face > 0 else -70)), int(self.hy + self.hh - 60), 70, 60)
            if c.mode == "free" and c.inv == 0 and not self.game.has("shield") and c.rect.colliderect(reach):
                c.mode = "grabbed"
                self.st, self.t = "grab_hold", 45
                self.grab_mode = random.choice(["punch", "throw"])
                play("boss")
            elif self.t <= 0:
                self.end_attack(45)
        elif st == "grab_hold":
            c.x = self.hx + (self.hw + 4 if self.face > 0 else -30)
            c.y = self.hy + 40
            c.vx = c.vy = 0
            if self.t <= 0:
                c.inv = 0
                if self.grab_mode == "punch":
                    c.mode = "free"
                    c.hurt(self.game, 1, self.face)
                else:
                    c.mode = "thrown"
                    c.thrown_t = 0
                    c.vx, c.vy = self.face * 13, -11
                    c.inv = 0
                    play("hit")
                self.end_attack(40)
        elif st == "balls_wind":
            self.face_cat()
            if self.t <= 0:
                self.st = "balls"
                self.balls_left = [3, 4, 5, 6][self.phase()]
                self.balls_tick = 0
        elif st == "balls":
            self.balls_tick -= 1
            if self.balls_tick <= 0 and self.balls_left > 0:
                self.face_cat()
                bx, by = self.hx + self.hw / 2 + self.face * 24, self.hy + 20
                ang = math.atan2((c.y + 13) - by, (c.x + 13) - bx) + random.uniform(-0.12, 0.12)
                v = 7.0 * sp
                self.balls.append({"x": bx, "y": by, "vx": math.cos(ang) * v, "vy": math.sin(ang) * v - 1.5,
                                   "life": 300, "bn": 0, "friend": False})
                self.balls_left -= 1
                self.balls_tick = int(18 / sp)
                play("scratch")
            if self.balls_left <= 0 and self.balls_tick <= 0:
                self.end_attack(20)
        elif st == "kick_wind":
            self.face_cat()
            if self.t <= 0:
                self.st, self.t = "kick", 14
                fx = self.hx + (self.hw + 6 if self.face > 0 else -32)
                self.footballs.append({"x": fx, "y": GY - 26.0, "vx": self.face * 11 * sp, "friend": False})
                play("boss")
        elif st == "kick":
            if self.t <= 0:
                self.end_attack(26)
        elif st == "chase_wind":
            self.face = 1
            if self.t <= 0:
                self.st = "chase"
        elif st == "chase":
            self.chase_t += 1
            self.face_cat()
            spd = [3.6, 4.0, 4.4, 4.8][self.phase()]
            self.hx += self.face * spd
            self.hx = max(0, min(self.hx, self.world_w - self.hw))
            if c.mode == "free" and c.rect.colliderect(self.hrect):
                if c.hurt(self.game, 1, self.face):
                    self.finish_chase(False)
            elif c.x >= self.CW - 220 or self.chase_t > 1500:
                self.finish_chase(True)       # llegaste a la meta: el humano se cansa
        elif st == "tired":
            if self.t <= 0:
                self.st = "walk"
                self.cool = 90
        elif st == "recover":
            if self.t <= 0:
                self.st = "walk"
                self.cool = 25 if self.queue else HUMAN_REST   # 5 s de descanso tras cada ataque

    def update_projectiles(self):
        c = self.cat
        cr = c.rect
        ar = c.atk_rect()
        hr = self.hrect
        for b in list(self.balls):
            b["vy"] += 0.12
            b["x"] += b["vx"]
            b["y"] += b["vy"]
            b["life"] -= 1
            if b["y"] > GY - 11:
                b["y"] = GY - 11
                b["vy"] = -abs(b["vy"]) * 0.6
                b["bn"] += 1
            br = pygame.Rect(int(b["x"]) - 10, int(b["y"]) - 10, 20, 20)
            dead = b["life"] <= 0 or b["bn"] > 3 or b["x"] < -50 or b["x"] > self.world_w + 50
            if not dead and ar and not b["friend"] and ar.colliderect(br):
                b["vx"] = -b["vx"] * 1.3
                b["vy"] = -4
                b["friend"] = True
                play("stomp")
            if not dead and b["friend"] and br.colliderect(hr) and self.inv == 0 and self.st != "dead":
                self.hp -= 1
                self.inv = 16
                self.shake = 8
                play("stomp")
                dead = True
            elif not dead and not b["friend"] and br.colliderect(cr):
                if c.hurt(self.game, 0.5, 1 if b["vx"] > 0 else -1):
                    dead = True
            if dead:
                self.balls.remove(b)
        for f in list(self.footballs):
            f["x"] += f["vx"]
            fr = pygame.Rect(int(f["x"]) - 13, int(f["y"]) - 13, 26, 26)
            dead = f["x"] < -40 or f["x"] > self.world_w + 40
            if not dead and ar and not f["friend"] and ar.colliderect(fr):
                f["vx"] = -f["vx"] * 1.2
                f["friend"] = True
                play("stomp")
            if not dead and f["friend"] and fr.colliderect(hr) and self.inv == 0 and self.st != "dead":
                self.hp -= 1
                self.inv = 16
                self.shake = 8
                play("stomp")
                dead = True
            elif not dead and not f["friend"] and fr.colliderect(cr):
                if c.hurt(self.game, 0.5, 1 if f["vx"] > 0 else -1):
                    dead = True
            if dead:
                self.footballs.remove(f)

    def damage_human(self):
        if self.inv > 0 or self.st == "dead":
            return
        c = self.cat
        hr, cr = self.hrect, c.rect
        ar = c.atk_rect()
        dmg = 2 if self.st == "tired" else 1
        if ar and ar.colliderect(hr):
            self.hp -= dmg
        elif cr.colliderect(hr) and c.vy > 2 and cr.bottom - hr.top < 26:
            self.hp -= dmg
            c.vy = -11
        else:
            return
        self.inv = 16
        self.shake = 8
        play("stomp")
        self.parts.burst(hr.centerx, hr.top + 20, (255, 230, 120), 10, 3)

    # -- dibujo
    def pose(self):
        st = self.st
        if st == "dead" or (self.inv > 8):
            return "hurt"
        if st == "tired":
            return "tired"
        if st in ("grab_lunge", "grab_hold"):
            return "reach"
        if st in ("balls_wind", "balls"):
            return "throw"
        if st == "kick_wind":
            return "kickback"
        if st == "kick":
            return "kick"
        if st in ("chase", "chase_wind"):
            return "run1" if int(self.anim) % 2 == 0 else "run2"
        if st == "walk" and self.cool > 0:
            return "run1" if int(self.anim) % 2 == 0 and abs(self.cat.x - self.hx) > 175 else "idle"
        return "idle"

    def draw(self, dst):
        self.draw_bg(dst)
        sx = random.randint(-3, 3) if self.shake > 0 else 0
        self.draw_tiles(dst)
        cam = int(self.camx)
        if self.chase_active:
            fx = self.CW - 150 - cam
            dst.blit(A["flag"], (fx - O, GY - 100 - O))
            txt(dst, "META", 20, (255, 240, 120), fx + 20, GY - 128, True)
        img = A["human_side"][self.pose()][self.face]
        hx = int(self.hx) - cam - 20 + sx
        if not (self.inv > 0 and (self.inv // 3) % 2 == 0):
            dst.blit(img, ((hx if self.face > 0 else hx - 20) - O, int(self.hy) - 16 - O))
        for b in self.balls:
            dst.blit(A["ball"], (int(b["x"]) - 12 - cam, int(b["y"]) - 12))
        for f in self.footballs:
            dst.blit(A["football"], (int(f["x"]) - 14 - cam, int(f["y"]) - 14))
        self.draw_balls(dst, cam)
        self.cat.draw(dst, cam)
        self.parts.draw(dst, cam)
        self.draw_hud(dst, "")
        # barra de vida del humano: 25 corazones
        panel(dst, (W // 2 - 214, 50, 428, 62), alpha=190)
        x0 = (W - 25 * 16) // 2
        for i in range(25):
            dst.blit(A["hearts_full" if i < self.hp else "hearts_empty"], (x0 + i * 16, 56))
        txt(dst, "EL HUMANO  -  FASE %d" % (self.phase() + 1), 18, (255, 255, 255), W // 2, 78, True)
        if self.st == "walk" and not self.queue:
            txt(dst, "Próximo ataque en %.1f s" % (max(0, self.cool) / 60.0), 15, (255, 220, 120), W // 2, 116, True)
        elif self.st == "tired":
            txt(dst, "¡CANSADO! Tu daño vale x2  (%.1f s)" % (max(0, self.t) / 60.0), 17, (130, 255, 160), W // 2, 116, True)
        if self.banner_t > 0:
            banner(dst, 210, self.banner, None, (255, 90, 90), 90)
        if self.intro > 0:
            banner(dst, 190, "¡EL HUMANO QUIERE ATRAPARTE!",
                   "Arañalo (X) o salta sobre su cabeza. Tras cada ataque descansa 5 s.")


# ----------------------------------------------------------------------------
#  LABERINTO PROCEDURAL (crece con cada nivel)
# ----------------------------------------------------------------------------
def maze_size(stage):
    return 25 + 8 * stage, 19 + 6 * stage       # siempre impares


def gen_maze(cols, rows, seed, stage):
    rnd = random.Random(seed)
    g = [[1] * cols for _ in range(rows)]
    g[1][1] = 0
    stack = [(1, 1)]
    while stack:
        x, y = stack[-1]
        nb = []
        for dx, dy in DIRS:
            nx, ny = x + dx * 2, y + dy * 2
            if 0 < nx < cols - 1 and 0 < ny < rows - 1 and g[ny][nx] == 1:
                nb.append((nx, ny, dx, dy))
        if nb:
            nx, ny, dx, dy = rnd.choice(nb)
            g[y + dy][x + dx] = 0
            g[ny][nx] = 0
            stack.append((nx, ny))
        else:
            stack.pop()
    cand = []
    for y in range(1, rows - 1):
        for x in range(1, cols - 1):
            if g[y][x] == 1:
                if x % 2 == 1 and y % 2 == 0 and g[y - 1][x] == 0 and g[y + 1][x] == 0:
                    cand.append((x, y))
                elif x % 2 == 0 and y % 2 == 1 and g[y][x - 1] == 0 and g[y][x + 1] == 0:
                    cand.append((x, y))
    rnd.shuffle(cand)
    for x, y in cand[:int(len(cand) * 0.16)]:        # bucles tipo Pac-Man
        g[y][x] = 0
    for _ in range(2 + stage * 2):                    # plazas abiertas
        cx = rnd.randrange(3, cols - 3, 2)
        cy = rnd.randrange(3, rows - 3, 2)
        for yy in range(cy - 1, cy + 2):
            for xx in range(cx - 1, cx + 2):
                g[yy][xx] = 0
    return g


def bfs(walls, start, limit=None):
    dist = {start: 0}
    q = deque([start])
    while q:
        cur = q.popleft()
        d = dist[cur]
        if limit is not None and d >= limit:
            continue
        for dx, dy in DIRS:
            n = (cur[0] + dx, cur[1] + dy)
            if n not in walls and n not in dist:
                dist[n] = d + 1
                q.append(n)
    return dist


ORB_KINDS = ["speed", "shield", "sense", "slow", "heal", "life", "ball"]
ORB_WEIGHTS = [14, 12, 12, 10, 12, 5, 16]


class Mover:
    def __init__(self, c, r, speed):
        self.c, self.r = c, r
        self.dx = self.dy = 0
        self.p = 0.0
        self.ldx = self.ldy = 0
        self.speed = speed
        self.fd = (1, 0)
        self.stun = 0

    @property
    def px(self):
        return (self.c + self.dx * self.p) * T

    @property
    def py(self):
        return (self.r + self.dy * self.p) * T

    def eff_speed(self, scene):
        return self.speed

    def advance(self, scene):
        move = self.eff_speed(scene)
        while move > 0:
            if self.dx == 0 and self.dy == 0:
                self.dx, self.dy = self.choose(scene)
                self.p = 0.0
                if self.dx == 0 and self.dy == 0:
                    return
                self.ldx, self.ldy = self.dx, self.dy
                self.fd = (self.dx, self.dy)
            need = 1 - self.p
            if move >= need:
                self.c += self.dx
                self.r += self.dy
                move -= need
                self.dx = self.dy = 0
                self.p = 0.0
            else:
                self.p += move
                move = 0


class MazeCat(Mover):
    def __init__(self, c, r):
        super().__init__(c, r, 0.085)
        self.want = (0, 0)

    def eff_speed(self, scene):
        return self.speed * (1.5 if scene.game.has("speed") else 1.0)

    def choose(self, scene):
        for d in (self.want, (self.ldx, self.ldy)):
            if d != (0, 0) and (self.c + d[0], self.r + d[1]) not in scene.walls:
                return d
        return (0, 0)

    def reverse_if_needed(self):
        if (self.dx or self.dy) and self.want == (-self.dx, -self.dy):
            self.c += self.dx
            self.r += self.dy
            self.p = 1 - self.p
            self.dx, self.dy = -self.dx, -self.dy
            self.ldx, self.ldy = self.dx, self.dy
            self.fd = (self.dx, self.dy)


class Chaser(Mover):
    """Perro / humano del laberinto: mas listos con cada nivel y con energia limitada al correr."""

    def __init__(self, c, r, kind, speed, aggr, detect, run_p):
        super().__init__(c, r, speed)
        self.kind, self.aggr, self.detect, self.run_p = kind, aggr, detect, run_p
        self.mode = "walk"
        self.mt = 0
        self.cd = random.randint(120, 300)
        self.alert = 0

    def eff_speed(self, scene):
        if self.stun > 0:
            return 0.0
        m = {"walk": 1.0, "run": RUN_MULT, "tired": TIRED_MULT}[self.mode]
        return self.speed * m * scene.scale

    def think(self, scene):
        if self.stun > 0:
            self.stun -= 1
            return
        d = scene.dist.get((self.c, self.r), 999)
        if d <= self.detect:
            self.alert = 240
        elif self.alert > 0:
            self.alert -= 1
        if self.mode == "walk":
            if self.cd > 0:
                self.cd -= 1
            elif d <= self.detect + 2 and random.random() < self.run_p:
                self.mode = "run"
                self.mt = random.randint(180, RUN_MAX)      # nunca mas de 5 s corriendo
                play("run")
        elif self.mode == "run":
            self.mt -= 1
            if self.mt <= 0:
                self.mode = "tired"
                self.mt = random.randint(TIRED_MIN, TIRED_MAX)   # 6-7 s caminando a la mitad
        else:
            self.mt -= 1
            if self.mt <= 0:
                self.mode = "walk"
                self.cd = random.randint(120, 240)

    def choose(self, scene):
        opts = [d for d in DIRS if (self.c + d[0], self.r + d[1]) not in scene.walls]
        if not opts:
            return (0, 0)
        non_rev = [d for d in opts if d != (-self.ldx, -self.ldy)]
        if non_rev:
            opts = non_rev
        if self.alert > 0:
            dm = scene.dist
            if self.kind == "dog1" and scene.dist2 and scene.dist.get((self.c, self.r), 999) > 6:
                dm = scene.dist2            # embosca: apunta delante del gato
            if random.random() < self.aggr:
                return min(opts, key=lambda d: dm.get((self.c + d[0], self.r + d[1]), 9999))
            return random.choice(opts)
        straight = (self.ldx, self.ldy)
        if straight in opts and random.random() < 0.8:
            return straight
        return random.choice(opts)


class MazeMouse(Mover):
    """El raton HUYE del gato por el laberinto."""

    def __init__(self, c, r, speed=0.058):
        super().__init__(c, r, speed)
        self.fd = (-1, 0)

    def eff_speed(self, scene):
        return 0.0 if self.stun > 0 else self.speed * scene.scale

    def choose(self, scene):
        opts = [d for d in DIRS if (self.c + d[0], self.r + d[1]) not in scene.walls]
        if not opts:
            return (0, 0)
        non_rev = [d for d in opts if d != (-self.ldx, -self.ldy)]
        if non_rev:
            opts = non_rev
        here = scene.dist.get((self.c, self.r), 99)
        if here > 11 or random.random() < 0.07:
            return random.choice(opts)
        best = max(scene.dist.get((self.c + d[0], self.r + d[1]), 0) for d in opts)
        top = [d for d in opts if scene.dist.get((self.c + d[0], self.r + d[1]), 0) == best]
        return random.choice(top)


class MazeBall:
    def __init__(self, x, y, d):
        self.x, self.y, self.d = x, y, d
        self.life = 70
        self.dead = False


class MazeScene:
    ticks_powers = True

    def __init__(self, game, msg=None):
        self.game = game
        stage = min(9, game.collected)
        self.stage = stage
        self.cols, self.rows = maze_size(stage)
        seed = game.maze_seed(stage)
        grid = gen_maze(self.cols, self.rows, seed, stage)
        self.walls = {(x, y) for y in range(self.rows) for x in range(self.cols) if grid[y][x]}
        self.tiles = maze_tiles(stage)
        self.cstart = (1, self.rows - 2)
        full = bfs(self.walls, self.cstart)
        maxd = max(full.values())
        rnd = random.Random(seed * 3 + 1)

        def pick(lo, hi, avoid):
            cands = [p for p, d in full.items() if lo * maxd <= d <= hi * maxd
                     and all(abs(p[0] - a[0]) + abs(p[1] - a[1]) >= 8 for a in avoid)]
            if not cands:
                cands = [p for p, d in full.items() if d > 6]
            return rnd.choice(sorted(cands))

        self.hstart = pick(0.5, 0.8, [self.cstart])
        self.dstart = [pick(0.3, 0.55, [self.cstart, self.hstart])]
        self.dstart.append(pick(0.3, 0.6, [self.cstart, self.hstart, self.dstart[0]]))
        mpos = pick(0.6, 1.0, [self.cstart, self.hstart] + self.dstart)
        self.mstart = mpos
        self.mouse = MazeMouse(mpos[0], mpos[1], 0.058 + 0.003 * stage)
        self.orbs = []
        for _ in range(2 + stage // 2 + 1):
            p = pick(0.08, 0.95, [self.cstart])
            self.orbs.append({"c": p[0], "r": p[1], "kind": rnd.choices(ORB_KINDS, weights=ORB_WEIGHTS)[0]})
        self.cat = MazeCat(*self.cstart)
        self.spawn_enemies()
        if isinstance(msg, str):
            msg = [msg]
        self.msg, self.msg_t = msg, 260 if msg else 0
        self.dist, self.dist2 = {}, {}
        self.last_key = None
        self.t = 0
        self.scale = 1.0
        self.grace = 130
        self.parts = Parts()
        self.balls = []
        self.camx = self.camy = 0.0
        self.bfs_limit = 8 + 2 * stage + 8
        # minimapa (solo lo explorado, o todo con sentido gatuno)
        self.mini_full = pygame.Surface((self.cols, self.rows))
        self.mini_seen = pygame.Surface((self.cols, self.rows))
        for s in (self.mini_full, self.mini_seen):
            s.fill((0, 0, 0))
        for y in range(self.rows):
            for x in range(self.cols):
                self.mini_full.set_at((x, y), (40, 60, 150) if (x, y) in self.walls else (200, 205, 235))
        self.seen = set()
        self.mini_scale = min(156.0 / self.cols, 100.0 / self.rows)
        self.update_dist()
        self.update_cam()

    # -- actores
    def make_enemy(self, kind, c, r):
        st = self.stage
        mult = 1 + 0.04 * st
        run_p = 0.003 + 0.0006 * st
        detect = 8 + 2 * st
        if kind == "human":
            return Chaser(c, r, "human", 0.066 * mult, min(0.99, 0.85 + 0.015 * st), detect + 2, run_p + 0.001)
        i = int(kind[3])
        return Chaser(c, r, kind, [0.055, 0.062][i] * mult, min(0.97, [0.55, 0.62][i] + 0.05 * st), detect, run_p)

    def spawn_enemies(self):
        g = self.game
        self.enemies = []
        for i in (0, 1):
            if g.dogs[i]:
                self.enemies.append(self.make_enemy("dog%d" % i, *self.dstart[i]))
        self.enemies.append(self.make_enemy("human", *self.hstart))

    def reset_actors(self):
        self.cat = MazeCat(*self.cstart)
        self.spawn_enemies()
        self.grace = 130
        self.last_key = None
        self.balls = []

    # -- IA
    def update_dist(self):
        cat = self.cat
        self.dist = bfs(self.walls, (cat.c, cat.r), self.bfs_limit)
        # emboscada: casilla unas cuantas celdas delante del gato
        tc, tr = cat.c, cat.r
        lead = 3 + self.stage // 2
        for _ in range(lead):
            nc, nr = tc + cat.fd[0], tr + cat.fd[1]
            if (nc, nr) in self.walls:
                break
            tc, tr = nc, nr
        self.dist2 = bfs(self.walls, (tc, tr), self.bfs_limit) if (tc, tr) != (cat.c, cat.r) else {}
        # explorado
        for y in range(max(0, cat.r - 8), min(self.rows, cat.r + 9)):
            for x in range(max(0, cat.c - 8), min(self.cols, cat.c + 9)):
                if (x, y) not in self.seen and (x - cat.c) ** 2 + (y - cat.r) ** 2 <= 70:
                    self.seen.add((x, y))
                    self.mini_seen.set_at((x, y), (40, 60, 150) if (x, y) in self.walls else (200, 205, 235))

    def update_cam(self):
        cx, cy = self.cat.px + 16, self.cat.py + 16
        self.camx = clamp(cx - W / 2, 0, self.cols * T - W)
        self.camy = clamp(cy - H / 2, 0, self.rows * T - H)

    def throw(self):
        g = self.game
        if g.ball_ammo <= 0:
            return
        g.ball_ammo -= 1
        d = self.cat.fd if self.cat.fd != (0, 0) else (1, 0)
        self.balls.append(MazeBall(self.cat.px + 16, self.cat.py + 16, d))
        play("throw")

    def update(self, events):
        g = self.game
        for e in events:
            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    g.pause(self)
                    return
                if e.key in BALL_KEYS:
                    self.throw()
        cat = self.cat
        keys = pygame.key.get_pressed()
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            cat.want = (-1, 0)
        elif keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            cat.want = (1, 0)
        elif keys[pygame.K_UP] or keys[pygame.K_w]:
            cat.want = (0, -1)
        elif keys[pygame.K_DOWN] or keys[pygame.K_s]:
            cat.want = (0, 1)
        self.scale = g.time_scale()
        cat.reverse_if_needed()
        cat.advance(self)
        key = (cat.c, cat.r, cat.fd)
        if key != self.last_key:
            self.last_key = key
            self.update_dist()
        self.t += 1
        if self.msg_t > 0:
            self.msg_t -= 1
        self.parts.update()
        if self.grace > 0:
            self.grace -= 1
        else:
            for en in self.enemies:
                en.think(self)
                en.advance(self)
                if en.mode == "run" and self.t % 5 == 0:
                    self.parts.burst(en.px + 16, en.py + 28, (200, 190, 170), 2, 1.2, 18, 0.02, 3)
            if self.mouse.stun > 0:
                self.mouse.stun -= 1
            self.mouse.advance(self)
        # pelotas
        for b in list(self.balls):
            b.x += b.d[0] * 7
            b.y += b.d[1] * 7
            b.life -= 1
            if (int(b.x) // T, int(b.y) // T) in self.walls or b.life <= 0:
                b.dead = True
            else:
                for en in self.enemies:
                    if math.hypot(en.px + 16 - b.x, en.py + 16 - b.y) < 22:
                        en.stun = 240
                        b.dead = True
                        self.parts.burst(b.x, b.y, (255, 230, 90), 12, 3)
                        play("stomp")
                        break
                if not b.dead and math.hypot(self.mouse.px + 16 - b.x, self.mouse.py + 16 - b.y) < 22:
                    self.mouse.stun = 180
                    b.dead = True
                    play("stomp")
            if b.dead:
                self.balls.remove(b)
        self.update_cam()
        cx, cy = cat.px + 16, cat.py + 16
        # enemigos
        if self.grace <= 0 and not g.has("shield"):
            for en in self.enemies:
                if en.stun <= 0 and math.hypot(en.px + 16 - cx, en.py + 16 - cy) < 22:
                    dmg = roll_human_damage() if en.kind == "human" else roll_dog_damage()
                    g.damage(dmg)
                    g.hit_event = 0
                    play("hit")
                    self.parts.text(cx, cy - 10, "-" + fmt_num(dmg), (255, 90, 90))
                    if g.hp <= 0:
                        g.go(GameOverScene(g))
                    else:
                        self.reset_actors()
                        self.msg, self.msg_t = ["¡Te atrapó! -%s corazones" % fmt_num(dmg)], 150
                    return
        # orbes
        for o in list(self.orbs):
            if math.hypot(o["c"] * T + 16 - cx, o["r"] * T + 16 - cy) < 22:
                self.orbs.remove(o)
                g.give(o["kind"])
                self.parts.burst(o["c"] * T + 16, o["r"] * T + 16, ITEM_COL[o["kind"]], 16, 4)
                play("power")
        # raton
        m = self.mouse
        if math.hypot(m.px + 16 - cx, m.py + 16 - cy) < 20:
            play("pick")
            g.collected += 1               # el nivel depende del orden en que los atrapas
            g.go(LevelScene(g, g.collected))

    # -- dibujo
    def visible(self, px, py, sense):
        if sense:
            return True
        return math.hypot(px - (self.cat.px + 16), py - (self.cat.py + 16)) < 340

    def draw(self, dst):
        g = self.game
        sense = g.has("sense")
        ox, oy = -int(self.camx), -int(self.camy)
        x0, y0 = int(self.camx) // T, int(self.camy) // T
        walls = self.walls
        tl = self.tiles
        for r in range(y0, min(self.rows, y0 + H // T + 2)):
            for c in range(x0, min(self.cols, x0 + W // T + 2)):
                if (c, r) in walls:
                    mask = ((1 if (c, r - 1) not in walls else 0) | (2 if (c + 1, r) not in walls else 0)
                            | (4 if (c, r + 1) not in walls else 0) | (8 if (c - 1, r) not in walls else 0))
                    dst.blit(tl[mask], (c * T + ox, r * T + oy))
                else:
                    dst.blit(tl["floor"], (c * T + ox, r * T + oy))
        # orbes de poder
        for o in self.orbs:
            px, py = o["c"] * T + 16, o["r"] * T + 16
            if self.visible(px, py, sense):
                bob = int(math.sin((self.t + o["c"] * 7) * 0.12) * 3)
                pygame.draw.circle(dst, shade(ITEM_COL[o["kind"]], -90), (px + ox, py + oy + 2), 19)
                dst.blit(A["items"][o["kind"]], (px - 15 + ox, py - 15 + oy + bob))
        # raton
        m = self.mouse
        if self.visible(m.px + 16, m.py + 16, sense):
            bob = int(math.sin(self.t * 0.2) * 2)
            pygame.draw.circle(dst, (60, 80, 50), (int(m.px) + 16 + ox, int(m.py) + 20 + oy), 14)
            dst.blit(A["mouse_r"] if m.fd[0] > 0 else A["mouse"], (int(m.px) - O + ox, int(m.py) - O + oy + bob))
            if sense:
                pygame.draw.circle(dst, (255, 255, 255), (int(m.px) + 16 + ox, int(m.py) + 16 + oy),
                                   20 + int(3 * math.sin(self.t * 0.2)), 2)
            if m.stun > 0:
                self.draw_stars(dst, int(m.px) + 16 + ox, int(m.py) - 2 + oy)
        # enemigos
        for en in self.enemies:
            if not self.visible(en.px + 16, en.py + 16, sense):
                continue
            ex, ey = int(en.px) + ox, int(en.py) + oy
            img = A["human_top"] if en.kind == "human" else A["dog_top"][en.kind]
            if en.mode == "run":
                for i in range(3):
                    pygame.draw.line(dst, (255, 255, 255), (ex + 16 - en.fd[0] * (18 + i * 6), ey + 10 + i * 6 - en.fd[1] * 12),
                                     (ex + 16 - en.fd[0] * (30 + i * 6), ey + 10 + i * 6 - en.fd[1] * 20), 2)
            dst.blit(img, (ex - O, ey - O))
            if sense:
                pygame.draw.circle(dst, (255, 70, 70), (ex + 16, ey + 16), 22, 2)
            if en.stun > 0:
                self.draw_stars(dst, ex + 16, ey - 4)
            elif en.mode == "run":
                pygame.draw.rect(dst, (30, 20, 10), (ex + 1, ey - 8, 30, 5))
                pygame.draw.rect(dst, (255, 150, 30), (ex + 2, ey - 7, int(28 * en.mt / RUN_MAX), 3))
            elif en.mode == "tired":
                pygame.draw.rect(dst, (10, 20, 40), (ex + 1, ey - 8, 30, 5))
                pygame.draw.rect(dst, (90, 170, 255), (ex + 2, ey - 7, int(28 * en.mt / TIRED_MAX), 3))
                dy = (self.t // 4) % 8
                pygame.draw.ellipse(dst, (140, 210, 255), (ex + 26, ey + 2 + dy, 4, 7))
                pygame.draw.ellipse(dst, (140, 210, 255), (ex + 2, ey + 6 + (dy + 4) % 8, 4, 7))
        for b in self.balls:
            dst.blit(A["catball"], (int(b.x) - 12 + ox, int(b.y) - 12 + oy))
        cat = self.cat
        if not (self.grace > 0 and (self.grace // 6) % 2 == 0):
            tops = A["cat_top"][g.skin]
            cx, cy = int(cat.px) + ox, int(cat.py) + oy
            if g.has("speed"):
                for i in range(3):
                    pygame.draw.line(dst, (255, 225, 90), (cx + 16 - cat.fd[0] * (16 + i * 5), cy + 8 + i * 8),
                                     (cx + 16 - cat.fd[0] * (28 + i * 5), cy + 8 + i * 8), 2)
            dst.blit(tops[cat.fd if cat.fd in tops else (1, 0)], (cx - O, cy - O))
            if g.has("shield"):
                ph = self.t * 0.15
                col = (int(140 + 115 * math.sin(ph)), int(140 + 115 * math.sin(ph + 2.1)), int(140 + 115 * math.sin(ph + 4.2)))
                pygame.draw.circle(dst, col, (cx + 16, cy + 16), 24, 3)
        self.parts.draw(dst, -ox, -oy)
        if not sense:
            fx = int(cat.px + 16 + ox) - W
            fy = int(cat.py + 16 + oy) - H
            dst.blit(A["fog"], (fx, fy))
        self.draw_hud(dst, sense)

    def draw_stars(self, dst, x, y):
        for i in range(3):
            a = self.t * 0.2 + i * 2.1
            pygame.draw.circle(dst, (255, 230, 90), (int(x + math.cos(a) * 9), int(y + math.sin(a) * 3)), 3)

    def draw_hud(self, dst, sense):
        g = self.game
        n = hearts_count(g.hp)
        panel(dst, (6, 6, n * 29 + 14, 40))
        draw_hearts(dst, 12, 12, g.hp, n)
        draw_powers(dst, g, 8, 50)
        panel(dst, (W - 262, 6, 256, 36))
        for i in range(10):
            dst.blit(A["mouse_small"] if i < g.collected else A["mouse_dim"], (W - 254 + i * 25, 12))
        txt(dst, "LABERINTO %d/10 · %dx%d" % (self.stage + 1, self.cols, self.rows), 14, (200, 210, 255),
            W - 134, 44, True)
        # minimapa
        src = self.mini_full if sense else self.mini_seen
        mw, mh = int(self.cols * self.mini_scale), int(self.rows * self.mini_scale)
        mini = pygame.transform.scale(src, (mw, mh))
        panel(dst, (W - mw - 14, 62, mw + 8, mh + 8), alpha=170)
        dst.blit(mini, (W - mw - 10, 66))
        s = self.mini_scale
        mx0, my0 = W - mw - 10, 66
        pygame.draw.circle(dst, (255, 230, 60), (int(mx0 + self.cat.px / T * s), int(my0 + self.cat.py / T * s)), 3)
        hint = sense or self.t > 1500
        if hint:
            pygame.draw.circle(dst, (255, 255, 255), (int(mx0 + self.mouse.px / T * s), int(my0 + self.mouse.py / T * s)), 3)
        if sense:
            for en in self.enemies:
                pygame.draw.circle(dst, (255, 70, 70), (int(mx0 + en.px / T * s), int(my0 + en.py / T * s)), 2)
        # flecha hacia el raton
        if hint:
            m = self.mouse
            ox, oy = -int(self.camx), -int(self.camy)
            cxs, cys = self.cat.px + 16 + ox, self.cat.py + 16 + oy
            mxs, mys = m.px + 16 + ox, m.py + 16 + oy
            if not (0 < mxs < W and 0 < mys < H):
                a = math.atan2(mys - cys, mxs - cxs)
                ax, ay = cxs + math.cos(a) * 90, cys + math.sin(a) * 90
                pygame.draw.polygon(dst, (255, 255, 255), [(ax + math.cos(a) * 14, ay + math.sin(a) * 14),
                                                           (ax + math.cos(a + 2.5) * 11, ay + math.sin(a + 2.5) * 11),
                                                           (ax + math.cos(a - 2.5) * 11, ay + math.sin(a - 2.5) * 11)])
                txt(dst, "ratón", 14, (255, 255, 255), int(ax), int(ay) + 12, True)
        if g.ball_ammo > 0:
            txt(dst, "C = lanzar pelota", 14, (255, 240, 160), W // 2, H - 24, True)
        if self.msg_t > 0 and self.msg:
            panel(dst, (90, 250, 620, 40 + 34 * len(self.msg)), alpha=210, border=(255, 220, 90))
            for i, line in enumerate(self.msg):
                txt(dst, line, 26 if i == 0 else 22, (255, 240, 120) if i == 0 else (140, 255, 170),
                    W // 2, 262 + i * 34, True)
        elif self.t < 150 and self.grace > 0:
            banner(dst, 250, "LABERINTO %d/10" % (self.stage + 1),
                   "Atrapa al ratón. ¡Los enemigos aprenden… y a veces corren!", (255, 220, 80), 100)


# ----------------------------------------------------------------------------
#  EDITOR DE SKINS (tipo Paint)
# ----------------------------------------------------------------------------
PALETTE = [
    (0, 0, 0), (60, 60, 70), (120, 120, 135), (190, 190, 205), (255, 255, 255), (120, 70, 40), (170, 110, 60), (230, 180, 120),
    (240, 150, 50), (190, 95, 25), (255, 225, 170), (255, 205, 60), (250, 250, 120), (150, 220, 70), (60, 170, 80), (30, 100, 60),
    (230, 60, 60), (160, 20, 40), (255, 130, 160), (255, 110, 200), (200, 80, 220), (110, 60, 190), (60, 80, 230), (90, 170, 255),
    (60, 210, 230), (20, 140, 150), (240, 240, 200), (210, 160, 255), (255, 170, 90), (90, 60, 30), (35, 25, 45), (140, 255, 200),
]


class SkinEditor:
    ticks_powers = False
    R_TAB = {"side": (30, 36, 150, 30), "top": (190, 36, 150, 30)}
    PAL_X, PAL_Y = 430, 190
    SLID_X, SLID_W = 452, 220
    R_TOOLS = [("pencil", "LÁPIZ", (430, 395, 86, 32)), ("eraser", "BORRAR", (522, 395, 86, 32)),
               ("fill", "CUBETA", (614, 395, 86, 32)), ("pick", "PIPETA", (706, 395, 70, 32))]
    R_UNDO, R_CLEAR, R_TEMPL = (430, 435, 110, 32), (546, 435, 110, 32), (662, 435, 114, 32)
    R_MIRROR = (430, 475, 230, 32)
    R_SAVE, R_CANCEL = (430, 540, 170, 44), (610, 540, 166, 44)
    CX, CY = 30, 78

    def __init__(self, game, slot):
        self.game, self.slot = game, slot
        data = game.custom[slot]
        self.base = game.skin if game.skin < N_BUILTIN else 0
        if data:
            self.side = decode_grid(data["side"], 22, 17)
            self.top = decode_grid(data["top"], 16, 16)
        else:
            self.side, self.top = template_grids(self.base)
        self.tab = "side"
        self.color = (240, 150, 50)
        self.rgb = list(self.color)
        self.tool = "pencil"
        self.undo = []
        self.mirror = True
        self.drag = None            # "canvas" o indice de slider
        self.last = None
        self.t = 0
        self.msg, self.msg_t = "", 0

    # -- geometria
    def grid(self):
        return self.side if self.tab == "side" else self.top

    def dims(self):
        return (22, 17, 17) if self.tab == "side" else (16, 16, 18)

    def cell_at(self, pos):
        w, h, cs = self.dims()
        x, y = (pos[0] - self.CX) // cs, (pos[1] - self.CY) // cs
        return (x, y) if 0 <= x < w and 0 <= y < h else None

    @staticmethod
    def inside(pos, rect):
        return rect[0] <= pos[0] < rect[0] + rect[2] and rect[1] <= pos[1] < rect[1] + rect[3]

    # -- edicion
    def push_undo(self):
        self.undo.append(([r[:] for r in self.side], [r[:] for r in self.top]))
        if len(self.undo) > 40:
            self.undo.pop(0)

    def do_undo(self):
        if self.undo:
            self.side, self.top = self.undo.pop()

    def set_cell(self, x, y, val):
        g = self.grid()
        w = self.dims()[0]
        g[y][x] = val
        if self.tab == "top" and self.mirror:
            g[y][w - 1 - x] = val

    def flood(self, x, y):
        g = self.grid()
        w, h, _ = self.dims()
        target = g[y][x]
        new = self.color
        if target == new:
            return
        q = deque([(x, y)])
        while q:
            cx, cy = q.popleft()
            if not (0 <= cx < w and 0 <= cy < h) or g[cy][cx] != target:
                continue
            g[cy][cx] = new
            q.extend(((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)))

    def apply(self, cell, first=False):
        x, y = cell
        if self.tool == "pencil":
            self.set_cell(x, y, self.color)
        elif self.tool == "eraser":
            self.set_cell(x, y, None)
        elif self.tool == "fill" and first:
            self.flood(x, y)
        elif self.tool == "pick" and first:
            c = self.grid()[y][x]
            if c:
                self.set_color(c)

    def stroke(self, cell):
        """Linea entre la ultima casilla y esta (sin huecos al arrastrar)."""
        if self.last is None or self.tool not in ("pencil", "eraser"):
            self.apply(cell)
        else:
            x0, y0 = self.last
            x1, y1 = cell
            n = max(abs(x1 - x0), abs(y1 - y0), 1)
            for i in range(n + 1):
                self.apply((x0 + (x1 - x0) * i // n, y0 + (y1 - y0) * i // n))
        self.last = cell

    def set_color(self, c):
        self.color = (int(c[0]), int(c[1]), int(c[2]))
        self.rgb = list(self.color)

    def slider_set(self, i, mx):
        self.rgb[i] = int(clamp((mx - self.SLID_X) / self.SLID_W, 0, 1) * 255)
        self.color = tuple(self.rgb)

    def say(self, s):
        self.msg, self.msg_t = s, 120

    # -- eventos
    def click(self, pos, button):
        g = self.game
        if button == 3:
            cell = self.cell_at(pos)
            if cell and self.grid()[cell[1]][cell[0]]:
                self.set_color(self.grid()[cell[1]][cell[0]])
            return
        for tab, r in self.R_TAB.items():
            if self.inside(pos, r):
                self.tab = tab
                return
        cell = self.cell_at(pos)
        if cell:
            self.push_undo()
            self.drag, self.last = "canvas", None
            if self.tool in ("pencil", "eraser"):
                self.stroke(cell)
            else:
                self.apply(cell, True)
            return
        for i, c in enumerate(PALETTE):
            r = (self.PAL_X + (i % 8) * 30, self.PAL_Y + (i // 8) * 30, 28, 28)
            if self.inside(pos, r):
                self.set_color(c)
                self.tool = "pencil" if self.tool in ("eraser", "pick") else self.tool
                return
        for i in range(3):
            if self.inside(pos, (self.SLID_X - 4, 322 + i * 20 - 3, self.SLID_W + 8, 20)):
                self.drag = i
                self.slider_set(i, pos[0])
                return
        for name, _, r in self.R_TOOLS:
            if self.inside(pos, r):
                self.tool = name
                return
        if self.inside(pos, self.R_UNDO):
            self.do_undo()
        elif self.inside(pos, self.R_CLEAR):
            self.push_undo()
            g_ = self.grid()
            for row in g_:
                for x in range(len(row)):
                    row[x] = None
        elif self.inside(pos, self.R_TEMPL):
            self.push_undo()
            self.base = (self.base + 1) % N_BUILTIN
            self.side, self.top = template_grids(self.base)
            self.say("Plantilla: " + SKINS[self.base]["name"])
        elif self.inside(pos, self.R_MIRROR):
            self.mirror = not self.mirror
        elif self.inside(pos, self.R_SAVE):
            self.save()
        elif self.inside(pos, self.R_CANCEL):
            g.go(MenuScene(g, "skins", view=g.skin))

    def save(self):
        g = self.game
        g.custom[self.slot] = {"side": encode_grid(self.side), "top": encode_grid(self.top)}
        g.save["custom"] = g.custom
        idx = N_BUILTIN + self.slot
        install_custom(idx, self.side, self.top)
        g.skin = idx
        g.save["skin"] = idx
        write_save(g.save)
        play("win")
        g.go(MenuScene(g, "skins", view=idx))

    def update(self, events):
        g = self.game
        self.t += 1
        if self.msg_t > 0:
            self.msg_t -= 1
        for e in events:
            if e.type == pygame.MOUSEBUTTONDOWN:
                self.click(e.pos, getattr(e, "button", 1))
            elif e.type == pygame.MOUSEMOTION:
                if self.drag == "canvas":
                    cell = self.cell_at(e.pos)
                    if cell and self.tool in ("pencil", "eraser"):
                        self.stroke(cell)
                elif isinstance(self.drag, int):
                    self.slider_set(self.drag, e.pos[0])
            elif e.type == pygame.MOUSEBUTTONUP:
                self.drag, self.last = None, None
            elif e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    g.go(MenuScene(g, "skins", view=g.skin))
                    return
                elif e.key == pygame.K_TAB:
                    self.tab = "top" if self.tab == "side" else "side"
                elif e.key == pygame.K_z and (pygame.key.get_mods() & pygame.KMOD_CTRL):
                    self.do_undo()
                elif e.key in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4):
                    self.tool = ["pencil", "eraser", "fill", "pick"][e.key - pygame.K_1]

    # -- dibujo
    def draw(self, dst):
        dst.fill((16, 14, 34))
        for i in range(30):
            pygame.draw.circle(dst, (34, 30, 66), ((i * 131 + self.t) % W, (i * 77) % H), 3)
        mp = pygame.mouse.get_pos()
        txt(dst, "EDITOR DE SKINS · MI SKIN %d" % (self.slot + 1), 20, (255, 220, 100), 30, 6, False)
        for tab, r in self.R_TAB.items():
            small_button(dst, r, "VISTA LATERAL" if tab == "side" else "VISTA SUPERIOR", self.tab == tab,
                         self.inside(mp, r), 16)
        w, h, cs = self.dims()
        g = self.grid()
        pygame.draw.rect(dst, (8, 8, 20), (self.CX - 4, self.CY - 4, w * cs + 8, h * cs + 8), border_radius=6)
        for y in range(h):
            for x in range(w):
                c = g[y][x]
                rect = (self.CX + x * cs, self.CY + y * cs, cs, cs)
                if c:
                    pygame.draw.rect(dst, c, rect)
                else:
                    pygame.draw.rect(dst, (70, 72, 92) if (x + y) % 2 == 0 else (52, 54, 74), rect)
        for x in range(w + 1):
            pygame.draw.line(dst, (20, 20, 40), (self.CX + x * cs, self.CY), (self.CX + x * cs, self.CY + h * cs))
        for y in range(h + 1):
            pygame.draw.line(dst, (20, 20, 40), (self.CX, self.CY + y * cs), (self.CX + w * cs, self.CY + y * cs))
        if self.tab == "top" and self.mirror:
            pygame.draw.line(dst, (255, 120, 120), (self.CX + w * cs // 2, self.CY), (self.CX + w * cs // 2, self.CY + h * cs), 1)
        cell = self.cell_at(mp)
        if cell:
            pygame.draw.rect(dst, (255, 255, 255), (self.CX + cell[0] * cs, self.CY + cell[1] * cs, cs, cs), 2)
        txt(dst, "Clic izq = dibujar · clic der = pipeta · Ctrl+Z = deshacer · TAB = cambiar vista", 13,
            (190, 195, 230), self.CX, self.CY + max(h * cs, 0) + 12, False, False)
        # previsualizacion real
        panel(dst, (430, 36, 350, 146), alpha=200)
        side = grid_to_surface(self.side, 22, 17, 2)
        side = pygame.transform.scale(side, (132, 102))
        bob = int(math.sin(self.t * 0.12) * 3)
        dst.blit(side, (444, 58 + bob))
        up = pygame.transform.scale(grid_to_surface(self.top, 16, 16, 2), (96, 96))
        dst.blit(up, (620, 62))
        txt(dst, "VISTA PREVIA", 14, (190, 195, 230), 444, 40, False, False)
        # paleta
        for i, c in enumerate(PALETTE):
            r = (self.PAL_X + (i % 8) * 30, self.PAL_Y + (i // 8) * 30, 28, 28)
            pygame.draw.rect(dst, c, r, border_radius=4)
            if c == self.color:
                pygame.draw.rect(dst, (255, 255, 255), r, 3, border_radius=4)
        # sliders RGB
        for i, (lab, col) in enumerate((("R", (255, 80, 80)), ("G", (80, 255, 100)), ("B", (90, 150, 255)))):
            y = 322 + i * 20
            txt(dst, lab, 14, col, 432, y - 2, False, False)
            pygame.draw.rect(dst, (30, 30, 50), (self.SLID_X, y, self.SLID_W, 14), border_radius=7)
            pygame.draw.rect(dst, col, (self.SLID_X, y, int(self.SLID_W * self.rgb[i] / 255), 14), border_radius=7)
            pygame.draw.circle(dst, (255, 255, 255), (self.SLID_X + int(self.SLID_W * self.rgb[i] / 255), y + 7), 8, 2)
        pygame.draw.rect(dst, self.color, (690, 322, 60, 54), border_radius=8)
        pygame.draw.rect(dst, (255, 255, 255), (690, 322, 60, 54), 2, border_radius=8)
        for name, label, r in self.R_TOOLS:
            small_button(dst, r, label, self.tool == name, self.inside(mp, r), 15)
        small_button(dst, self.R_UNDO, "DESHACER", False, self.inside(mp, self.R_UNDO), 15)
        small_button(dst, self.R_CLEAR, "LIMPIAR", False, self.inside(mp, self.R_CLEAR), 15)
        small_button(dst, self.R_TEMPL, "PLANTILLA", False, self.inside(mp, self.R_TEMPL), 15)
        small_button(dst, self.R_MIRROR, "SIMETRÍA (vista sup.): " + ("SÍ" if self.mirror else "NO"),
                     self.mirror, self.inside(mp, self.R_MIRROR), 14)
        small_button(dst, self.R_SAVE, "GUARDAR Y USAR", False, self.inside(mp, self.R_SAVE), 18)
        small_button(dst, self.R_CANCEL, "CANCELAR", False, self.inside(mp, self.R_CANCEL), 18)
        if self.msg_t > 0:
            txt(dst, self.msg, 18, (140, 255, 170), 430, 515, False)


# ----------------------------------------------------------------------------
#  MENUS
# ----------------------------------------------------------------------------
class MenuScene:
    ITEMS = ["JUGAR", "SKINS", "CÓMO JUGAR", "SALIR"]
    R_EDIT = (W // 2 - 130, 486, 260, 38)

    def __init__(self, game, page="main", view=None):
        self.game = game
        self.page = page
        self.sel = 0
        self.t = 0
        self.view = game.skin if view is None else view

    def start_game(self):
        self.game.new_game()
        self.game.go(MazeScene(self.game))

    def edit(self):
        if self.view >= N_BUILTIN:
            self.game.go(SkinEditor(self.game, self.view - N_BUILTIN))

    def update(self, events):
        g = self.game
        self.t += 1
        for e in events:
            if e.type == pygame.MOUSEBUTTONDOWN and self.page == "skins":
                if SkinEditor.inside(e.pos, self.R_EDIT) and self.view >= N_BUILTIN:
                    play("pick")
                    self.edit()
                    return
            if e.type != pygame.KEYDOWN:
                continue
            k = e.key
            if self.page == "main":
                if k in (pygame.K_UP, pygame.K_w):
                    self.sel = (self.sel - 1) % len(self.ITEMS)
                    play("menu")
                elif k in (pygame.K_DOWN, pygame.K_s):
                    self.sel = (self.sel + 1) % len(self.ITEMS)
                    play("menu")
                elif k in (pygame.K_RETURN, pygame.K_SPACE):
                    play("pick")
                    if self.sel == 0:
                        self.start_game()
                    elif self.sel == 1:
                        self.page, self.view = "skins", g.skin
                    elif self.sel == 2:
                        self.page = "help"
                    else:
                        pygame.quit()
                        sys.exit()
                elif k == pygame.K_ESCAPE:
                    pygame.quit()
                    sys.exit()
            elif self.page == "skins":
                if k in (pygame.K_LEFT, pygame.K_a):
                    self.view = (self.view - 1) % N_SKINS
                    play("menu")
                elif k in (pygame.K_RIGHT, pygame.K_d):
                    self.view = (self.view + 1) % N_SKINS
                    play("menu")
                elif k in (pygame.K_RETURN, pygame.K_SPACE):
                    g.skin = self.view
                    g.save["skin"] = g.skin
                    write_save(g.save)
                    play("pick")
                elif k == pygame.K_e:
                    self.edit()
                    return
                elif k == pygame.K_ESCAPE:
                    self.page = "main"
            else:
                if k in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_SPACE):
                    self.page = "main"

    def draw(self, dst):
        g = self.game
        draw_menu_bg(dst, self.t, g.skin)
        if self.page == "main":
            bob = int(math.sin(self.t * 0.07) * 5)
            txt(dst, "MEOW", 104, (255, 190, 60), W // 2 - 190, 24 + bob, True, True, True)
            txt(dst, "MAYHEM", 104, (255, 90, 110), W // 2 + 150, 24 - bob, True, True, True)
            txt(dst, "¡El gato escapa de 2 perros y de un humano!", 22, (255, 255, 255), W // 2, 150, True)
            for i, label in enumerate(self.ITEMS):
                button(dst, W // 2, 200 + i * 66, 320, label, i == self.sel)
            txt(dst, "Victorias: %d" % g.save.get("wins", 0), 16, (200, 200, 230), 14, H - 28, False)
            txt(dst, "M = sonido   |   ↑↓ + ENTER", 16, (200, 200, 230), W - 14 - 190, H - 28, False)
        elif self.page == "skins":
            txt(dst, "SKINS", 60, (255, 220, 90), W // 2, 14, True, True, True)
            panel(dst, (200, 84, 400, 300), alpha=200)
            v = self.view
            bob = int(math.sin(self.t * 0.1) * 6)
            big = pygame.transform.scale(A["cat_side"][v][(self.t // 8) % 2][1], (264, 207))
            dst.blit(big, (W // 2 - 132, 126 + bob))
            top = pygame.transform.scale(A["cat_top"][v][(1, 0)], (64, 64))
            dst.blit(top, (W // 2 - 32, 316))
            lx, rx = 150, W - 150
            for cx, d in ((lx, -1), (rx, 1)):
                pygame.draw.polygon(dst, (255, 215, 80), [(cx + 24 * d, 220), (cx - 16 * d, 190), (cx - 16 * d, 250)])
            txt(dst, skin_name(v), 36, (255, 255, 255), W // 2, 396, True, True, True)
            equipped = v == g.skin
            txt(dst, "✔ EQUIPADA" if equipped else "ENTER = equipar", 20,
                (130, 255, 160) if equipped else (255, 220, 120), W // 2, 440, True)
            if v >= N_BUILTIN:
                mp = pygame.mouse.get_pos()
                filled = g.custom[v - N_BUILTIN] is not None
                small_button(dst, self.R_EDIT, ("✎ EDITAR MI DIBUJO (E)" if filled else "✎ DIBUJAR MI SKIN (E)"),
                             False, SkinEditor.inside(mp, self.R_EDIT), 18)
            else:
                txt(dst, "Las últimas 3 skins son para TUS dibujos", 16, (180, 190, 230), W // 2, 492, True, False)
            for i in range(N_SKINS):
                pygame.draw.circle(dst, (255, 215, 80) if i == v else (90, 90, 130),
                                   (W // 2 - (N_SKINS - 1) * 12 + i * 24, 548), 7 if i == v else 5)
            txt(dst, "← → cambiar     ESC = volver", 18, (200, 200, 230), W // 2, 570, True)
        else:
            txt(dst, "CÓMO JUGAR", 56, (255, 220, 90), W // 2, 8, True, True, True)
            panel(dst, (40, 74, 720, 494), alpha=220)
            lines = [
                ("LABERINTO (crece con cada nivel)", (255, 190, 70)),
                ("Atrapa al ratón: ¡huye! Los perros y el humano aprenden, corren (máx. 5 s)", None),
                ("y luego caminan a la mitad 6-7 s. Perro quita 3 (o 2 / 1,5), humano 4 (o 2 / 3).", None),
                ("PLATAFORMAS", (255, 190, 70)),
                ("ESPACIO = saltar · X = arañar (1,2 s) · C = lanzar pelota · ↓ = bajar al volar", None),
                ("Golpea bloques ? desde abajo. ¡Hay bloques SECRETOS invisibles!", None),
                ("PODERES", (255, 190, 70)),
                ("Vida extra · Curación · Velocidad · Inmunidad · Volar · Sentido gatuno ·", None),
                ("Cámara lenta (todo lento menos tú, con efecto mareo) · Pelota", None),
                ("JEFES", (255, 190, 70)),
                ("3.er ratón: Perro 1 · 6.º: Perro 2 · 10.º: EL HUMANO (25 corazones).", None),
                ("Saltar sobre un perro = 3 s invulnerable. El humano descansa 5 s tras atacar.", None),
                ("Si llegas a la meta de su persecución se cansa 4 s y recibe doble daño.", None),
                ("CORAZONES", (255, 190, 70)),
                ("Cada nivel +1 (máx. 5). Jefe sin daño: +3 sin límite. 20 pescados: +1.", None),
            ]
            y = 84
            for text, col in lines:
                if col:
                    txt(dst, text, 20, col, 60, y, False)
                    y += 28
                else:
                    txt(dst, text, 16, (235, 235, 255), 70, y, False, False)
                    y += 23
            txt(dst, "ESC / ENTER = volver", 16, (200, 200, 230), W // 2, 574, True)


class PauseScene:
    ITEMS = ["CONTINUAR", "SONIDO", "MENÚ PRINCIPAL"]
    ticks_powers = False

    def __init__(self, game, prev):
        self.game, self.prev = game, prev
        self.sel = 0

    def update(self, events):
        g = self.game
        for e in events:
            if e.type != pygame.KEYDOWN:
                continue
            k = e.key
            if k == pygame.K_ESCAPE:
                g.scene = self.prev
                return
            if k in (pygame.K_UP, pygame.K_w):
                self.sel = (self.sel - 1) % 3
                play("menu")
            elif k in (pygame.K_DOWN, pygame.K_s):
                self.sel = (self.sel + 1) % 3
                play("menu")
            elif k in (pygame.K_RETURN, pygame.K_SPACE):
                if self.sel == 0:
                    g.scene = self.prev
                    return
                elif self.sel == 1:
                    MUTED[0] = not MUTED[0]
                else:
                    g.go(MenuScene(g))
                    return

    def draw(self, dst):
        self.prev.draw(dst)
        ov = surf(W, H)
        ov.fill((0, 0, 20, 170))
        dst.blit(ov, (0, 0))
        panel(dst, (W // 2 - 190, 130, 380, 340), alpha=225)
        txt(dst, "PAUSA", 62, (255, 220, 90), W // 2, 140, True, True, True)
        for i, label in enumerate(self.ITEMS):
            if i == 1:
                label = "SONIDO: " + ("NO" if MUTED[0] else "SÍ")
            button(dst, W // 2, 235 + i * 70, 300, label, i == self.sel)


class GameOverScene:
    ITEMS = ["REINTENTAR", "MENÚ PRINCIPAL"]
    ticks_powers = False

    def __init__(self, game):
        self.game = game
        self.t = 0
        self.sel = 0
        self.got = game.collected

    def update(self, events):
        self.t += 1
        for e in events:
            if e.type != pygame.KEYDOWN:
                continue
            if e.key in (pygame.K_UP, pygame.K_DOWN, pygame.K_w, pygame.K_s):
                self.sel = 1 - self.sel
                play("menu")
            elif e.key in (pygame.K_RETURN, pygame.K_SPACE):
                if self.sel == 0:
                    self.game.new_game()
                    self.game.go(MazeScene(self.game))
                else:
                    self.game.go(MenuScene(self.game))
            elif e.key == pygame.K_ESCAPE:
                self.game.go(MenuScene(self.game))

    def draw(self, dst):
        dst.fill((28, 6, 12))
        for i in range(30):
            pygame.draw.circle(dst, (60, 14, 22), ((i * 131 + self.t) % W, (i * 77) % H), 3)
        txt(dst, "GAME OVER", 100, (240, 60, 60), W // 2, 70, True, True, True)
        panel(dst, (W // 2 - 230, 200, 460, 120), alpha=190, border=(240, 60, 60))
        txt(dst, "El gato fue atrapado...", 28, (255, 255, 255), W // 2, 214, True)
        txt(dst, "Ratones atrapados: %d / 10" % self.got, 24, (255, 220, 120), W // 2, 262, True)
        for i, label in enumerate(self.ITEMS):
            button(dst, W // 2, 360 + i * 70, 320, label, i == self.sel)


class WinScene:
    ticks_powers = False

    def __init__(self, game, flawless=False):
        self.game = game
        self.flawless = flawless
        self.t = 0
        game.save["wins"] = game.save.get("wins", 0) + 1
        write_save(game.save)
        self.conf = [[random.uniform(0, W), random.uniform(-H, 0), random.uniform(-1, 1), random.uniform(2, 5),
                      random.choice([(255, 90, 90), (255, 220, 80), (90, 220, 255), (150, 255, 120), (255, 130, 220)])]
                     for _ in range(140)]
        play("win")

    def update(self, events):
        self.t += 1
        for c in self.conf:
            c[0] += c[2]
            c[1] += c[3]
            if c[1] > H:
                c[1] = -10
        for e in events:
            if e.type == pygame.KEYDOWN and e.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_ESCAPE):
                self.game.go(MenuScene(self.game))

    def draw(self, dst):
        dst.blit(sky_surface((20, 20, 50), (90, 90, 160)), (0, 0))
        for c in self.conf:
            pygame.draw.rect(dst, c[4], (int(c[0]), int(c[1]), 8, 8))
        txt(dst, "¡EL GATO ES LIBRE!", 86, (255, 230, 100), W // 2, 60, True, True, True)
        big = pygame.transform.scale(A["cat_side"][self.game.skin][(self.t // 8) % 2][1], (230, 180))
        dst.blit(big, (W // 2 - 115, 230 - abs(int(math.sin(self.t * 0.1) * 34))))
        pygame.draw.rect(dst, (60, 150, 70), (0, 410, W, 198))
        panel(dst, (W // 2 - 240, 440, 480, 100), alpha=190, border=(255, 220, 90))
        txt(dst, "¡Derrotaste al humano!", 26, (255, 255, 255), W // 2, 448, True)
        if self.flawless:
            txt(dst, "★ SIN RECIBIR DAÑO EN EL JEFE ★", 22, (130, 255, 160), W // 2, 486, True)
        else:
            txt(dst, "Intenta vencerlo sin que te toque...", 20, (200, 220, 255), W // 2, 488, True)
        if (self.t // 30) % 2 == 0:
            txt(dst, "ENTER = menú", 22, (255, 255, 255), W // 2, 560, True)


# ----------------------------------------------------------------------------
#  JUEGO
# ----------------------------------------------------------------------------
class Game:
    def __init__(self):
        self.save = load_save()
        self.skin = int(self.save.get("skin", 0)) % N_SKINS
        custom = self.save.get("custom")
        self.custom = custom if isinstance(custom, list) and len(custom) == N_CUSTOM else [None] * N_CUSTOM
        self.new_game()
        self.scene = MenuScene(self)
        self.fade = 0

    def load_custom_skins(self):
        for i, d in enumerate(self.custom):
            if d:
                try:
                    install_custom(N_BUILTIN + i, decode_grid(d["side"], 22, 17), decode_grid(d["top"], 16, 16))
                except Exception:
                    self.custom[i] = None

    def new_game(self):
        self.hp = 5.0
        self.collected = 0
        self.dogs = [True, True]
        self.dmg_total = 0.0
        self.powers = {}
        self.ball_ammo = 0
        self.fish = 0
        self.hit_event = 0
        self.toast = None
        self.maze_seeds = {}

    def maze_seed(self, stage):
        if stage not in self.maze_seeds:
            self.maze_seeds[stage] = random.randrange(1, 10 ** 6)
        return self.maze_seeds[stage]

    # -- vida
    def damage(self, d):
        self.hp -= d
        self.dmg_total += d
        self.hit_event = d

    def heal(self, n, cap=float(MAX_HEARTS_NORMAL)):
        self.hp = max(self.hp, min(cap, self.hp + n))

    # -- poderes
    def has(self, name):
        return self.powers.get(name, 0) > 0

    def say(self, s, t=110):
        self.toast = [s, t]

    def give(self, kind):
        if kind == "life":
            self.hp += 1
            self.say("¡VIDA EXTRA! +1 corazón")
        elif kind == "heal":
            if self.hp < MAX_HEARTS_NORMAL:
                self.heal(1)
                self.say("+1 corazón recuperado")
            else:
                self.ball_ammo = min(9, self.ball_ammo + 3)
                self.say("¡PELOTA! +3 lanzamientos (C)")
        elif kind == "ball":
            self.ball_ammo = min(9, self.ball_ammo + 3)
            self.say("¡PELOTA! +3 lanzamientos (tecla C)")
        else:
            self.powers[kind] = POWER_DUR[kind]
            self.say("¡%s!" % POWER_NAMES[kind])

    def tick_powers(self):
        for k in list(self.powers):
            self.powers[k] -= 1
            if self.powers[k] <= 0:
                del self.powers[k]
        if self.toast:
            self.toast[1] -= 1
            if self.toast[1] <= 0:
                self.toast = None

    def time_scale(self):
        return SLOW_SCALE if self.has("slow") else 1.0

    def add_fish(self):
        self.fish += 1
        if self.fish % 20 == 0:
            self.heal(1)
            self.say("¡20 pescados! +1 corazón (máx. 5)")

    # -- flujo
    def go(self, scene):
        self.scene = scene
        self.fade = 255

    def pause(self, scene):
        self.scene = PauseScene(self, scene)

    def level_done(self, n):
        self.heal(1)
        if n == 3:
            self.go(BossDogScene(self, 0))
        elif n == 6:
            self.go(BossDogScene(self, 1))
        elif n == 10:
            self.go(BossHumanScene(self))
        else:
            self.go(MazeScene(self, ["¡Nivel %d completado!  +1 corazón" % n,
                                     "El laberinto ahora es MÁS GRANDE y los enemigos más listos"]))

    def dog_defeated(self, idx, flawless):
        self.dogs[idx] = False
        lines = ["¡El perro %d ya no te persigue!" % (idx + 1)]
        if flawless:
            self.hp += FLAWLESS_BONUS
            lines.append("★ ¡SIN DAÑO! +%d corazones extra ★" % FLAWLESS_BONUS)
        else:
            self.heal(1)
            lines.append("+1 corazón")
        self.go(MazeScene(self, lines))


def draw_toast(dst, game):
    if game.toast:
        s, t = game.toast
        a = min(1.0, t / 20.0)
        wd = font(24).size(s)[0] + 40
        y = 128 - int((1 - a) * 20)
        panel(dst, (W // 2 - wd // 2, y, wd, 40), alpha=int(215 * a), border=(255, 220, 90))
        txt(dst, s, 24, (255, 245, 170), W // 2, y + 6, True)


_tint = [None]


def blit_dizzy(screen, buf, t):
    """Efecto 'mareado' mientras dura la camara lenta."""
    if _tint[0] is None:
        _tint[0] = surf(W, H)
        _tint[0].fill((130, 60, 210, 40))
    screen.fill((20, 0, 40))
    amp = 6 + int(3 * math.sin(t * 0.05))
    for y in range(0, H, 8):
        off = int(math.sin(t * 0.09 + y * 0.045) * amp)
        screen.blit(buf, (off, y), pygame.Rect(0, y, W, 8))
    screen.blit(_tint[0], (0, 0))
    for i in range(7):
        a = t * 0.04 + i * 0.9
        x = W // 2 + int(math.cos(a) * (340 + 18 * math.sin(t * 0.03 + i)))
        y = H // 2 + int(math.sin(a) * 255)
        pygame.draw.circle(screen, (225, 170, 255), (x, y), 7, 2)
        pygame.draw.circle(screen, (255, 235, 120), (x, y), 2)


# ----------------------------------------------------------------------------
#  CONTROLES TACTILES (celular / APK Android)
# ----------------------------------------------------------------------------
TOUCH_ANDROID = bool(os.environ.get("ANDROID_ARGUMENT")) or os.environ.get("MEOW_FORCE_TOUCH") == "1"
GAMEPLAY_SCENES = ("LevelScene", "MazeScene", "BossDogScene", "BossHumanScene")

_real_get_pressed = pygame.key.get_pressed
TOUCH_KEYS_DOWN = {}


class _MergedKeys:
    __slots__ = ("_real",)

    def __init__(self, real):
        self._real = real

    def __getitem__(self, k):
        if TOUCH_KEYS_DOWN.get(k, 0) > 0:
            return True
        try:
            return self._real[k]
        except Exception:
            return False


def _patched_get_pressed():
    return _MergedKeys(_real_get_pressed())


if TOUCH_ANDROID:
    pygame.key.get_pressed = _patched_get_pressed


class TouchButton:
    def __init__(self, name, key, rect, label, shape="circle"):
        self.name, self.key, self.rect = name, key, pygame.Rect(rect)
        self.label, self.shape = label, shape

    def contains(self, pos):
        return self.rect.collidepoint(pos)


class TouchControls:
    """Capa de botones tactiles: mueve al gato y dispara acciones con el dedo."""

    def __init__(self):
        dp_cx, dp_cy, s = 96, H - 112, 50
        self.buttons = [
            TouchButton("left", pygame.K_LEFT, (dp_cx - s - 46, dp_cy - s // 2, s, s), "<"),
            TouchButton("right", pygame.K_RIGHT, (dp_cx + 46, dp_cy - s // 2, s, s), ">"),
            TouchButton("up", pygame.K_UP, (dp_cx - s // 2, dp_cy - s - 46, s, s), "^"),
            TouchButton("down", pygame.K_DOWN, (dp_cx - s // 2, dp_cy + 46, s, s), "v"),
            TouchButton("jump", pygame.K_SPACE, (W - 100, H - 184, 80, 80), "SALTO"),
            TouchButton("atk", pygame.K_x, (W - 192, H - 104, 66, 66), "GOLPE"),
            TouchButton("ball", pygame.K_c, (W - 100, H - 96, 66, 66), "BOLA"),
            TouchButton("pause", pygame.K_ESCAPE, (W - 48, 10, 38, 38), "II", "rect"),
        ]
        self.active = {}

    def _hit(self, pos):
        for b in self.buttons:
            if b.contains(pos):
                return b
        return None

    def _by_name(self, name):
        for b in self.buttons:
            if b.name == name:
                return b
        return None

    def _press(self, b):
        TOUCH_KEYS_DOWN[b.key] = TOUCH_KEYS_DOWN.get(b.key, 0) + 1
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=b.key))

    def _release(self, name):
        b = self._by_name(name)
        if b is None:
            return
        TOUCH_KEYS_DOWN[b.key] = max(0, TOUCH_KEYS_DOWN.get(b.key, 0) - 1)
        pygame.event.post(pygame.event.Event(pygame.KEYUP, key=b.key))

    def _move(self, fid, pos):
        b = self._hit(pos)
        old = self.active.get(fid)
        new = b.name if b else None
        if new == old:
            return
        if old:
            self._release(old)
            del self.active[fid]
        if b:
            self.active[fid] = b.name
            self._press(b)

    def _up(self, fid):
        old = self.active.pop(fid, None)
        if old:
            self._release(old)

    def handle(self, events):
        for e in events:
            et = e.type
            if et == pygame.FINGERDOWN:
                self._move(e.finger_id, (e.x * W, e.y * H))
            elif et == pygame.FINGERMOTION:
                self._move(e.finger_id, (e.x * W, e.y * H))
            elif et == pygame.FINGERUP:
                self._up(e.finger_id)
            elif et == pygame.MOUSEBUTTONDOWN and e.button == 1:
                self._move("mouse", e.pos)
            elif et == pygame.MOUSEMOTION and "mouse" in self.active:
                self._move("mouse", e.pos)
            elif et == pygame.MOUSEBUTTONUP and e.button == 1:
                self._up("mouse")

    def draw(self, dst):
        held_names = set(self.active.values())
        for b in self.buttons:
            held = b.name in held_names
            col = (255, 220, 90, 150) if held else (255, 255, 255, 85)
            s = surf(b.rect.w, b.rect.h)
            if b.shape == "circle":
                pygame.draw.ellipse(s, col, (0, 0, b.rect.w, b.rect.h))
                pygame.draw.ellipse(s, (20, 10, 30, 170), (0, 0, b.rect.w, b.rect.h), 3)
            else:
                pygame.draw.rect(s, col, (0, 0, b.rect.w, b.rect.h), border_radius=10)
                pygame.draw.rect(s, (20, 10, 30, 170), (0, 0, b.rect.w, b.rect.h), 3, border_radius=10)
            dst.blit(s, b.rect.topleft)
            fs = 12 if len(b.label) > 2 else 20
            txt(dst, b.label, fs, (30, 15, 40), b.rect.centerx, b.rect.centery, True)


def main():
    pygame.mixer.pre_init(22050, -16, 1, 512)
    pygame.init()
    try:
        pygame.display.set_icon(make_window_icon())
    except Exception:
        pass
    flags = pygame.SCALED if TOUCH_ANDROID else (pygame.SCALED | pygame.RESIZABLE)
    screen = pygame.display.set_mode((W, H), flags)
    pygame.display.set_caption("MEOW MAYHEM")
    clock = pygame.time.Clock()
    init_sounds()
    build_art()
    game = Game()
    game.load_custom_skins()
    touch = TouchControls() if TOUCH_ANDROID else None
    buf = pygame.Surface((W, H))
    fade_surf = pygame.Surface((W, H))
    fade_surf.fill((0, 0, 0))
    frame = 0
    while True:
        events = pygame.event.get()
        for e in events:
            if e.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if e.type == pygame.KEYDOWN and e.key == pygame.K_m:
                MUTED[0] = not MUTED[0]
        if touch is not None:
            touch.handle(events)
        game.scene.update(events)
        if getattr(game.scene, "ticks_powers", False):
            game.tick_powers()
        frame += 1
        if game.has("slow"):
            game.scene.draw(buf)
            draw_toast(buf, game)
            blit_dizzy(screen, buf, frame)
        else:
            game.scene.draw(screen)
            draw_toast(screen, game)
        if touch is not None and type(game.scene).__name__ in GAMEPLAY_SCENES:
            touch.draw(screen)
        if game.fade > 0:
            fade_surf.set_alpha(game.fade)
            screen.blit(fade_surf, (0, 0))
            game.fade = max(0, game.fade - 14)
        pygame.display.flip()
        clock.tick(FPS)


if __name__ == "__main__":
    main()
