# -*- coding: utf-8 -*-
"""데스크탑 캐릭터 위젯 — 메모 전용 (Python 표준 라이브러리만 사용)

- 캐릭터 클릭: 스티커 메모 열기
- 우클릭 → 캐릭터 변경: 캐릭터 고르기 / + 로 그림 추가
설정: 같은 폴더의 settings.ini
"""
import os
import sys
from datetime import datetime as _dt

# very first thing: record that the script was started (helps when nothing appears)
try:
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "launch.log"), "a", encoding="utf-8") as _f:
        _f.write("%s start  python=%s  exe=%s\n" % (_dt.now().isoformat(timespec="seconds"), sys.version.split()[0], sys.executable))
except Exception:
    pass

import copy
import ctypes
import json
import random
import math
import queue
import re
import shutil
import subprocess
import threading
import time
import traceback
import urllib.request
import webbrowser
from datetime import datetime, date

import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog

DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, DIR)
import widget_cal as usagi_cal  # noqa: E402

KEY = "#010101"              # colour made transparent on screen (near-black: soft edges blend into a dark outline)
LINE = "#4a3428"
TEXT = "#3c281e"
FONT = ("Malgun Gothic", 10)
APP_NAME = "DesktopBuddyWidget"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
STICKY_APP = "shell:AppsFolder\\Microsoft.MicrosoftStickyNotes_8wekyb3d8bbwe!App"

def log(msg):
    try:
        with open(os.path.join(DIR, "error.log"), "a", encoding="utf-8") as f:
            f.write(datetime.now().isoformat(timespec="seconds") + "  " + msg + "\n")
    except Exception:
        pass


# ---------------------------------------------------------------- Windows helpers
def single_instance():
    try:
        k32 = ctypes.windll.kernel32
        handle = k32.CreateMutexW(None, False, "DesktopBuddyWidget_Python")
        if k32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
            return None
        return handle
    except Exception:
        return True


def virtual_screen():
    try:
        u = ctypes.windll.user32
        x, y = u.GetSystemMetrics(76), u.GetSystemMetrics(77)
        return x, y, x + u.GetSystemMetrics(78), y + u.GetSystemMetrics(79)
    except Exception:
        return None


def work_area():
    try:
        class RECT(ctypes.Structure):
            _fields_ = [("l", ctypes.c_long), ("t", ctypes.c_long), ("r", ctypes.c_long), ("b", ctypes.c_long)]
        r = RECT()
        ctypes.windll.user32.SystemParametersInfoW(0x30, 0, ctypes.byref(r), 0)
        return r.l, r.t, r.r, r.b
    except Exception:
        return None


def sticky_installed():
    try:
        import winreg
    except ImportError:
        return False
    for path in (r"Software\Classes\ActivatableClasses\Package",
                 r"Software\Classes\Local Settings\Software\Microsoft\Windows\CurrentVersion\AppModel\Repository\Packages"):
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as k:
                i = 0
                while True:
                    try:
                        name = winreg.EnumKey(k, i)
                    except OSError:
                        break
                    if name.lower().startswith("microsoft.microsoftstickynotes_"):
                        return True
                    i += 1
        except OSError:
            continue
    return False


def pythonw_path():
    exe = sys.executable
    cands = []
    if exe:
        d = os.path.dirname(exe)
        if "\\program files\\windowsapps\\" not in exe.lower():
            cands.append(os.path.join(d, "pythonw.exe"))
    cands += [shutil.which("pythonw.exe"), shutil.which("pyw.exe")]
    for c in cands:
        if c and os.path.exists(c):
            return c
    return exe


def autostart_enabled():
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            winreg.QueryValueEx(k, APP_NAME)
            return True
    except Exception:
        return False


def set_autostart(on):
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
        if on:
            cmd = '"%s" "%s"' % (pythonw_path(), os.path.abspath(__file__))
            winreg.SetValueEx(k, APP_NAME, 0, winreg.REG_SZ, cmd)
        else:
            try:
                winreg.DeleteValue(k, APP_NAME)
            except FileNotFoundError:
                pass


# ---------------------------------------------------------------- UI pieces
MAX_SIZE = 170          # character height in px (same as the built-in Usagi)
CHAR_DIR = os.path.join(DIR, "characters")
CHOICE_FILE = os.path.join(DIR, "character_choice.txt")
BUILTIN = "__builtin__"
BUILTIN_NAME = "기본 캐릭터"
IMG_EXT = (".png", ".gif")
UI_DIR = os.path.join(DIR, "ui")
STATE_FILE = os.path.join(DIR, "state.json")
DEFAULT_CHAR = "토리.png"
ACC_DIR = os.path.join(DIR, "accessories")
FX_DIR = os.path.join(ACC_DIR, "effects")
DECOR_FILE = os.path.join(DIR, "decor.json")
SLOTS = ["ground", "body", "side", "head", "pin"]          # drawing order (head things on top)
SLOT_NAMES = {"head": "머리", "pin": "머리핀", "body": "몸", "side": "손", "ground": "바닥"}
SLOT_DEFAULT = {"head": dict(w=0.62, y=0.12), "pin": dict(w=0.30, y=0.10, x=0.72),
                "body": dict(w=0.90, y=0.62), "side": dict(w=0.38, y=0.66, x=0.95),
                "ground": dict(w=1.25, y=0.80)}
# bundled accessories: slot, width (x character width), y/x anchor (fractions of the character box)
ACC_INFO = {
    "산타모자.png": dict(slot="head", w=0.80, y=0.20),
    "루돌프뿔.png": dict(slot="head", w=0.92, y=0.12),
    "선물상자.png": dict(slot="side", w=0.38, y=0.72, x=0.95),
    "파티모자.png": dict(slot="head", w=0.42, y=0.08),
    "왕관.png": dict(slot="head", w=0.56, y=0.10),
    "리본.png": dict(slot="pin", w=0.46, y=0.10, x=0.5),
    "벚꽃화관.png": dict(slot="head", w=0.88, y=0.14),
    "벚꽃핀.png": dict(slot="pin", w=0.34, y=0.10, x=0.72),
    "벚꽃가지.png": dict(slot="side", w=0.45, y=0.55, x=0.95),
    "밀짚모자.png": dict(slot="head", w=1.05, y=0.22),
    "수경.png": dict(slot="head", w=0.80, y=0.20),
    "튜브.png": dict(slot="body", w=1.18, y=0.70),
    "모히또.png": dict(slot="side", w=0.30, y=0.66, x=0.95),
    "베레모.png": dict(slot="head", w=0.78, y=0.16),
    "단풍핀.png": dict(slot="pin", w=0.26, y=0.10, x=0.72),
    "코트.png": dict(slot="body", w=0.92, y=0.66),
    "책.png": dict(slot="side", w=0.42, y=0.68, x=0.92),
    "털모자.png": dict(slot="head", w=0.84, y=0.24),
    "귀마개.png": dict(slot="head", w=1.00, y=0.32),
    "목도리.png": dict(slot="body", w=0.86, y=0.52),
    "썰매.png": dict(slot="ground", w=1.35, y=0.80),
}
# themes: name, items, falling effect, one-click preset
THEMES = [
    ("기본", ["파티모자.png", "왕관.png", "리본.png"], None, []),
    ("봄 · 벚꽃", ["벚꽃화관.png", "벚꽃핀.png", "벚꽃가지.png"], "벚꽃잎", ["벚꽃화관.png", "벚꽃가지.png"]),
    ("여름 · 바다", ["밀짚모자.png", "수경.png", "튜브.png", "모히또.png"], "물방울", ["밀짚모자.png", "튜브.png", "모히또.png"]),
    ("가을", ["베레모.png", "단풍핀.png", "코트.png", "책.png"], "낙엽", ["베레모.png", "코트.png", "책.png"]),
    ("겨울", ["털모자.png", "귀마개.png", "목도리.png", "썰매.png"], "눈", ["털모자.png", "목도리.png", "썰매.png"]),
    ("크리스마스", ["산타모자.png", "루돌프뿔.png", "선물상자.png", "목도리.png"], "눈", ["산타모자.png", "선물상자.png"]),
]
EFFECTS = {"벚꽃잎": dict(dir="down", n=7, speed=(0.5, 1.0)), "물방울": dict(dir="up", n=6, speed=(0.4, 0.9)),
           "낙엽": dict(dir="down", n=6, speed=(0.6, 1.1)), "눈": dict(dir="down", n=10, speed=(0.35, 0.8))}
AUTO_MODES = [("off", "끄기"), ("xmas", "크리스마스만 (12/1~25)"), ("season", "계절마다 (봄·여름·가을·겨울·크리스마스)")]


def load_state():
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def save_state(d):
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=1)
    except Exception as ex:
        log("state: %s" % ex)


def update_settings(changes):
    """Change KEY=value lines in settings.ini, keeping the comments."""
    path = os.path.join(DIR, "settings.ini")
    try:
        with open(path, encoding="utf-8-sig") as f:
            lines = f.read().splitlines()
    except FileNotFoundError:
        lines = []
    done = set()
    for i, raw in enumerate(lines):
        t = raw.strip()
        if t and t[0] not in "#;" and "=" in t:
            k = t.split("=", 1)[0].strip().upper()
            if k in changes:
                lines[i] = "%s=%s" % (k, changes[k])
                done.add(k)
    for k, v in changes.items():
        if k not in done:
            lines.append("%s=%s" % (k, v))
    with open(path, "w", encoding="utf-8-sig", newline="\r\n") as f:
        f.write("\n".join(lines) + "\n")


CAL_HELP = ("구글 캘린더 주소 찾는 방법\n\n"
            "1. PC에서 calendar.google.com 접속\n"
            "2. 오른쪽 위 톱니바퀴 → 설정\n"
            "3. 왼쪽 '내 캘린더의 설정'에서 내 이름 클릭\n"
            "4. 맨 아래 '캘린더 통합' → 'iCal 형식의 비공개 주소' 복사\n\n"
            "✔ …/private-…/basic.ics 처럼 private 이 들어간 주소예요.\n"
            "✖ …/public/basic.ics (공개 주소), …/calendar/u/0/r (웹페이지 주소)는 안 돼요.\n\n"
            "※ 이 주소는 비밀번호와 같아요. 다른 사람에게 보내지 마세요.\n\n"
            "지금 구글 캘린더 설정 페이지를 열까요?")


def fetch_ics(url):
    """Download one iCal feed. Raises ValueError('NOT_ICAL'/'PUBLIC_URL') for the usual wrong addresses."""
    if url.lower().startswith("webcal://"):
        url = "https://" + url[9:]
    req = urllib.request.Request(url, headers={"User-Agent": "CharacterWidget/1.0", "Cache-Control": "no-cache"})
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            data = resp.read().decode("utf-8", "replace")
    except Exception as ex:
        if "/public/" in url and getattr(ex, "code", None) in (403, 404):
            raise ValueError("PUBLIC_URL")
        raise
    if "BEGIN:VCALENDAR" not in data:
        raise ValueError("NOT_ICAL")
    return data


def explain_cal_error(err):
    if err == "NOT_ICAL":
        return "넣은 주소가 캘린더 '웹페이지' 주소예요.\n'iCal 형식의 비공개 주소'를 넣어 주세요."
    if err == "PUBLIC_URL":
        return "넣은 주소가 '공개 주소'예요.\n맨 아래 'iCal 형식의 비공개 주소'를 넣어 주세요."
    return "캘린더를 못 불러왔어요. 인터넷 연결이나 주소를 확인해 주세요.\n(%s)" % err


def greeting_line():
    h = datetime.now().hour
    if 5 <= h < 11:
        opts = ["좋은 아침이야! 오늘도 화이팅 ♪", "일어났어? 오늘 하루도 잘 부탁해!"]
    elif 11 <= h < 14:
        opts = ["점심은 맛있게 먹었어?", "밥 꼭 챙겨 먹고 하자!"]
    elif 14 <= h < 18:
        opts = ["오후도 힘내자! 잠깐 스트레칭 어때?", "물 한 잔 마시고 하자 ♪"]
    elif 18 <= h < 23:
        opts = ["오늘 하루도 수고했어!", "저녁은 먹었어? 푹 쉬어 ♪"]
    else:
        opts = ["늦었는데 아직 안 자? 너무 무리하지 마!"]
    return random.choice(opts)


TOUR = [
    "안녕! 나는 {name}{iya}.\n오늘부터 바탕화면에서 같이 지낼게!\n사용법을 간단히 알려줄게.",
    "나를 한 번 클릭하면 메모가 열려.\n할 일이나 생각난 걸 적어둬!",
    "나를 꾹 누른 채로 끌면\n원하는 곳으로 옮길 수 있어.\n자리는 내가 기억해둘게!",
    "나를 오른쪽 클릭하면 메뉴가 나와.\n꾸미기 · 캐릭터 바꾸기 · 설정이\n다 거기 있어!",
    "꾸미기에서 봄 · 여름 · 가을 · 겨울\n테마 옷을 입혀줄 수 있어.\n내 그림으로 캐릭터를 바꿀 수도 있고!",
    "설정에서 구글 캘린더를 연결하면\n오늘 일정이랑 일정 10분 전에\n내가 통통 뛰면서 알려줄게!",
    "준비 끝! 앞으로 잘 부탁해 ♪\n사용법은 메뉴 → 사용법 보기에서\n언제든 다시 볼 수 있어.",
]


def ui_icon(name, cache={}):
    if name not in cache:
        try:
            cache[name] = tk.PhotoImage(file=os.path.join(UI_DIR, name + ".png"))
        except Exception:
            cache[name] = None
    return cache[name]


def theme_by_name(name):
    for t in THEMES:
        if t[0] == name:
            return t
    return None


def list_accessories():
    try:
        return sorted((n for n in os.listdir(ACC_DIR) if n.lower().endswith(IMG_EXT)), key=str.lower)
    except FileNotFoundError:
        return []


def custom_accessories():
    return [n for n in list_accessories() if n not in ACC_INFO]


def acc_info(item, decor):
    if item in ACC_INFO:
        return ACC_INFO[item]
    slot = (decor.get("_custom") or {}).get(item, "head")
    d = dict(SLOT_DEFAULT.get(slot, SLOT_DEFAULT["head"]))
    d["slot"] = slot
    return d


def load_decor():
    try:
        with open(DECOR_FILE, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def save_decor(d):
    try:
        with open(DECOR_FILE, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=1)
    except Exception as ex:
        log("decor save: %s" % ex)


def default_place():
    return dict(dx=0, dy=0, scale=1.0, angle=0)


def auto_mode(decor):
    m = decor.get("_auto")
    if m in ("off", "xmas", "season"):
        return m
    return "xmas" if decor.get("_season", True) else "off"


def season_theme(today=None):
    t = today or date.today()
    if t.month == 12 and t.day <= 25:
        return "크리스마스"
    return {3: "봄 · 벚꽃", 4: "봄 · 벚꽃", 5: "봄 · 벚꽃", 6: "여름 · 바다", 7: "여름 · 바다", 8: "여름 · 바다",
            9: "가을", 10: "가을", 11: "가을"}.get(t.month, "겨울")


def entry_items(decor, key):
    """-> (items {slot: file}, effect, places) for a character (also reads the old one-item format)."""
    e = decor.get(key) or {}
    items = dict(e.get("items") or {})
    if e.get("item") and not items:
        items[acc_info(e["item"], decor)["slot"]] = e["item"]
    return items, e.get("effect"), dict(e.get("places") or {})


def build_dec(items, effect, places, decor):
    layers = []
    for slot in SLOTS:
        it = items.get(slot)
        if it and os.path.exists(os.path.join(ACC_DIR, it)):
            d = dict(default_place(), **(places.get(it) or {}))
            d.update(item=it, **{k: v for k, v in acc_info(it, decor).items()})
            layers.append(d)
    effect = effect if effect in EFFECTS else None
    if not layers and not effect:
        return None
    return dict(layers=layers, effect=effect)


def active_decor(key, decor, today=None):
    """What the character wears right now: its own decoration, or the automatic seasonal one."""
    items, effect, places = entry_items(decor, key)
    items = {s: i for s, i in items.items() if i}
    if not items and not effect:
        mode = auto_mode(decor)
        theme = None
        if mode == "season":
            theme = theme_by_name(season_theme(today))
        elif mode == "xmas" and season_theme(today) == "크리스마스":
            theme = theme_by_name("크리스마스")
        if theme:
            items = {acc_info(i, decor)["slot"]: i for i in theme[3]}
            effect = theme[2]
    return build_dec(items, effect, places, decor)


def decor_sig(dec):
    if not dec or not dec.get("layers"):
        return "plain"
    import hashlib
    stamps = []
    for l in dec["layers"]:
        try:
            st = os.stat(os.path.join(ACC_DIR, l["item"]))
            stamps.append("%d_%d" % (int(st.st_mtime), st.st_size))
        except Exception:
            pass
    raw = json.dumps(dec["layers"], sort_keys=True, ensure_ascii=False) + "|".join(stamps)
    return hashlib.md5(raw.encode("utf-8")).hexdigest()[:8]


def fit(img, max_size):
    w, h = img.width(), img.height()
    big = max(w, h)
    if big > max_size:
        f = -(-big // max_size)          # ceil
        return img.subsample(f, f)
    if big * 2 <= max_size and big < 90:
        return img.zoom(2, 2)
    return img


def target_dims(w, h, size):
    """Same height as Usagi (size px); very wide pictures are limited by width instead."""
    max_w = int(size * 1.25)
    th = size
    tw = max(1, int(round(w * size / float(h))))
    if tw > max_w:
        tw = max_w
        th = max(1, int(round(h * max_w / float(w))))
    return tw, th


def prefit(img, tw, th):
    """Cheap integer shrink that still leaves >= 2x the target for smooth averaging."""
    f = max(1, min(img.width() // (2 * tw), img.height() // (2 * th)))
    return img.subsample(f, f) if f > 1 else img


def resample(src, sw, sh, tw, th):
    """Area-average resize of '#rrggbb' rows to exactly tw x th (KEY = transparent)."""
    if (sw, sh) == (tw, th):
        return src
    xr = []
    for tx in range(tw):
        x0 = int(tx * sw / float(tw))
        x1 = max(x0 + 1, min(sw, int(math.ceil((tx + 1) * sw / float(tw)))))
        xr.append(range(x0, x1))
    out = []
    for ty in range(th):
        y0 = int(ty * sh / float(th))
        y1 = max(y0 + 1, min(sh, int(math.ceil((ty + 1) * sh / float(th)))))
        rows = src[y0:y1]
        row = []
        for xs in xr:
            r = g = b = n = k = 0
            for srow in rows:
                for xx in xs:
                    c = srow[xx]
                    if c == KEY:
                        k += 1
                    else:
                        cr, cg, cb = _rgb(c)
                        r += cr
                        g += cg
                        b += cb
                        n += 1
            if n == 0 or k > n:
                row.append(KEY)
            else:
                c = "#%02x%02x%02x" % (r // n, g // n, b // n)
                row.append("#020202" if c == KEY else c)
        out.append(row)
    return out


def sized_photo(img, size, bg=False):
    """PhotoImage resized to the standard character size (optionally background removed)."""
    tw, th = target_dims(img.width(), img.height(), size)
    img = prefit(img, tw, th)
    src = _pixel_rows(img)
    if bg:
        try:
            src, _ = remove_background(src)
        except Exception as ex:
            log("bg remove: %s" % ex)
    src = resample(src, img.width(), img.height(), tw, th)
    out = tk.PhotoImage(width=tw, height=th)
    out.put(" ".join("{" + " ".join(r) + "}" for r in src))
    return out, src


def image_frames(path, max_size, dec=None):
    """Frames of an animated GIF, each resized to the standard character size."""
    frames = []
    bb = None
    if path.lower().endswith(".gif"):
        i = 0
        while i < 120:
            try:
                fr = tk.PhotoImage(file=path, format="gif -index %d" % i)
            except tk.TclError:
                break
            try:
                img, src = sized_photo(fr, max_size)
                if dec:
                    if bb is None:
                        bb = bbox_rows(src)
                    rows, w, h = wear(src, img.width(), img.height(), dec, bb)
                    img = rows_photo(rows, w, h)
                frames.append(img)
            except Exception as ex:
                log("gif frame %d: %s" % (i, ex))
                frames.append(fit(fr, max_size))
            i += 1
    if not frames:
        frames = [sized_photo(tk.PhotoImage(file=path), max_size)[0]]
    return frames


def builtin_frames(prefix):
    folder = os.path.join(DIR, "frames")
    try:
        names = sorted(n for n in os.listdir(folder) if n.startswith(prefix) and n.endswith(".png"))
    except FileNotFoundError:
        return []
    return [tk.PhotoImage(file=os.path.join(folder, n)) for n in names]


def list_characters():
    keys = []
    if os.path.isdir(os.path.join(DIR, "frames")):
        keys.append(BUILTIN)
    if os.path.isdir(CHAR_DIR):
        keys += sorted((n for n in os.listdir(CHAR_DIR) if n.lower().endswith(IMG_EXT)), key=str.lower)
    return keys


NAMES_FILE = os.path.join(DIR, "names.json")
_NAMES = {}


def load_names():
    global _NAMES
    try:
        with open(NAMES_FILE, encoding="utf-8") as f:
            d = json.load(f)
        _NAMES = {k: str(v) for k, v in d.items() if v} if isinstance(d, dict) else {}
    except Exception:
        _NAMES = {}
    return _NAMES


def set_name(key, name):
    name = (name or "").strip()[:20]
    if name:
        _NAMES[key] = name
    else:
        _NAMES.pop(key, None)
    try:
        with open(NAMES_FILE, "w", encoding="utf-8") as f:
            json.dump(_NAMES, f, ensure_ascii=False, indent=1)
    except Exception as ex:
        log("names: %s" % ex)


def default_name(key):
    return BUILTIN_NAME if key == BUILTIN else os.path.splitext(key)[0]


def char_name(key):
    return _NAMES.get(key) or default_name(key)


def josa(word, with_final, without_final):
    """Korean particle: '이야/야', '이에요/예요' depending on the last syllable."""
    if word:
        ch = word[-1]
        if "가" <= ch <= "힣":
            return with_final if (ord(ch) - 0xAC00) % 28 else without_final
    return without_final


# ---------- automatic animation for still images (no extra libraries)
ANIM_DIR = os.path.join(CHAR_DIR, ".anim")
ANIM_VERSION = "4"
IDLE_SPEC = [(1 + 0.025 * math.sin(2 * math.pi * i / 20), 1 - 0.025 * math.sin(2 * math.pi * i / 20),
              0, 2.5 * math.sin(2 * math.pi * i / 20)) for i in range(20)]
HOP_SPEC = [(1.10, 0.88, 0, 0), (1.04, 0.96, 6, 0), (0.95, 1.06, 18, 0), (0.96, 1.05, 28, 0),
            (0.98, 1.02, 33, 0), (1, 1, 34, 0), (0.98, 1.02, 30, 0), (0.96, 1.05, 20, 0),
            (0.97, 1.04, 8, 0), (1.10, 0.88, 0, 0), (1.04, 0.95, 0, 0), (1, 1, 0, 0)]


def source_path(key):
    if key == BUILTIN:
        return os.path.join(DIR, "frames", "base.png")
    return os.path.join(CHAR_DIR, key)


def _anim_folder(key, max_size, bg=True, dec=None):
    st = os.stat(source_path(key))
    safe = re.sub(r"[^0-9A-Za-z가-힣_-]", "_", os.path.splitext(key)[0])[:40]
    return os.path.join(ANIM_DIR, "%s_%d_%d_%d_%s_%s_v%s" % (safe, int(st.st_mtime), st.st_size, max_size,
                                                           "bg" if bg else "raw", decor_sig(dec), ANIM_VERSION))


def anim_ready(key, max_size, bg=True, dec=None):
    try:
        d = _anim_folder(key, max_size, bg, dec)
        return os.path.exists(os.path.join(d, "hop_%02d.png" % (len(HOP_SPEC) - 1)))
    except Exception:
        return False


def _pixel_rows(img):
    """Rows of '#rrggbb' strings; transparent pixels become KEY (shown as see-through)."""
    raw = img.tk.call(str(img), "data", "-background", KEY)
    rows = img.tk.splitlist(raw) if isinstance(raw, str) else raw
    return [list(img.tk.splitlist(r)) if isinstance(r, str) else list(r) for r in rows]


def _rgb(c, cache={}):
    v = cache.get(c)
    if v is None:
        try:
            v = (int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16))
        except Exception:
            v = (0, 0, 0)
        cache[c] = v
    return v


def remove_background(src, tol=20):
    """Make the plain background around a character transparent.

    Flood-fills from the image border through pixels very close to the border's
    main colour(s) - handles plain backgrounds and fake 'checkerboard transparency'.
    Uses a strict per-channel match so light characters (cream, pastel) are kept,
    and pixels enclosed by the character (e.g. a white face) are never touched.
    Returns (rows, changed)."""
    h, w = len(src), len(src[0]) if src else 0
    if h < 3 or w < 3:
        return src, False
    border = [(0, x) for x in range(w)] + [(h - 1, x) for x in range(w)] + \
             [(y, 0) for y in range(1, h - 1)] + [(y, w - 1) for y in range(1, h - 1)]
    cols = [src[y][x] for y, x in border]
    if sum(1 for c in cols if c == KEY) > len(cols) * 0.3:
        return src, False                        # already has a transparent background
    clusters = []                                # [sum_r, sum_g, sum_b, count, first_rgb]
    for c in cols:
        r, g, b = _rgb(c)
        for cl in clusters:
            R, G, B = cl[4]
            if abs(r - R) <= 12 and abs(g - G) <= 12 and abs(b - B) <= 12:
                cl[0] += r
                cl[1] += g
                cl[2] += b
                cl[3] += 1
                break
        else:
            if len(clusters) < 64:
                clusters.append([r, g, b, 1, (r, g, b)])
    clusters.sort(key=lambda cl: -cl[3])
    seeds, covered = [], 0
    for cl in clusters[:4]:
        if covered >= len(cols) * 0.8:
            break
        seeds.append((cl[0] / cl[3], cl[1] / cl[3], cl[2] / cl[3]))
        covered += cl[3]
    if covered < len(cols) * 0.6:
        return src, False                        # busy border (photo/scene) - leave it

    def near(c, t):
        r, g, b = _rgb(c)
        for a, b_, c_ in seeds:
            if abs(r - a) <= t and abs(g - b_) <= t and abs(b - c_) <= t:
                return True
        return False

    bgmask = [[False] * w for _ in range(h)]
    stack = []
    for y, x in border:
        if not bgmask[y][x] and near(src[y][x], tol):
            bgmask[y][x] = True
            stack.append((y, x))
    while stack:
        y, x = stack.pop()
        for ny, nx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
            if 0 <= ny < h and 0 <= nx < w and not bgmask[ny][nx] and near(src[ny][nx], tol):
                bgmask[ny][nx] = True
                stack.append((ny, nx))
    # one ring of light anti-aliasing halo next to the background
    halo = []
    for y in range(h):
        for x in range(w):
            if not bgmask[y][x] and near(src[y][x], tol + 14):
                if (y > 0 and bgmask[y - 1][x]) or (y < h - 1 and bgmask[y + 1][x]) or \
                   (x > 0 and bgmask[y][x - 1]) or (x < w - 1 and bgmask[y][x + 1]):
                    halo.append((y, x))
    for y, x in halo:
        bgmask[y][x] = True
    removed = sum(sum(1 for v in row if v) for row in bgmask)
    if removed == 0 or removed > h * w * 0.92:   # nothing found, or the guess ate everything
        return src, False
    out = []
    for y in range(h):
        mrow, srow = bgmask[y], src[y]
        out.append([KEY if mrow[x] else srow[x] for x in range(w)])
    return out, True


def bbox_rows(src):
    top = bottom = None
    left, right = 10 ** 9, -1
    for y, r in enumerate(src):
        xs = [x for x, c in enumerate(r) if c != KEY]
        if xs:
            if top is None:
                top = y
            bottom = y
            left, right = min(left, xs[0]), max(right, xs[-1])
    if top is None:
        return None
    return left, top, right + 1, bottom + 1


def rotate_rows(rows, w, h, angle):
    a = math.radians(angle)
    ca, sa = math.cos(a), math.sin(a)
    nw = int(abs(w * ca) + abs(h * sa)) + 2
    nh = int(abs(w * sa) + abs(h * ca)) + 2
    cx, cy, ncx, ncy = w / 2.0, h / 2.0, nw / 2.0, nh / 2.0
    out = []
    for y in range(nh):
        dy = y - ncy
        row = []
        for x in range(nw):
            dx = x - ncx
            sx = int(round(dx * ca + dy * sa + cx))
            sy = int(round(-dx * sa + dy * ca + cy))
            row.append(rows[sy][sx] if 0 <= sx < w and 0 <= sy < h else KEY)
        out.append(row)
    return out, nw, nh


_ACC_CACHE = {}


def accessory_rows(item, width):
    path = os.path.join(ACC_DIR, item)
    try:
        stamp = os.path.getmtime(path)
    except OSError:
        stamp = 0
    k = (item, width, stamp)
    if k not in _ACC_CACHE:
        fmt = "gif -index 0" if item.lower().endswith(".gif") else None
        img = tk.PhotoImage(file=path, format=fmt) if fmt else tk.PhotoImage(file=path)
        h = max(1, int(round(img.height() * width / float(img.width()))))
        img = prefit(img, width, h)
        if len(_ACC_CACHE) > 40:
            _ACC_CACHE.clear()
        _ACC_CACHE[k] = (resample(_pixel_rows(img), img.width(), img.height(), width, h), width, h)
    return _ACC_CACHE[k]


def _layer_box(bb, layer):
    bx0, by0, bx1, by1 = bb
    bw, bh = bx1 - bx0, by1 - by0
    aw = max(6, int(bw * layer.get("w", 0.6) * float(layer.get("scale", 1.0))))
    arows, aw, ah = accessory_rows(layer["item"], aw)
    ang = float(layer.get("angle", 0))
    if abs(ang) > 0.5:
        arows, aw, ah = rotate_rows(arows, aw, ah, ang)
    cx = bx0 + layer.get("x", 0.5) * bw + float(layer.get("dx", 0))
    yy = by0 + layer.get("y", 0.12) * bh + float(layer.get("dy", 0))
    slot = layer.get("slot", "head")
    if slot in ("head", "pin"):
        ay = yy - ah                     # sits on top, its bottom edge at yy
    elif slot == "ground":
        ay = yy                          # starts at yy and goes down
    else:
        ay = yy - ah / 2.0               # centred on yy (body / side)
    return arows, aw, ah, int(round(cx - aw / 2.0)), int(round(ay))


def wear(src, sw, sh, dec, bb=None):
    """Put every accessory layer on the character -> (rows, w, h)."""
    if not dec or not dec.get("layers"):
        return src, sw, sh
    bb = bb or bbox_rows(src)
    if not bb:
        return src, sw, sh
    placed = [_layer_box(bb, l) for l in dec["layers"]]
    left = min([0] + [p[3] for p in placed])
    right = max([sw] + [p[3] + p[1] for p in placed])
    top = min([0] + [p[4] for p in placed])
    bottom = max([sh] + [p[4] + p[2] for p in placed])
    side = max(-left, right - sw)
    nw, nh = sw + 2 * side, (sh - top) + (bottom - sh)
    out = [[KEY] * nw for _ in range(-top)]
    for r in src:
        out.append([KEY] * side + list(r) + [KEY] * side)
    out += [[KEY] * nw for _ in range(bottom - sh)]
    for arows, aw, ah, ax, ay in placed:
        ox, oy = ax + side, ay - top
        for y in range(ah):
            orow, arow = out[oy + y], arows[y]
            for x in range(aw):
                c = arow[x]
                if c != KEY:
                    orow[ox + x] = c
    return out, nw, nh


def rows_photo(rows, w, h, bg=None):
    data = " ".join("{" + " ".join(r) + "}" for r in rows)
    if bg:
        data = data.replace(KEY, bg)
    img = tk.PhotoImage(width=w, height=h)
    img.put(data)
    return img


def _render(src, sw, sh, cw, ch, sx, sy, dy, lean):
    """Squash/stretch + lean, nearest-neighbour, feet anchored at the bottom centre."""
    px, py = cw / 2.0, ch - 4 - dy
    xmap = [int((x - px) / sx + sw / 2.0) for x in range(cw)]
    blank = "{" + " ".join([KEY] * cw) + "}"
    tan = math.tan(math.radians(lean))
    rows = []
    for y in range(ch):
        iy = int((y - py) / sy + sh)
        if not 0 <= iy < sh:
            rows.append(blank)
            continue
        srow = src[iy]
        shift = int(round((py - y) * tan))
        row = [srow[i] if 0 <= i < sw else KEY for i in xmap]
        if shift > 0:
            row = [KEY] * shift + row[:-shift]
        elif shift < 0:
            row = row[-shift:] + [KEY] * (-shift)
        rows.append("{" + " ".join(row) + "}")
    return " ".join(rows)


def still_source(key, max_size, bg=True, dec=None):
    path = source_path(key)
    fmt = "gif -index 0" if key.lower().endswith(".gif") else None
    base = tk.PhotoImage(file=path, format=fmt) if fmt else tk.PhotoImage(file=path)
    img, src = sized_photo(base, max_size, bg and key != BUILTIN)
    sw, sh = img.width(), img.height()
    if dec:
        try:
            src, sw, sh = wear(src, sw, sh, dec)
        except Exception as ex:
            log("decor: %s" % ex)
    return src, sw, sh


def plain_frame(key, max_size, bg=True, dec=None):
    """Single still frame (background removed) for ANIMATE=off."""
    src, sw, sh = still_source(key, max_size, bg, dec)
    return rows_photo(src, sw, sh)


def animated_frames(key, max_size, bg=True, dec=None):
    """Make (or load cached) idle/hop frames for a still image."""
    folder = _anim_folder(key, max_size, bg, dec)
    names_i = ["idle_%02d.png" % i for i in range(len(IDLE_SPEC))]
    names_h = ["hop_%02d.png" % i for i in range(len(HOP_SPEC))]
    if anim_ready(key, max_size, bg, dec):
        try:
            return ([tk.PhotoImage(file=os.path.join(folder, n)) for n in names_i],
                    [tk.PhotoImage(file=os.path.join(folder, n)) for n in names_h])
        except Exception:
            pass
    src, sw, sh = still_source(key, max_size, bg, dec)
    cw, ch = int(sw * 1.12) + 10, int(sh * 1.07) + 44
    out = []
    for spec in IDLE_SPEC + HOP_SPEC:
        img = tk.PhotoImage(width=cw, height=ch)
        img.put(_render(src, sw, sh, cw, ch, *spec))
        out.append(img)
    idle, hop = out[:len(IDLE_SPEC)], out[len(IDLE_SPEC):]
    try:                                         # cache so next time is instant
        os.makedirs(folder, exist_ok=True)
        for img, n in zip(idle + hop, names_i + names_h):
            img.write(os.path.join(folder, n), format="png")
    except Exception as ex:
        log("anim cache: %s" % ex)
    return idle, hop


def is_still(key):
    if key == BUILTIN or not key.lower().endswith(".gif"):
        return True
    try:
        tk.PhotoImage(file=os.path.join(CHAR_DIR, key), format="gif -index 1")
        return False                             # has a 2nd frame -> already animated
    except tk.TclError:
        return True


def load_char(key, max_size, animate=True, bg=True, dec=None):
    """-> dict(idle=[frames], hop=[frames] or None, bob=bool)"""
    if key == BUILTIN and dec and os.path.exists(source_path(BUILTIN)):
        if animate:
            idle, hop = animated_frames(key, max_size, False, dec)
            return dict(key=key, idle=idle, hop=hop, bob=False)
        return dict(key=key, idle=[plain_frame(key, max_size, False, dec)], hop=None, bob=True)
    if key == BUILTIN:
        idle, hop = builtin_frames("idle_"), builtin_frames("hop_")
        if not idle:
            raise FileNotFoundError("frames 폴더의 기본 캐릭터 그림을 찾을 수 없어요.")
        return dict(key=key, idle=idle, hop=hop or None, bob=False)
    if is_still(key):
        if animate:
            idle, hop = animated_frames(key, max_size, bg, dec)
            return dict(key=key, idle=idle, hop=hop, bob=False)
        return dict(key=key, idle=[plain_frame(key, max_size, bg, dec)], hop=None, bob=True)
    frames = image_frames(os.path.join(CHAR_DIR, key), max_size, dec)
    return dict(key=key, idle=frames, hop=None, bob=True)


def read_choice():
    try:
        with open(CHOICE_FILE, encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return ""


def write_choice(key):
    try:
        with open(CHOICE_FILE, "w", encoding="utf-8") as f:
            f.write(key)
    except Exception as ex:
        log("choice: %s" % ex)


def thumbnail(key, size=96):
    try:
        if key == BUILTIN:
            img = tk.PhotoImage(file=os.path.join(DIR, "frames", "idle_00.png"))
        else:
            path = os.path.join(CHAR_DIR, key)
            fmt = "gif -index 0" if key.lower().endswith(".gif") else None
            img = tk.PhotoImage(file=path, format=fmt) if fmt else tk.PhotoImage(file=path)
        big = max(img.width(), img.height())
        if big > size:
            f = -(-big // size)
            img = img.subsample(f, f)
        return img
    except Exception:
        return None


class Picker:
    """'캐릭터 변경' window: pick a character, or add one with +."""
    BG = "#fffaf0"
    SEL = "#ffd27a"

    def __init__(self, app):
        self.app = app
        top = self.top = tk.Toplevel(app.root)
        top.title("캐릭터 변경")
        top.attributes("-topmost", True)
        top.config(bg=self.BG)
        top.resizable(False, False)
        tk.Label(top, text="캐릭터를 눌러서 바꾸세요  ·  + 로 그림 추가  ·  더블클릭/우클릭으로 이름 바꾸기",
                 bg=self.BG, fg="#6b5545", font=("Malgun Gothic", 9)).pack(padx=14, pady=(12, 4))
        self.grid = tk.Frame(top, bg=self.BG)
        self.grid.pack(padx=10, pady=(4, 14))
        self.thumbs = []
        self.alive = True
        top.protocol("WM_DELETE_WINDOW", self.close)
        self.build()
        top.update_idletasks()
        r = app.root
        x = r.winfo_x() - top.winfo_width() - 10
        wa = work_area()
        if wa and x < wa[0]:
            x = r.winfo_x() + r.winfo_width() + 10
        y = r.winfo_y() + r.winfo_height() - top.winfo_height()
        if wa:
            y = max(wa[1], min(y, wa[3] - top.winfo_height()))
        top.geometry("+%d+%d" % (x, y))
        top.lift()
        top.focus_force()

    def build(self):
        for w in self.grid.winfo_children():
            w.destroy()
        self.thumbs = []
        keys = list_characters()
        cols = 4
        for i, key in enumerate(keys + ["+"]):
            r_, c_ = divmod(i, cols)
            selected = key == self.app.char_key
            cell = tk.Frame(self.grid, bg=self.SEL if selected else self.BG, cursor="hand2",
                            highlightthickness=1, highlightbackground="#e6d6bf")
            cell.grid(row=r_, column=c_, padx=5, pady=5)
            inner = tk.Frame(cell, bg="white", width=110, height=124)
            inner.pack(padx=3, pady=3)
            inner.pack_propagate(False)
            if key == "+":
                lab = tk.Label(inner, text="+", font=("Malgun Gothic", 34), fg="#c9a87c", bg="white")
                lab.pack(expand=True)
                cap = tk.Label(inner, text="그림 추가", font=("Malgun Gothic", 9), fg="#8a7360", bg="white")
                cap.pack(pady=(0, 6))
                widgets = (cell, inner, lab, cap)
                for w in widgets:
                    w.bind("<Button-1>", lambda e: self.add())
                continue
            img = thumbnail(key)
            self.thumbs.append(img)
            lab = tk.Label(inner, image=img, bg="white") if img else tk.Label(inner, text="(못 읽음)", bg="white")
            lab.pack(expand=True)
            name = char_name(key)
            cap = tk.Label(inner, text=(name if len(name) <= 9 else name[:8] + "…") + (" ✔" if selected else ""),
                           font=("Malgun Gothic", 9, "bold" if selected else "normal"), fg="#5a4636", bg="white")
            cap.pack(pady=(0, 6))
            for w in (cell, inner, lab, cap):
                w.bind("<Button-1>", lambda e, k=key: self.pick(k))
                w.bind("<Button-3>", lambda e, k=key: self.context(e, k))
                w.bind("<Double-Button-1>", lambda e, k=key: self.rename(k))

    def pick(self, key):
        if key == self.app.char_key:            # already chosen: keep the grid so double-click can rename
            return
        if self.app.set_character(key):
            self.build()

    def add(self):
        paths = filedialog.askopenfilenames(
            parent=self.top, title="캐릭터 그림 고르기 (배경이 투명한 PNG 추천)",
            filetypes=[("그림 파일 (PNG, GIF)", "*.png *.gif"), ("PNG", "*.png"), ("GIF", "*.gif")])
        if not paths:
            return
        os.makedirs(CHAR_DIR, exist_ok=True)
        added, bad = None, []
        for p in paths:
            base = os.path.basename(p)
            stem, ext = os.path.splitext(base)
            ext = ext.lower()
            if ext not in IMG_EXT:
                bad.append(base)
                continue
            stem = re.sub(r'[\\/:*?"<>|]', "_", stem).strip() or "character"
            dest, n = os.path.join(CHAR_DIR, stem + ext), 2
            while os.path.exists(dest):
                dest = os.path.join(CHAR_DIR, "%s (%d)%s" % (stem, n, ext))
                n += 1
            try:
                shutil.copyfile(p, dest)
                tk.PhotoImage(file=dest)          # make sure Tk can read it
                added = os.path.basename(dest)
            except Exception as ex:
                log("add character %s: %s" % (base, ex))
                bad.append(base)
                try:
                    os.remove(dest)
                except Exception:
                    pass
        if bad:
            messagebox.showwarning("캐릭터 변경",
                                   "이 그림은 추가하지 못했어요:\n" + "\n".join(bad) +
                                   "\n\nPNG 또는 GIF 그림만 쓸 수 있어요.\n"
                                   "JPG 는 그림판에서 열어 '다른 이름으로 저장 → PNG' 로 바꿔 주세요.",
                                   parent=self.top)
        if added:
            self.build()
            self.ask_name(added, "이름 짓기",
                          "새 캐릭터의 이름을 지어 주세요!\n(비워두면 그림 파일 이름을 써요)")
            self.app.set_character(added)
        self.build()

    def ask_name(self, key, title="이름 짓기", msg=None):
        cur = char_name(key)
        name = simpledialog.askstring(
            title, msg or "'%s'의 새 이름을 적어 주세요.\n(비워두면 원래 이름으로 돌아가요)" % cur,
            initialvalue=cur, parent=self.top)
        if name is None:
            return False
        set_name(key, name)
        if key == self.app.char_key:
            self.app.update_name(announce=True)
        return True

    def rename(self, key):
        if self.ask_name(key, "이름 바꾸기"):
            self.build()

    def context(self, e, key):
        m = tk.Menu(self.top, tearoff=0, font=("Malgun Gothic", 10))
        m.add_command(label="이름 바꾸기", command=lambda: self.rename(key))
        if key != BUILTIN:
            m.add_command(label="'%s' 삭제" % char_name(key), command=lambda: self.delete(key))
        try:
            m.tk_popup(e.x_root, e.y_root)
        finally:
            m.grab_release()

    def delete(self, key):
        if not messagebox.askyesno("캐릭터 변경", "'%s' 그림을 목록에서 지울까요?" % char_name(key), parent=self.top):
            return
        try:
            os.remove(os.path.join(CHAR_DIR, key))
            if os.path.isdir(ANIM_DIR):
                stem = re.sub(r"[^0-9A-Za-z가-힣_-]", "_", os.path.splitext(key)[0])[:40] + "_"
                for d in os.listdir(ANIM_DIR):
                    if d.startswith(stem):
                        shutil.rmtree(os.path.join(ANIM_DIR, d), ignore_errors=True)
        except Exception as ex:
            messagebox.showerror("캐릭터 변경", "지우지 못했어요: %s" % ex, parent=self.top)
            return
        set_name(key, "")
        if key == self.app.char_key:
            keys = list_characters()
            if keys:
                self.app.set_character(keys[0])
            else:
                self.app.show_placeholder()
        self.build()

    def close(self):
        self.alive = False
        self.top.destroy()


class DecorWindow:
    """'꾸미기' window: themed accessories for the current character."""
    BG = "#fffaf0"
    PV = "#f3ece0"
    SEL = "#ffd27a"
    ACT = "#f2a65a"
    MINE = "내 소품"

    def __init__(self, app):
        self.app = app
        self.key = app.char_key
        self.work = copy.deepcopy(app.decor)
        self.size = app.int_cfg("SIZE", MAX_SIZE)
        top = self.top = tk.Toplevel(app.root)
        top.title("꾸미기 - %s" % char_name(self.key))
        top.attributes("-topmost", True)
        top.config(bg=self.BG)
        top.resizable(False, False)
        self.alive = True
        top.protocol("WM_DELETE_WINDOW", self.close)
        if self.key == BUILTIN and not os.path.exists(source_path(BUILTIN)):
            tk.Label(top, text="기본 캐릭터는 꾸미기 준비 파일(frames\\base.png)이 없어서\n꾸밀 수 없어요.",
                     bg=self.BG, font=("Malgun Gothic", 10)).pack(padx=20, pady=20)
            return
        self.base = still_source(self.key, self.size, app.bg_on())
        items, effect, places = entry_items(self.work, self.key)
        e = self.work.setdefault(self.key, {})
        e.pop("item", None)
        e["items"], e["effect"], e["places"] = items, effect, places
        self.active = next((items[s] for s in reversed(SLOTS) if items.get(s)), None)
        self.theme = THEMES[0][0]
        for t in THEMES:
            if any(i in t[1] for i in items.values()):
                self.theme = t[0]
                break
        self.fx_imgs = {}

        # theme tabs
        self.tabs = tk.Frame(top, bg=self.BG)
        self.tabs.pack(fill="x", padx=14, pady=(12, 4))

        body = tk.Frame(top, bg=self.BG)
        body.pack(fill="both", padx=6)
        left = tk.Frame(body, bg=self.BG)
        left.pack(side="left", padx=(8, 6), pady=6, anchor="n")
        self.pv = tk.Canvas(left, width=250, height=280, bg=self.PV, highlightthickness=1,
                            highlightbackground="#e6d6bf", cursor="fleur")
        self.pv.pack()
        tk.Label(left, text="고른 소품을 드래그해서 옮기세요\n(방향키로 1칸씩)", bg=self.BG,
                 fg="#8a7360", font=("Malgun Gothic", 9)).pack(pady=(6, 0))
        self.pv.bind("<ButtonPress-1>", self.on_press)
        self.pv.bind("<B1-Motion>", self.on_drag)
        for k, d in (("<Left>", (-1, 0)), ("<Right>", (1, 0)), ("<Up>", (0, -1)), ("<Down>", (0, 1))):
            top.bind(k, lambda ev, d=d: self.nudge(*d))

        right = tk.Frame(body, bg=self.BG)
        right.pack(side="left", padx=(6, 10), pady=6, anchor="n")
        self.items_title = tk.Label(right, bg=self.BG, fg="#5a4636", font=("Malgun Gothic", 10, "bold"))
        self.items_title.pack(anchor="w")
        self.items_box = tk.Frame(right, bg=self.BG)
        self.items_box.pack(anchor="w", pady=(4, 4))
        self.theme_row = tk.Frame(right, bg=self.BG)
        self.theme_row.pack(anchor="w", pady=(0, 8))

        tk.Label(right, text="착용 중  (눌러서 조절할 소품 고르기)", bg=self.BG, fg="#5a4636",
                 font=("Malgun Gothic", 10, "bold")).pack(anchor="w")
        self.worn = tk.Frame(right, bg=self.BG)
        self.worn.pack(anchor="w", pady=(4, 4), fill="x")
        ctl = tk.Frame(right, bg=self.BG)
        ctl.pack(anchor="w", pady=(2, 10))
        for txt, cmd in (("작게", lambda: self.scale(1 / 1.1)), ("크게", lambda: self.scale(1.1)),
                         ("↺", lambda: self.rotate(-6)), ("↻", lambda: self.rotate(6)),
                         ("처음 위치로", self.reset), ("모두 벗기", self.clear_all)):
            tk.Button(ctl, text=txt, command=cmd, font=("Malgun Gothic", 9), bg="white", relief="groove",
                      padx=6).pack(side="left", padx=2)

        auto = tk.Frame(right, bg=self.BG)
        auto.pack(anchor="w", pady=(0, 2))
        tk.Label(auto, text="자동 꾸미기", bg=self.BG, fg="#5a4636",
                 font=("Malgun Gothic", 10, "bold")).pack(side="left")
        labels = [lab for _, lab in AUTO_MODES]
        cur = dict(AUTO_MODES)[auto_mode(self.work)]
        self.auto_var = tk.StringVar(value=cur)
        om = tk.OptionMenu(auto, self.auto_var, *labels, command=self.on_auto)
        om.config(font=("Malgun Gothic", 9), bg="white", relief="groove", highlightthickness=0)
        om["menu"].config(font=("Malgun Gothic", 9))
        om.pack(side="left", padx=6)
        tk.Label(right, text="꾸미기를 비워둔 캐릭터만 날짜에 맞춰 알아서 꾸며줘요.", bg=self.BG,
                 fg="#8a7360", font=("Malgun Gothic", 8)).pack(anchor="w", pady=(0, 10))

        btns = tk.Frame(right, bg=self.BG)
        btns.pack(anchor="e", fill="x", pady=(0, 6))
        tk.Button(btns, text="닫기", command=self.close, font=("Malgun Gothic", 10), bg="white",
                  relief="groove", padx=12).pack(side="right", padx=(6, 0))
        tk.Button(btns, text="적용", command=self.apply, font=("Malgun Gothic", 10, "bold"), bg=self.SEL,
                  relief="groove", padx=16).pack(side="right")

        self.thumbs = []
        self.build_all()
        top.update_idletasks()
        r = app.root
        x = r.winfo_x() - top.winfo_width() - 10
        wa = work_area()
        if wa and x < wa[0]:
            x = r.winfo_x() + r.winfo_width() + 10
        y = r.winfo_y() + r.winfo_height() - top.winfo_height()
        if wa:
            y = max(wa[1], min(y, wa[3] - top.winfo_height()))
        top.geometry("+%d+%d" % (x, max(0, y)))
        top.lift()
        top.focus_force()

    # ----- data
    def entry(self):
        return self.work[self.key]

    def items(self):
        return self.entry()["items"]

    def place(self, item=None):
        item = item or self.active
        if not item:
            return None
        return self.entry()["places"].setdefault(item, default_place())

    def preview_dec(self):
        e = self.entry()
        return build_dec(e["items"], e.get("effect"), e["places"], self.work)

    # ----- building the ui
    def build_all(self):
        self.build_tabs()
        self.build_items()
        self.build_worn()
        self.redraw()

    def build_tabs(self):
        for w in self.tabs.winfo_children():
            w.destroy()
        for name in [t[0] for t in THEMES] + [self.MINE]:
            sel = name == self.theme
            b = tk.Label(self.tabs, text=name, bg=self.SEL if sel else "white", fg="#5a4636", cursor="hand2",
                         font=("Malgun Gothic", 9, "bold" if sel else "normal"), padx=8, pady=3,
                         highlightthickness=1, highlightbackground="#e6d6bf")
            b.pack(side="left", padx=2)
            b.bind("<Button-1>", lambda e, n=name: self.set_theme(n))

    def set_theme(self, name):
        self.theme = name
        self.build_tabs()
        self.build_items()

    def build_items(self):
        for w in self.items_box.winfo_children() + self.theme_row.winfo_children():
            w.destroy()
        self.thumbs = []
        t = theme_by_name(self.theme)
        if t:
            names = [i for i in t[1] if os.path.exists(os.path.join(ACC_DIR, i))]
            self.items_title.config(text="%s 소품  (누르면 입고, 다시 누르면 벗어요)" % self.theme)
        else:
            names = custom_accessories() + ["+"]
            self.items_title.config(text="내 소품  (+ 로 추가 · 우클릭으로 위치 종류/삭제)")
        worn = set(self.items().values())
        for i, item in enumerate(names):
            on = item in worn
            act = item == self.active
            cell = tk.Frame(self.items_box, bg=self.ACT if act else (self.SEL if on else self.BG), cursor="hand2",
                            highlightthickness=1, highlightbackground="#e6d6bf")
            cell.grid(row=i // 4, column=i % 4, padx=3, pady=3)
            inner = tk.Frame(cell, bg="white", width=70, height=78)
            inner.pack(padx=2, pady=2)
            inner.pack_propagate(False)
            if item == "+":
                lab = tk.Label(inner, text="+", bg="white", fg="#c9a87c", font=("Malgun Gothic", 22))
                cap = tk.Label(inner, text="소품 추가", bg="white", fg="#8a7360", font=("Malgun Gothic", 8))
            else:
                img = thumbnail_file(os.path.join(ACC_DIR, item), 50)
                self.thumbs.append(img)
                lab = tk.Label(inner, image=img, bg="white") if img else tk.Label(inner, text="?", bg="white")
                nm = os.path.splitext(item)[0]
                cap = tk.Label(inner, text=(nm if len(nm) <= 6 else nm[:5] + "…"), bg="white", fg="#5a4636",
                               font=("Malgun Gothic", 8, "bold" if on else "normal"))
            lab.pack(expand=True)
            cap.pack(pady=(0, 3))
            for w in (cell, inner, lab, cap):
                if item == "+":
                    w.bind("<Button-1>", lambda e: self.add())
                else:
                    w.bind("<Button-1>", lambda e, it=item: self.toggle(it))
                    if t is None:
                        w.bind("<Button-3>", lambda e, it=item: self.context(e, it))
        if t and (t[2] or t[3]):
            if t[2]:
                on = self.entry().get("effect") == t[2]
                fx = tk.Label(self.theme_row, text=("✔ " if on else "") + "%s 날리기" % t[2], cursor="hand2",
                              bg=self.SEL if on else "white", fg="#5a4636", font=("Malgun Gothic", 9),
                              padx=8, pady=3, highlightthickness=1, highlightbackground="#e6d6bf")
                fx.pack(side="left", padx=(0, 6))
                fx.bind("<Button-1>", lambda e, n=t[2]: self.toggle_effect(n))
            if t[3]:
                tk.Button(self.theme_row, text="이 테마 한 번에 입히기", command=lambda th=t: self.wear_theme(th),
                          font=("Malgun Gothic", 9, "bold"), bg="white", relief="groove",
                          padx=8).pack(side="left")

    def build_worn(self):
        for w in self.worn.winfo_children():
            w.destroy()
        e = self.entry()
        any_worn = False
        for slot in reversed(SLOTS):
            it = e["items"].get(slot)
            if not it:
                continue
            any_worn = True
            act = it == self.active
            chip = tk.Label(self.worn, text="%s: %s" % (SLOT_NAMES[slot], os.path.splitext(it)[0]),
                            bg=self.ACT if act else "white", fg="#5a4636", cursor="hand2",
                            font=("Malgun Gothic", 9, "bold" if act else "normal"), padx=6, pady=2,
                            highlightthickness=1, highlightbackground="#e6d6bf")
            chip.pack(side="left", padx=2)
            chip.bind("<Button-1>", lambda ev, i=it: self.set_active(i))
        if e.get("effect"):
            any_worn = True
            tk.Label(self.worn, text="효과: %s" % e["effect"], bg="white", fg="#5a4636",
                     font=("Malgun Gothic", 9), padx=6, pady=2, highlightthickness=1,
                     highlightbackground="#e6d6bf").pack(side="left", padx=2)
        if not any_worn:
            tk.Label(self.worn, text="(아직 없어요)", bg=self.BG, fg="#8a7360",
                     font=("Malgun Gothic", 9)).pack(side="left")

    def fx_image(self, name):
        if name not in self.fx_imgs:
            imgs = []
            for n in sorted(os.listdir(FX_DIR)) if os.path.isdir(FX_DIR) else []:
                if n.startswith(name + "_") and n.lower().endswith(".png"):
                    try:
                        imgs.append(tk.PhotoImage(file=os.path.join(FX_DIR, n)))
                    except Exception:
                        pass
            self.fx_imgs[name] = imgs
        return self.fx_imgs[name]

    def redraw(self):
        src, sw, sh = self.base
        dec = self.preview_dec()
        rows, w, h = wear(src, sw, sh, dec) if dec else (src, sw, sh)
        self.pv_img = rows_photo(rows, w, h, self.PV)
        cw, ch = max(250, w + 40), max(280, h + 30)
        self.pv.config(width=cw, height=ch)
        self.pv.delete("all")
        self.pv.create_image(cw // 2, ch - 10, image=self.pv_img, anchor="s")
        if dec and dec.get("effect"):
            imgs = self.fx_image(dec["effect"])
            if imgs:
                import random
                rnd = random.Random(7)
                for i in range(9):
                    self.pv.create_image(rnd.randint(10, cw - 10), rnd.randint(10, ch - 20), image=imgs[i % len(imgs)])

    # ----- actions
    def refresh(self):
        self.build_items()
        self.build_worn()
        self.redraw()

    def toggle(self, item):
        items = self.items()
        slot = acc_info(item, self.work)["slot"]
        if items.get(slot) == item:
            if self.active == item:
                items.pop(slot, None)
                self.active = next((items[s] for s in reversed(SLOTS) if items.get(s)), None)
            else:
                self.active = item
        else:
            items[slot] = item
            self.active = item
        self.refresh()

    def set_active(self, item):
        self.active = item
        self.refresh()

    def toggle_effect(self, name):
        e = self.entry()
        e["effect"] = None if e.get("effect") == name else name
        self.refresh()

    def wear_theme(self, t):
        e = self.entry()
        e["items"] = {acc_info(i, self.work)["slot"]: i for i in t[3]}
        e["effect"] = t[2]
        self.active = t[3][0] if t[3] else None
        self.refresh()

    def clear_all(self):
        e = self.entry()
        e["items"], e["effect"] = {}, None
        self.active = None
        self.refresh()

    def on_press(self, ev):
        self.drag_from = (ev.x, ev.y)

    def on_drag(self, ev):
        p = self.place()
        if not p or not getattr(self, "drag_from", None):
            return
        dx, dy = ev.x - self.drag_from[0], ev.y - self.drag_from[1]
        if abs(dx) + abs(dy) < 2:
            return
        self.drag_from = (ev.x, ev.y)
        p["dx"] = p.get("dx", 0) + dx
        p["dy"] = p.get("dy", 0) + dy
        self.redraw()

    def nudge(self, dx, dy):
        p = self.place()
        if p:
            p["dx"] = p.get("dx", 0) + dx
            p["dy"] = p.get("dy", 0) + dy
            self.redraw()

    def scale(self, f):
        p = self.place()
        if p:
            p["scale"] = max(0.3, min(3.0, round(p.get("scale", 1.0) * f, 3)))
            self.redraw()

    def rotate(self, d):
        p = self.place()
        if p:
            p["angle"] = max(-60, min(60, p.get("angle", 0) + d))
            self.redraw()

    def reset(self):
        if self.active:
            self.entry()["places"][self.active] = default_place()
            self.redraw()

    def on_auto(self, label):
        for code, lab in AUTO_MODES:
            if lab == label:
                self.work["_auto"] = code
        self.work.pop("_season", None)

    def add(self):
        paths = filedialog.askopenfilenames(
            parent=self.top, title="소품 그림 고르기 (배경이 투명한 PNG 추천)",
            filetypes=[("그림 파일 (PNG, GIF)", "*.png *.gif"), ("PNG", "*.png"), ("GIF", "*.gif")])
        if not paths:
            return
        os.makedirs(ACC_DIR, exist_ok=True)
        added = None
        for p in paths:
            base = os.path.basename(p)
            stem, ext = os.path.splitext(base)
            if ext.lower() not in IMG_EXT:
                continue
            stem = re.sub(r'[\\/:*?"<>|]', "_", stem).strip() or "accessory"
            dest, n = os.path.join(ACC_DIR, stem + ext.lower()), 2
            while os.path.exists(dest):
                dest = os.path.join(ACC_DIR, "%s (%d)%s" % (stem, n, ext.lower()))
                n += 1
            try:
                shutil.copyfile(p, dest)
                tk.PhotoImage(file=dest)
                added = os.path.basename(dest)
            except Exception as ex:
                log("add accessory %s: %s" % (base, ex))
                try:
                    os.remove(dest)
                except Exception:
                    pass
        if added:
            self.toggle(added)
        else:
            self.refresh()

    def context(self, ev, item):
        m = tk.Menu(self.top, tearoff=0, font=("Malgun Gothic", 10))
        cur = acc_info(item, self.work)["slot"]
        for slot in ("head", "pin", "body", "side", "ground"):
            m.add_command(label=("✔ " if slot == cur else "   ") + "%s에 두기" % SLOT_NAMES[slot],
                          command=lambda s=slot: self.set_slot(item, s))
        m.add_separator()
        m.add_command(label="'%s' 삭제" % os.path.splitext(item)[0], command=lambda: self.delete(item))
        try:
            m.tk_popup(ev.x_root, ev.y_root)
        finally:
            m.grab_release()

    def set_slot(self, item, slot):
        old = acc_info(item, self.work)["slot"]
        self.work.setdefault("_custom", {})[item] = slot
        items = self.items()
        if items.get(old) == item:
            items.pop(old, None)
            items[slot] = item
        self.refresh()

    def delete(self, item):
        if not messagebox.askyesno("꾸미기", "'%s' 소품을 지울까요?" % os.path.splitext(item)[0], parent=self.top):
            return
        try:
            os.remove(os.path.join(ACC_DIR, item))
        except Exception as ex:
            messagebox.showerror("꾸미기", "지우지 못했어요: %s" % ex, parent=self.top)
            return
        for k, e in self.work.items():
            if isinstance(e, dict) and isinstance(e.get("items"), dict):
                for s in [s for s, i in e["items"].items() if i == item]:
                    e["items"].pop(s, None)
        if self.active == item:
            self.active = None
        self.refresh()

    def apply(self):
        self.app.decor = self.work
        save_decor(self.work)
        self.close()
        self.app.set_character(self.key)

    def close(self):
        self.alive = False
        try:
            self.top.destroy()
        except Exception:
            pass


def thumbnail_file(path, size):
    try:
        fmt = "gif -index 0" if path.lower().endswith(".gif") else None
        img = tk.PhotoImage(file=path, format=fmt) if fmt else tk.PhotoImage(file=path)
        big = max(img.width(), img.height())
        if big > size:
            f = -(-big // size)
            img = img.subsample(f, f)
        return img
    except Exception:
        return None


def round_rect(c, x1, y1, x2, y2, r, **kw):
    pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
           x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
    return c.create_polygon(pts, smooth=True, **kw)


class Bubble:
    def __init__(self, app, text, seconds, buttons=None, footer=None):
        """buttons: [(label, callback, primary)] - a bubble with buttons stays until a button is pressed."""
        self.app = app
        top = self.top = tk.Toplevel(app.root)
        top.overrideredirect(True)
        top.attributes("-topmost", True)
        top.config(bg=KEY)
        top.attributes("-transparentcolor", KEY)
        c = tk.Canvas(top, bg=KEY, highlightthickness=0, bd=0, cursor="hand2")
        tid = c.create_text(18, 13, text=text, anchor="nw", width=280, font=FONT, fill=TEXT)
        x1, y1, x2, y2 = c.bbox(tid)
        w, h = max(x2 + 18, 120), y2 + 15
        made = []
        if buttons:
            bx = 0
            for label, cb, primary in buttons:
                t = c.create_text(0, 0, text=label, font=("Malgun Gothic", 9, "bold" if primary else "normal"),
                                  fill=TEXT, anchor="nw")
                tb = c.bbox(t)
                made.append((t, tb[2] - tb[0] + 22, cb, primary))
                bx += tb[2] - tb[0] + 22 + 6
            w = max(w, bx + 30)
            h += 34
        shape = round_rect(c, 2, 2, w - 3, h - 3, 16, fill="#fffdf6", outline=LINE, width=2)
        c.tag_raise(tid, shape)
        if footer:
            c.create_text(18, h - 22, text=footer, anchor="w", font=("Malgun Gothic", 8), fill="#a08a76")
        x = w - 14
        for t, bw, cb, primary in reversed(made):
            x0 = x - bw
            tag = "btn%d" % t
            pill = round_rect(c, x0, h - 34, x, h - 12, 10, fill="#ffd27a" if primary else "#ffffff",
                              outline="#d9c2a3", width=1, tags=(tag,))
            c.coords(t, x0 + 11, h - 31)
            c.itemconfig(t, tags=(tag,))
            c.tag_raise(t, pill)
            c.tag_bind(tag, "<Button-1>", lambda e, f=cb: f())
            x = x0 - 6
        c.config(width=w, height=h)
        c.pack()
        if not buttons:
            c.bind("<Button-1>", lambda e: self.close())
        self.w, self.h = w, h
        self.alive = True
        self.has_buttons = bool(buttons)
        self.place()
        if seconds and seconds > 0:
            top.after(seconds * 1000, self.close)

    def place(self):
        if not self.alive:
            return
        r = self.app.root
        wx, wy, ww, wh = r.winfo_x(), r.winfo_y(), r.winfo_width(), r.winfo_height()
        x = wx + ww // 2 - self.w // 2
        y = wy - self.h + 34
        vs = virtual_screen() or (0, 0, r.winfo_screenwidth(), r.winfo_screenheight())
        if y < vs[1]:
            y = wy + wh - 4
        x = max(vs[0] + 4, min(x, vs[2] - self.w - 4))
        y = max(vs[1] + 4, min(y, vs[3] - self.h - 4))
        self.top.geometry("+%d+%d" % (x, y))

    def close(self):
        if self.alive:
            self.alive = False
            try:
                self.top.destroy()
            except Exception:
                pass


class CuteMenu:
    """Card-style right-click menu with icons."""
    BG = "#fffaf0"
    HOV = "#ffe9b8"
    W = 228

    def __init__(self, app, x, y):
        self.app = app
        self.alive = True
        top = self.top = tk.Toplevel(app.root)
        top.overrideredirect(True)
        top.attributes("-topmost", True)
        top.config(bg=KEY)
        top.attributes("-transparentcolor", KEY)
        items = [("memo", "메모 열기", app.open_memo),
                 ("calendar", "오늘 일정", app.menu_today),
                 ("decor", "꾸미기", app.open_decor),
                 ("change", "캐릭터 바꾸기", app.open_picker),
                 ("settings", "설정", app.open_settings_window),
                 ("help", "사용법 보기", app.start_tour)]
        head_h, row_h, tog_h, foot_h = 52, 36, 40, 52
        W = self.W
        H = head_h + 6 + len(items) * row_h + 8 + tog_h * 2 + foot_h
        c = self.c = tk.Canvas(top, width=W, height=H, bg=KEY, highlightthickness=0, bd=0)
        c.pack()
        round_rect(c, 2, 2, W - 3, H - 3, 18, fill=self.BG, outline=LINE, width=2)
        # header: little picture of the character + "토리의 메뉴"
        try:
            fr = app.char["idle"][0]
            f = max(1, -(-fr.height() // 38))
            self.thumb = fr.subsample(f, f)
            c.create_image(30, head_h // 2 + 2, image=self.thumb)
        except Exception:
            self.thumb = None
        c.create_text(56, head_h // 2 + 2, text="%s의 메뉴" % app.name, anchor="w",
                      font=("Malgun Gothic", 11, "bold"), fill=TEXT)
        c.create_line(16, head_h + 2, W - 16, head_h + 2, fill="#e6d6bf", dash=(3, 3))
        y = head_h + 6
        for i, (icon, label, cmd) in enumerate(items):
            self.row(i, y, row_h, icon, label, cmd)
            y += row_h
        c.create_line(16, y + 4, W - 16, y + 4, fill="#e6d6bf", dash=(3, 3))
        y += 8
        # on/off switches
        self.switches = {}
        self.toggle_row("tog_rand", y, tog_h, "캐릭터 랜덤으로 바꾸기", app.random_on, self.toggle_random)
        y += tog_h
        self.toggle_row("tog", y, tog_h, "컴퓨터 켤 때 자동 실행", autostart_enabled, self.toggle_autostart)
        y += tog_h
        # footer buttons
        half = (W - 16 * 2 - 8) // 2
        self.button(16, y + 6, half, 34, "restart", "다시 시작", app.restart, "#fff4dc")
        self.button(16 + half + 8, y + 6, half, 34, "power", "끄기", app.quit, "#ffe4e1")
        # place near the mouse, inside the screen
        wa = work_area() or (0, 0, app.root.winfo_screenwidth(), app.root.winfo_screenheight())
        x = max(wa[0] + 4, min(x, wa[2] - W - 4))
        yy = max(wa[1] + 4, min(app.root.winfo_pointery() - H // 2, wa[3] - H - 4))
        top.geometry("%dx%d+%d+%d" % (W, H, x, yy))
        top.bind("<Escape>", lambda e: self.close())
        top.bind("<FocusOut>", lambda e: top.after(120, self.close_if_unfocused))
        top.after(30, self.grab_focus)
        top.after(20000, self.close)

    def grab_focus(self):
        try:
            self.top.focus_force()
        except Exception:
            pass

    def close_if_unfocused(self):
        try:
            if self.alive and self.top.focus_displayof() is None:
                self.close()
        except Exception:
            self.close()

    def row(self, i, y, h, icon, label, cmd):
        c, tag = self.c, "row%d" % i
        bg = round_rect(c, 8, y + 2, self.W - 8, y + h - 2, 10, fill=self.BG, outline="", tags=(tag,))
        img = ui_icon(icon)
        if img:
            c.create_image(30, y + h // 2, image=img, tags=(tag,))
        c.create_text(52, y + h // 2, text=label, anchor="w", font=("Malgun Gothic", 10), fill=TEXT, tags=(tag,))
        c.tag_bind(tag, "<Enter>", lambda e: (c.itemconfig(bg, fill=self.HOV), c.config(cursor="hand2")))
        c.tag_bind(tag, "<Leave>", lambda e: (c.itemconfig(bg, fill=self.BG), c.config(cursor="")))
        c.tag_bind(tag, "<Button-1>", lambda e: self.run(cmd))

    def button(self, x, y, w, h, icon, label, cmd, fill):
        c, tag = self.c, "btn_" + icon
        bg = round_rect(c, x, y, x + w, y + h, 12, fill=fill, outline="#e6d6bf", width=1, tags=(tag,))
        img = ui_icon(icon)
        tx = x + w // 2
        if img:
            c.create_image(x + 22, y + h // 2, image=img, tags=(tag,))
            tx = x + 22 + (w - 22) // 2
        c.create_text(tx, y + h // 2, text=label, font=("Malgun Gothic", 9, "bold"), fill=TEXT, tags=(tag,))
        c.tag_bind(tag, "<Enter>", lambda e: (c.itemconfig(bg, fill=self.HOV), c.config(cursor="hand2")))
        c.tag_bind(tag, "<Leave>", lambda e: (c.itemconfig(bg, fill=fill), c.config(cursor="")))
        c.tag_bind(tag, "<Button-1>", lambda e: self.run(cmd))

    def toggle_row(self, tag, y, h, label, is_on, on_click):
        c = self.c
        bg = round_rect(c, 8, y + 2, self.W - 8, y + h - 4, 10, fill=self.BG, outline="", tags=(tag,))
        c.create_text(20, y + h // 2 - 1, text=label, anchor="w",
                      font=("Malgun Gothic", 9), fill=TEXT, tags=(tag,))
        self.switches[tag] = {"y": y, "is_on": is_on, "items": []}
        self.draw_switch(tag)
        c.tag_bind(tag, "<Enter>", lambda e: (c.itemconfig(bg, fill=self.HOV), c.config(cursor="hand2")))
        c.tag_bind(tag, "<Leave>", lambda e: (c.itemconfig(bg, fill=self.BG), c.config(cursor="")))
        c.tag_bind(tag, "<Button-1>", lambda e: on_click())

    def draw_switch(self, tag="tog"):
        c, sw = self.c, self.switches[tag]
        for it in sw["items"]:
            c.delete(it)
        try:
            on = bool(sw["is_on"]())
        except Exception:
            on = False
        x1, y1 = self.W - 62, sw["y"] + 10
        pill = round_rect(c, x1, y1, x1 + 40, y1 + 20, 10, fill="#9fd8b0" if on else "#e2d9cc",
                          outline="#d0c2ad", width=1, tags=(tag,))
        kx = x1 + 30 if on else x1 + 10
        knob = c.create_oval(kx - 8, y1 + 2, kx + 8, y1 + 18, fill="white", outline="#d0c2ad", tags=(tag,))
        sw["items"] = [pill, knob]

    def toggle_autostart(self):
        self.app.set_autostart_on(not autostart_enabled())
        self.draw_switch("tog")

    def toggle_random(self):
        self.app.set_random_on(not self.app.random_on())
        if self.alive:
            self.draw_switch("tog_rand")

    def run(self, cmd):
        self.close()
        self.app.root.after(10, cmd)

    def close(self):
        if self.alive:
            self.alive = False
            try:
                self.top.destroy()
            except Exception:
                pass


class SettingsWindow:
    """Friendly settings instead of editing settings.ini by hand."""
    BG = "#fffaf0"

    def __init__(self, app):
        self.app = app
        self.alive = True
        cfg = app.cfg
        top = self.top = tk.Toplevel(app.root)
        top.title("설정")
        top.attributes("-topmost", True)
        top.config(bg=self.BG)
        top.resizable(False, False)
        top.protocol("WM_DELETE_WINDOW", self.close)
        f_title = ("Malgun Gothic", 10, "bold")
        f = ("Malgun Gothic", 9)
        self.memo = tk.StringVar(value=cfg.get("MEMO", "auto").lower())
        self.size = tk.IntVar(value=app.int_cfg("SIZE", MAX_SIZE))
        self.animate = tk.BooleanVar(value=cfg.get("ANIMATE", "on").lower() != "off")
        self.motion = tk.BooleanVar(value=cfg.get("MOTION", "on").lower() != "off")
        self.bg = tk.BooleanVar(value=cfg.get("REMOVE_BG", "on").lower() != "off")
        self.greet = tk.BooleanVar(value=cfg.get("GREETING", "on").lower() != "off")
        self.auto = tk.BooleanVar(value=autostart_enabled())
        self.url = tk.StringVar(value=app.urls[0] if app.urls else "")
        self.show_url = tk.BooleanVar(value=False)
        rm = app.int_cfg("REMIND_MINUTES", 10)
        self.remind_opts = [("끄기", 0), ("5분 전", 5), ("10분 전", 10), ("15분 전", 15), ("30분 전", 30)]
        self.remind = tk.StringVar(value=next((l for l, v in self.remind_opts if v == rm), "10분 전"))
        self.tq = queue.Queue()

        def section(text):
            tk.Label(top, text=text, bg=self.BG, fg="#5a4636", font=f_title).pack(anchor="w", padx=18, pady=(12, 2))

        def check(text, var):
            tk.Checkbutton(top, text=text, variable=var, bg=self.BG, activebackground=self.BG,
                           font=f, anchor="w").pack(anchor="w", padx=24)

        section("메모")
        for val, text in (("sticky", "윈도우 스티커 메모 열기"), ("builtin", "위젯 전용 메모장 열기"),
                          ("auto", "자동 (스티커 메모가 있으면 그걸로)")):
            tk.Radiobutton(top, text=text, value=val, variable=self.memo, bg=self.BG, activebackground=self.BG,
                           font=f, anchor="w").pack(anchor="w", padx=24)
        section("캐릭터")
        row = tk.Frame(top, bg=self.BG)
        row.pack(anchor="w", padx=24, pady=(2, 2))
        tk.Label(row, text="크기", bg=self.BG, font=f).pack(side="left")
        tk.Label(row, text="작게", bg=self.BG, fg="#8a7360", font=("Malgun Gothic", 8)).pack(side="left", padx=(10, 2))
        tk.Scale(row, from_=120, to=260, resolution=10, orient="horizontal", variable=self.size, length=170,
                 showvalue=False, bg=self.BG, highlightthickness=0, troughcolor="#f0e4d2").pack(side="left")
        tk.Label(row, text="크게", bg=self.BG, fg="#8a7360", font=("Malgun Gothic", 8)).pack(side="left", padx=2)
        check("멈춘 그림도 통통 움직이게 만들기", self.animate)
        check("평소에 둥실둥실 떠 있기", self.motion)
        check("그림 배경 자동으로 지우기", self.bg)
        section("구글 캘린더 (선택)")
        cal = tk.Frame(top, bg=self.BG)
        cal.pack(anchor="w", padx=24)
        self.url_entry = tk.Entry(cal, textvariable=self.url, width=34, show="•", font=f, relief="groove")
        self.url_entry.pack(side="left")
        tk.Checkbutton(cal, text="보이기", variable=self.show_url, bg=self.BG, activebackground=self.BG, font=f,
                       command=lambda: self.url_entry.config(show="" if self.show_url.get() else "•")).pack(side="left", padx=4)
        cal2 = tk.Frame(top, bg=self.BG)
        cal2.pack(anchor="w", padx=24, pady=(4, 0))
        tk.Button(cal2, text="연결 확인", command=self.test_url, font=f, bg="white", relief="groove",
                  padx=8).pack(side="left")
        tk.Label(cal2, text="  알림", bg=self.BG, font=f).pack(side="left")
        om = tk.OptionMenu(cal2, self.remind, *[l for l, _ in self.remind_opts])
        om.config(font=f, bg="white", relief="groove", highlightthickness=0)
        om["menu"].config(font=f)
        om.pack(side="left", padx=4)
        how = tk.Label(cal2, text="주소 찾는 방법", bg=self.BG, fg="#a08a76", cursor="hand2",
                       font=("Malgun Gothic", 8, "underline"))
        how.pack(side="left", padx=6)
        how.bind("<Button-1>", lambda e: self.cal_help())
        self.test_lbl = tk.Label(top, text="", bg=self.BG, fg="#5a4636", font=("Malgun Gothic", 8),
                                 justify="left", wraplength=330)
        self.test_lbl.pack(anchor="w", padx=24, pady=(2, 0))
        section("기타")
        check("켤 때 인사하기", self.greet)
        check("컴퓨터 켤 때 자동 실행", self.auto)
        links = tk.Frame(top, bg=self.BG)
        links.pack(anchor="w", padx=24, pady=(6, 0))
        for text, cmd in (("위젯 폴더 열기", lambda: os.startfile(DIR)), ("고급: 설정 파일 직접 열기", app.open_settings)):
            lk = tk.Label(links, text=text, bg=self.BG, fg="#a08a76", cursor="hand2",
                          font=("Malgun Gothic", 8, "underline"))
            lk.pack(side="left", padx=(0, 12))
            lk.bind("<Button-1>", lambda e, c=cmd: c())
        btns = tk.Frame(top, bg=self.BG)
        btns.pack(fill="x", padx=18, pady=14)
        tk.Button(btns, text="취소", command=self.close, font=("Malgun Gothic", 10), bg="white",
                  relief="groove", padx=12).pack(side="right", padx=(6, 0))
        tk.Button(btns, text="저장", command=self.save, font=("Malgun Gothic", 10, "bold"), bg="#ffd27a",
                  relief="groove", padx=16).pack(side="right")
        top.update_idletasks()
        r = app.root
        x = r.winfo_x() - top.winfo_width() - 10
        wa = work_area()
        if wa and x < wa[0]:
            x = r.winfo_x() + r.winfo_width() + 10
        y = r.winfo_y() + r.winfo_height() - top.winfo_height()
        if wa:
            y = max(wa[1], min(y, wa[3] - top.winfo_height()))
        top.geometry("+%d+%d" % (x, max(0, y)))
        top.lift()
        top.focus_force()

    def cal_help(self):
        if messagebox.askyesno("구글 캘린더 연결", CAL_HELP, parent=self.top):
            webbrowser.open("https://calendar.google.com/calendar/u/0/r/settings")

    def test_url(self):
        u = self.url.get().strip()
        if not u:
            self.test_lbl.config(text="주소를 먼저 붙여넣어 주세요.", fg="#c0504d")
            return
        self.test_lbl.config(text="확인하는 중…", fg="#5a4636")

        def work():
            try:
                evs = usagi_cal.parse_ics(fetch_ics(u))
                n = len(usagi_cal.on_day(evs, date.today()))
                self.tq.put(("ok", "✔ 연결 성공! 일정 %d개를 받았고, 오늘 일정은 %d개예요." % (len(evs), n)))
            except Exception as ex:
                code = str(ex) if isinstance(ex, ValueError) else "%s" % ex
                self.tq.put(("err", "✖ " + explain_cal_error(code)))
        threading.Thread(target=work, daemon=True).start()
        self.poll_test()

    def poll_test(self):
        try:
            kind, msg = self.tq.get_nowait()
            self.test_lbl.config(text=msg, fg="#3d8b55" if kind == "ok" else "#c0504d")
        except queue.Empty:
            if self.alive:
                self.top.after(200, self.poll_test)

    def save(self):
        onoff = lambda v: "on" if v.get() else "off"
        before = (self.app.int_cfg("SIZE", MAX_SIZE), self.app.animate_on(), self.app.bg_on())
        try:
            remind = dict(self.remind_opts).get(self.remind.get(), 10)
            update_settings({"MEMO": self.memo.get(), "SIZE": str(self.size.get()), "ANIMATE": onoff(self.animate),
                             "MOTION": onoff(self.motion), "REMOVE_BG": onoff(self.bg), "GREETING": onoff(self.greet),
                             "ICAL_URL": self.url.get().strip(), "REMIND_MINUTES": str(remind)})
        except Exception as ex:
            messagebox.showerror("설정", "설정을 저장하지 못했어요: %s" % ex, parent=self.top)
            return
        if self.auto.get() != autostart_enabled():
            self.app.set_autostart_on(self.auto.get(), quiet=True)
        old_urls = list(self.app.urls)
        self.app.load_config()
        self.app.motion = self.app.cfg.get("MOTION", "on").lower() != "off"
        self.close()
        if self.app.urls and self.app.urls != old_urls:
            self.app.root.after(1500, lambda: self.app.refresh(True))
        after = (self.app.int_cfg("SIZE", MAX_SIZE), self.app.animate_on(), self.app.bg_on())
        if after != before and not self.app.placeholder:
            self.app.set_character(self.app.char_key)
        self.app.say("설정을 저장했어!", 4)

    def close(self):
        self.alive = False
        try:
            self.top.destroy()
        except Exception:
            pass


class Memo:
    def __init__(self, app):
        self.path = os.path.join(DIR, "memo.txt")
        self.name = app.name
        top = self.top = tk.Toplevel(app.root)
        top.title(app.name + " 메모")
        top.attributes("-topmost", True)
        top.config(bg="#fff7c8")
        top.geometry("300x320")
        self.text = tk.Text(top, wrap="word", font=("Malgun Gothic", 11), bg="#fff7c8",
                            bd=0, padx=10, pady=10, undo=True, relief="flat")
        self.text.pack(fill="both", expand=True)
        try:
            with open(self.path, encoding="utf-8") as f:
                self.text.insert("1.0", f.read())
        except FileNotFoundError:
            pass
        self.saved = self.text.get("1.0", "end-1c")
        self.text.edit_modified(False)
        # <<Modified>> also fires for Korean IME commits, unlike key events
        self.text.bind("<<Modified>>", self.on_modified)
        self.text.bind("<FocusOut>", lambda e: self.save())
        self.text.bind("<Control-s>", lambda e: (self.save(), "break")[1])
        top.protocol("WM_DELETE_WINDOW", self.close)
        self.alive = True
        self.autosave()
        r = app.root
        x = r.winfo_x() - 300 - 8
        wa = work_area()
        if wa and x < wa[0]:
            x = r.winfo_x() + r.winfo_width() + 8
        y = max(wa[1] if wa else 0, r.winfo_y() + r.winfo_height() - 360)
        top.geometry("+%d+%d" % (x, y))
        top.lift()
        top.focus_force()
        self.text.focus_set()

    def on_modified(self, _e=None):
        if self.text.edit_modified():
            self.text.edit_modified(False)
            self.top.after(300, self.save)

    def autosave(self):
        # safety net: every 2 s, write whatever is in the box if it changed
        if not self.alive:
            return
        self.save()
        self.top.after(2000, self.autosave)

    def save(self):
        if not self.alive:
            return
        try:
            content = self.text.get("1.0", "end-1c")
        except tk.TclError:
            return
        if content == self.saved:
            return
        try:
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(content)
            os.replace(tmp, self.path)
            self.saved = content
            self.top.title("%s 메모 · %s 저장됨" % (self.name, datetime.now().strftime("%H:%M:%S")))
        except Exception as ex:
            log("memo save: %s" % ex)
            self.top.title("%s 메모 · 저장 실패!" % self.name)

    def close(self):
        self.save()
        self.alive = False
        self.top.destroy()


# ---------------------------------------------------------------- app
class App:
    def __init__(self):
        self.root = r = tk.Tk()
        r.title("캐릭터 위젯")
        r.overrideredirect(True)
        r.attributes("-topmost", True)
        r.config(bg=KEY)
        r.attributes("-transparentcolor", KEY)
        r.report_callback_exception = self.on_error

        self.cfg, self.urls = {}, []
        self.load_config()
        self.t0, self.hop_start = time.time(), 0.0
        self.decor = load_decor()
        self.decor_win = None
        self.motion = self.cfg.get("MOTION", "on").lower() != "off"
        self.picker = None

        keys = list_characters()
        self.placeholder = not keys
        self.ph_items = []
        self.sprite = None
        load_names()
        if self.placeholder:
            self.char_key, self.char = None, None
        want = read_choice() if keys else ""
        if len(keys) > 1 and load_state().get("random_char"):      # 랜덤 바꾸기: 켤 때마다 다른 친구
            want = random.choice([k for k in keys if k != want] or keys)
        if keys:
            self.char_key = want if want in keys else (DEFAULT_CHAR if DEFAULT_CHAR in keys else keys[0])
            try:
                self.char = load_char(self.char_key, self.int_cfg("SIZE", MAX_SIZE), self.animate_on(), self.bg_on(), self.dec_for(self.char_key))
            except Exception as ex:
                log("load %s: %s" % (self.char_key, ex))
                self.char_key = keys[0]
                self.char = load_char(self.char_key, self.int_cfg("SIZE", MAX_SIZE), self.animate_on(), self.bg_on(), self.dec_for(self.char_key))
        self.name = self.display_name(self.char_key)

        self.effect = (self.dec_for(self.char_key) or {}).get("effect")
        w, h = self.canvas_size()
        self.cw, self.ch = w, h
        self.label = tk.Canvas(r, width=w, height=h, bg=KEY, highlightthickness=0, bd=0, cursor="hand2")
        self.label.pack()
        if self.placeholder:
            self.draw_placeholder()
        else:
            self.sprite = self.label.create_image(w // 2, h - 4, image=self.char["idle"][0], anchor="s")
        self.setup_effect(self.dec_for(self.char_key))
        x, y = self.load_pos(w, h)
        r.geometry("%dx%d+%d+%d" % (w, h, x, y))

        self.label.bind("<ButtonPress-1>", self.on_down)
        self.label.bind("<B1-Motion>", self.on_move)
        self.label.bind("<ButtonRelease-1>", self.on_up)
        self.label.bind("<Button-3>", self.on_menu)
        self.autostart = tk.BooleanVar(value=autostart_enabled())
        self.cute_menu = None
        self.settings_win = None
        self.events, self.today = [], []
        self.have_data, self.fetching = False, False
        self.loaded_day = self.announced_day = None
        self.last_fetch = 0.0
        self.notified = set()
        self.q = queue.Queue()
        self.state = load_state()

        self.bubble, self.memo = None, None
        self.down = None
        self.moved = False
        self.sticky = None

        _d = self.dec_for(self.char_key)
        self.cur_sig = decor_sig(_d) + "/" + str((_d or {}).get("effect"))
        self.root.after(10 * 60 * 1000, self.season_check)
        self.next_random = time.time() + self.random_minutes() * 60
        r.after(60 * 1000, self.random_tick)
        self.animate()
        r.after(2500, lambda: self.refresh(True))
        r.after(30000, self.tick)
        r.after(300, self.poll)
        if self.placeholder:
            r.after(900, lambda: self.say("안녕하세요!\n여기를 클릭해서 캐릭터로 쓸 그림을\n등록해 주세요 :)", 0,
                                          buttons=[("그림 고르기", self.register_character, True)]))
        elif not self.state.get("tour_done"):
            r.after(900, self.start_tour)
        elif self.cfg.get("GREETING", "on").lower() != "off":
            r.after(800, lambda: self.say(greeting_line(), 6))

    def on_error(self, exc, val, tb):
        log("".join(traceback.format_exception(exc, val, tb)))

    # ---------- config / position
    def load_config(self):
        self.cfg, self.urls = {}, []
        try:
            with open(os.path.join(DIR, "settings.ini"), encoding="utf-8-sig") as f:
                lines = f.read().splitlines()
        except UnicodeDecodeError:
            with open(os.path.join(DIR, "settings.ini"), encoding="cp949", errors="replace") as f:
                lines = f.read().splitlines()
        except FileNotFoundError:
            return
        for raw in lines:
            line = raw.strip()
            if not line or line[0] in "#;" or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k, v = k.strip().upper(), v.strip().strip('"')
            if k.startswith("ICAL_URL"):
                if v.lower().startswith("webcal://"):
                    v = "https://" + v[9:]
                if v.lower().startswith("http"):
                    self.urls.append(v)
            else:
                self.cfg[k] = v

    def int_cfg(self, k, default):
        try:
            return int(self.cfg.get(k, ""))
        except ValueError:
            return default

    def load_pos(self, w, h):
        try:
            with open(os.path.join(DIR, "pos.txt")) as f:
                x, y = (int(v) for v in f.read().strip().split(","))
            vs = virtual_screen()
            if vs and vs[0] <= x + w // 2 <= vs[2] and vs[1] <= y + h // 2 <= vs[3]:
                wa = work_area()
                if wa and wa[0] <= x + w // 2 <= wa[2] and wa[1] <= y + h // 2 <= wa[3] + h:
                    x = max(wa[0], min(x, wa[2] - w))
                    y = max(wa[1], min(y, wa[3] - h))
                return x, y
        except Exception:
            pass
        wa = work_area() or (0, 0, self.root.winfo_screenwidth(), self.root.winfo_screenheight() - 40)
        return wa[2] - w - 40, wa[3] - h - 6

    def save_pos(self):
        try:
            with open(os.path.join(DIR, "pos.txt"), "w") as f:
                f.write("%d,%d" % (self.root.winfo_x(), self.root.winfo_y()))
        except Exception:
            pass

    # ---------- animation
    def canvas_size(self):
        if self.placeholder or not self.char:
            return 160, 184
        frames = self.char["idle"] + (self.char["hop"] or [])
        iw = max(f.width() for f in frames)
        ih = max(f.height() for f in frames)
        head = 44 if self.char["bob"] else 0           # room to jump into
        mx, mt = (34, 26) if getattr(self, "effect", None) else (0, 0)   # room for falling petals/snow
        return iw + 8 + 2 * mx, ih + head + 6 + mt

    def setup_effect(self, dec):
        """(Re)create the little falling/rising particles around the character."""
        import random
        for p in getattr(self, "particles", []):
            self.label.delete(p["id"])
        self.particles = []
        self.effect = (dec or {}).get("effect")
        if not self.effect:
            return
        imgs = []
        if os.path.isdir(FX_DIR):
            for n in sorted(os.listdir(FX_DIR)):
                if n.startswith(self.effect + "_") and n.lower().endswith(".png"):
                    try:
                        imgs.append(tk.PhotoImage(file=os.path.join(FX_DIR, n)))
                    except Exception:
                        pass
        if not imgs:
            self.effect = None
            return
        self.fx_imgs = imgs
        cfg = EFFECTS[self.effect]
        self.rnd = random.Random()
        for i in range(cfg["n"]):
            p = dict(img=imgs[i % len(imgs)], phase=self.rnd.random() * 6.28)
            self.spawn(p, first=True)
            p["id"] = self.label.create_image(p["x"], p["y"], image=p["img"])
            self.particles.append(p)

    def spawn(self, p, first=False):
        cfg = EFFECTS[self.effect]
        p["x"] = self.rnd.uniform(6, self.cw - 6)
        p["v"] = self.rnd.uniform(*cfg["speed"])
        if cfg["dir"] == "up":
            p["y"] = self.rnd.uniform(10, self.ch) if first else self.ch + 6
        else:
            p["y"] = self.rnd.uniform(-10, self.ch - 10) if first else -8

    def move_particles(self):
        if not getattr(self, "particles", None):
            return
        up = EFFECTS[self.effect]["dir"] == "up"
        for p in self.particles:
            p["phase"] += 0.06
            p["y"] += -p["v"] if up else p["v"]
            p["x"] += math.sin(p["phase"]) * 0.45
            if p["y"] > self.ch + 8 or p["y"] < -10 or p["x"] < -10 or p["x"] > self.cw + 10:
                self.spawn(p)
            self.label.coords(p["id"], p["x"], p["y"])

    def animate_on(self):
        return self.cfg.get("ANIMATE", "on").lower() != "off"

    def bg_on(self):
        return self.cfg.get("REMOVE_BG", "on").lower() != "off"

    def display_name(self, key):
        if not key:
            return self.cfg.get("NAME", "") or "캐릭터 위젯"
        return _NAMES.get(key) or self.cfg.get("NAME", "") or default_name(key)

    def update_name(self, announce=False):
        self.name = self.display_name(self.char_key)
        if announce:
            self.say("이제 내 이름은 %s%s!" % (self.name, josa(self.name, "이야", "야")), 6)

    def dec_for(self, key):
        if not key:
            return None
        return active_decor(key, self.decor)

    def draw_placeholder(self):
        """Dashed 'please register a character' box shown when there is no character yet."""
        c = self.label
        for it in self.ph_items:
            c.delete(it)
        w, h = self.cw, self.ch
        x0, y0, x1, y1 = 6, 6, w - 6, h - 6
        self.ph_items = [
            round_rect(c, x0, y0, x1, y1, 18, fill="#fffdf8", outline=""),
            round_rect(c, x0, y0, x1, y1, 18, fill="", outline="#c8b49a", width=2, dash=(6, 4)),
            c.create_text(w // 2, h // 2 - 30, text="+", font=("Malgun Gothic", 30), fill="#c8a882"),
            c.create_text(w // 2, h // 2 + 14, text="캐릭터를\n등록해 주세요!", font=("Malgun Gothic", 10, "bold"),
                          fill=TEXT, justify="center"),
            c.create_text(w // 2, h // 2 + 48, text="클릭해서 그림 고르기", font=("Malgun Gothic", 8), fill="#a08a76"),
        ]

    def show_placeholder(self):
        """Back to the empty box (e.g. the last character was deleted)."""
        r = self.root
        cx, by = r.winfo_x() + self.cw // 2, r.winfo_y() + self.ch
        self.placeholder = True
        self.char_key, self.char = None, None
        if self.sprite:
            self.label.delete(self.sprite)
            self.sprite = None
        self.setup_effect(None)
        write_choice("")
        self.name = self.display_name(None)
        self.cw, self.ch = self.canvas_size()
        self.label.config(width=self.cw, height=self.ch)
        r.geometry("%dx%d+%d+%d" % (self.cw, self.ch, cx - self.cw // 2, by - self.ch))
        self.draw_placeholder()

    def register_character(self):
        if self.bubble:
            self.bubble.close()
        self.open_picker()
        if self.picker and self.picker.alive:
            self.picker.top.after(150, self.picker.add)

    def need_character(self):
        if self.placeholder:
            self.say("먼저 캐릭터 그림을 등록해 주세요!", 0,
                     buttons=[("나중에", lambda: self.bubble.close(), False),
                              ("그림 고르기", self.register_character, True)])
            return True
        return False

    def open_decor(self):
        if self.need_character():
            return
        if self.decor_win and self.decor_win.alive:
            self.decor_win.close()
        self.decor_win = DecorWindow(self)

    def season_check(self):
        # Christmas hat on/off when the date changes while the widget is running
        try:
            _d = self.dec_for(self.char_key)
            if not self.placeholder and decor_sig(_d) + "/" + str((_d or {}).get("effect")) != getattr(self, "cur_sig", None):
                self.set_character(self.char_key)
        except Exception as ex:
            log("season: %s" % ex)
        self.root.after(10 * 60 * 1000, self.season_check)

    def set_character(self, key):
        size = self.int_cfg("SIZE", MAX_SIZE)
        dec = self.dec_for(key)
        eff_bg = self.bg_on() and key != BUILTIN
        needs = (key == BUILTIN and dec and os.path.exists(source_path(BUILTIN))) or (key != BUILTIN and is_still(key))
        if self.animate_on() and needs and not anim_ready(key, size, eff_bg, dec):
            self.say("움직임 만드는 중…\n(처음 한 번만 몇 초 걸려요)", 30, hop=False)
            self.root.update()
        try:
            new = load_char(key, size, self.animate_on(), self.bg_on(), dec)
        except Exception as ex:
            log("load %s: %s" % (key, ex))
            messagebox.showerror("캐릭터 변경", "이 그림을 불러오지 못했어요.\n(%s)" % ex,
                                 parent=self.picker.top if self.picker and self.picker.alive else self.root)
            return False
        r = self.root
        old_w, old_h = self.cw, self.ch
        cx, by = r.winfo_x() + old_w // 2, r.winfo_y() + old_h      # keep feet in place
        was_empty = self.placeholder
        if was_empty:
            for it in self.ph_items:
                self.label.delete(it)
            self.ph_items = []
            self.placeholder = False
        self.char, self.char_key = new, key
        self.cur_sig = decor_sig(dec) + "/" + str((dec or {}).get("effect"))
        self.effect = (dec or {}).get("effect")
        self.name = self.display_name(key)
        write_choice(key)
        w, h = self.canvas_size()
        self.cw, self.ch = w, h
        self.label.config(width=w, height=h)
        if self.sprite is None:
            self.sprite = self.label.create_image(w // 2, h - 4, image=new["idle"][0], anchor="s")
        self.label.itemconfig(self.sprite, image=new["idle"][0])
        r.geometry("%dx%d+%d+%d" % (w, h, cx - w // 2, by - h))
        self.setup_effect(dec)
        self.save_pos()
        self.do_hop()
        if was_empty and not self.state.get("tour_done"):
            self.root.after(700, self.start_tour)
        return True

    def open_picker(self):
        if self.picker and self.picker.alive:
            self.picker.top.lift()
            self.picker.build()
            return
        self.picker = Picker(self)

    def animate(self):
        if self.placeholder or not self.char:
            self.root.after(120, self.animate)
            return
        now = time.time()
        c = self.char
        t = now - self.hop_start
        dy = 0.0
        if c["bob"]:
            if t < 1.2:                                  # two little hops
                p = (t % 0.6) / 0.6
                dy = 4 * p * (1 - p) * (34 if t < 0.6 else 22)
            elif self.motion:                            # gentle floating
                dy = 2.5 + 2.5 * math.sin((now - self.t0) * 2.4)
            frames = c["idle"]
            img = frames[int((now - self.t0) / 0.08) % len(frames)]
        elif c["hop"] and t < 1.44:
            img = c["hop"][int(t / 0.06) % len(c["hop"])]
        else:
            img = c["idle"][int((now - self.t0) / 0.07) % len(c["idle"])]
        self.label.itemconfig(self.sprite, image=img)
        self.label.coords(self.sprite, self.cw // 2, self.ch - 4 - round(dy))
        self.move_particles()
        self.root.after(40, self.animate)

    def do_hop(self):
        self.hop_start = time.time()

    # ---------- mouse
    def on_down(self, e):
        if self.cute_menu and self.cute_menu.alive:
            self.cute_menu.close()
        self.down = (e.x_root, e.y_root, self.root.winfo_x(), self.root.winfo_y())
        self.moved = False

    def on_move(self, e):
        if not self.down:
            return
        dx, dy = e.x_root - self.down[0], e.y_root - self.down[1]
        if not self.moved and abs(dx) + abs(dy) < 5:
            return
        self.moved = True
        self.root.geometry("+%d+%d" % (self.down[2] + dx, self.down[3] + dy))
        if self.bubble:
            self.bubble.place()

    def on_up(self, _e):
        if not self.down:
            return
        self.down = None
        if self.moved:
            self.save_pos()
        elif self.placeholder:
            self.register_character()
        else:
            self.open_memo()

    def build_menu(self):
        m = tk.Menu(self.root, tearoff=0, font=("Malgun Gothic", 10))
        m.add_command(label="메모 열기", command=self.open_memo)
        m.add_separator()
        m.add_command(label="캐릭터 변경", command=self.open_picker)
        m.add_command(label="꾸미기", command=self.open_decor)
        m.add_checkbutton(label="컴퓨터 켤 때 자동 실행", variable=self.autostart, command=self.toggle_autostart)
        m.add_command(label="설정 파일 열기", command=self.open_settings)
        m.add_separator()
        m.add_command(label="다시 시작 (업데이트 적용)", command=self.restart)
        m.add_command(label="종료", command=self.quit)
        return m

    def on_menu(self, e):
        self.open_menu(e.x_root, e.y_root)

    def open_menu(self, x, y):
        if self.cute_menu and self.cute_menu.alive:
            self.cute_menu.close()
        self.cute_menu = CuteMenu(self, x, y)

    def set_autostart_on(self, want, quiet=False):
        try:
            set_autostart(want)
            self.autostart.set(want)
            if not quiet:
                self.say("이제 컴퓨터를 켜면 내가 자동으로 나올게!" if want else "자동 실행을 껐어!", 5, want)
        except Exception as ex:
            log("autostart: %s" % ex)
            self.autostart.set(autostart_enabled())
            self.say("앗, 자동 실행 설정을 못 바꿨어…\n(%s)" % ex, 10, False)

    def toggle_autostart(self):
        self.set_autostart_on(self.autostart.get())

    # ---------- random character
    def random_on(self):
        return bool(self.state.get("random_char"))

    def random_minutes(self):
        return max(1, self.int_cfg("RANDOM_MINUTES", 30))

    def set_random_on(self, want):
        if want and len(list_characters()) < 2:
            self.say("캐릭터가 2개 이상 있어야\n랜덤으로 바꿀 수 있어!\n(메뉴 → 캐릭터 바꾸기 → +)", 8, False)
            return
        self.state["random_char"] = bool(want)
        save_state(self.state)
        if want:
            self.random_switch()
            self.say("이제 %d분마다 다른 친구로 바뀔게!" % self.random_minutes(), 5, False)
        else:
            self.next_random = time.time() + self.random_minutes() * 60
            self.say("랜덤 바꾸기를 껐어!", 4, False)

    def random_switch(self):
        self.next_random = time.time() + self.random_minutes() * 60
        if self.placeholder:
            return False
        if (self.picker and self.picker.alive) or (self.decor_win and self.decor_win.alive):
            return False                                    # 바꾸기·꾸미기 창을 쓰는 중이면 기다려요
        others = [k for k in list_characters() if k != self.char_key]
        if not others:
            return False
        return self.set_character(random.choice(others)) is True

    def random_tick(self):
        try:
            if self.random_on() and time.time() >= self.next_random:
                self.random_switch()
        except Exception as ex:
            log("random: %s" % ex)
        self.root.after(60 * 1000, self.random_tick)

    def open_settings_window(self):
        if self.settings_win and self.settings_win.alive:
            self.settings_win.close()
        self.settings_win = SettingsWindow(self)

    # ---------- first-run tour
    def start_tour(self):
        self.tour_i = 0
        self.show_tour()

    def show_tour(self):
        i, n = self.tour_i, len(TOUR)
        text = TOUR[i].format(name=self.name, iya=josa(self.name, "이야", "야"))
        if i == n - 1:
            buttons = [("시작하기 ♪", self.finish_tour, True)]
        else:
            buttons = [("건너뛰기", self.finish_tour, False), ("다음 ▶", self.next_tour, True)]
        if self.bubble:
            self.bubble.close()
        self.bubble = Bubble(self, text, 0, buttons=buttons, footer="%d / %d" % (i + 1, n))
        self.do_hop()

    def next_tour(self):
        self.tour_i += 1
        self.show_tour()

    def finish_tour(self):
        if self.bubble:
            self.bubble.close()
        self.state["tour_done"] = True
        save_state(self.state)

    def open_settings(self):
        try:
            subprocess.Popen(["notepad.exe", os.path.join(DIR, "settings.ini")])
        except Exception as ex:
            log("notepad: %s" % ex)

    def quit(self):
        self.save_pos()
        self.root.destroy()

    def restart(self):
        self.restart_flag = True
        self.quit()

    # ---------- memo
    def open_memo(self):
        self.do_hop()
        self.load_config()
        mode = self.cfg.get("MEMO", "auto").lower()
        if self.sticky is None:
            self.sticky = sticky_installed()
        if mode == "sticky" or (mode == "auto" and self.sticky):
            try:
                subprocess.Popen(["explorer.exe", STICKY_APP])
                return
            except Exception as ex:
                log("sticky: %s" % ex)
        if self.memo and self.memo.alive:
            self.memo.close()
            return
        self.memo = Memo(self)

    # ---------- bubble
    def say(self, text, seconds, hop=True, buttons=None):
        if self.bubble:
            self.bubble.close()
        self.bubble = Bubble(self, text, seconds, buttons=buttons)
        if hop:
            self.do_hop()

    # ---------- calendar
    def bubble_busy(self):
        """A tour step or a question is on screen - don't cover it with calendar news."""
        b = self.bubble
        return bool(b and b.alive and getattr(b, "has_buttons", False))

    def menu_today(self):
        if not self.urls:
            self.say("구글 캘린더를 연결하면\n오늘 일정을 알려줄게!", 0,
                     buttons=[("나중에", lambda: self.bubble.close(), False),
                              ("연결하기", lambda: (self.bubble.close(), self.open_settings_window()), True)])
            return
        if not self.have_data:
            self.refresh(True)
            return
        self.announce()

    def refresh(self, announce):
        if not self.urls or self.fetching:
            return
        self.fetching = True
        self.last_fetch = time.time()
        urls = list(self.urls)

        def work():
            evs, ok, err = [], 0, None
            diag = ["진단 시각: %s (일정 제목은 기록하지 않아요)" % datetime.now().strftime("%Y-%m-%d %H:%M:%S")]
            for i, u in enumerate(urls, 1):
                try:
                    data = fetch_ics(u)
                    evs.extend(usagi_cal.parse_ics(data))
                    diag.append("캘린더 %d: 받아오기 성공" % i)
                    try:
                        diag.extend(usagi_cal.diagnose(data, datetime.now()))
                    except Exception as ex:
                        diag.append("  진단 오류: %s" % ex)
                    ok += 1
                except Exception as ex:
                    err = str(ex)
                    diag.append("캘린더 %d: 실패 %s" % (i, type(ex).__name__))
            self.q.put((evs, ok > 0, err, announce, diag))

        threading.Thread(target=work, daemon=True).start()

    def poll(self):
        try:
            while True:
                self.fetched(*self.q.get_nowait())
        except queue.Empty:
            pass
        self.root.after(300, self.poll)

    def fetched(self, evs, ok, err, announce, diag=None):
        self.fetching = False
        if diag is not None:
            try:
                diag.append("일정 %d개 / 오늘(%s) %s개" % (len(evs), date.today(),
                                                        len(usagi_cal.on_day(evs, date.today())) if ok else "-"))
                with open(os.path.join(DIR, "diag.txt"), "w", encoding="utf-8") as f:
                    f.write("\n".join(diag) + "\n")
            except Exception as ex:
                log("diag: %s" % ex)
        if not ok:
            log("calendar: %s" % err)
            if announce:
                self.later_say("앗! " + explain_cal_error(err), 15)
            return
        self.events, self.have_data = evs, True
        self.loaded_day = date.today()
        self.today = usagi_cal.on_day(self.events, self.loaded_day)
        if announce:
            self.announced_day = date.today()
            self.announce()
        else:
            self.check_reminders()

    def later_say(self, text, seconds):
        if self.bubble_busy():
            self.root.after(5000, lambda: self.later_say(text, seconds))
        else:
            self.say(text, seconds)

    def announce(self):
        if self.bubble_busy():
            self.root.after(5000, self.announce)
            return
        if not self.today:
            self.say("오늘은 일정이 없어!\n여유로운 하루 보내~", 8)
            return
        lines = ["오늘 일정 %d개 있어!\n" % len(self.today)]
        for i, o in enumerate(self.today):
            if i == 8:
                lines.append("…외 %d개" % (len(self.today) - 8))
                break
            when = "종일" if o["allday"] else o["start"].strftime("%H:%M")
            lines.append("• %s  %s" % (when, o["summary"] or "(제목 없음)"))
        self.say("\n".join(lines), 20)

    def tick(self):
        try:
            now, today = time.time(), date.today()
            if self.have_data and self.loaded_day != today:
                self.today = usagi_cal.on_day(self.events, today)
                self.loaded_day = today
                self.notified.clear()
                self.refresh(False)
            elif self.urls and now - self.last_fetch >= 15 * 60:
                self.refresh(False)
            if self.have_data and self.announced_day != today and datetime.now().hour >= self.int_cfg("MORNING_HOUR", 8):
                self.announced_day = today
                self.announce()
            else:
                self.check_reminders()
        except Exception:
            log(traceback.format_exc())
        self.root.after(30000, self.tick)

    def check_reminders(self):
        mins = self.int_cfg("REMIND_MINUTES", 10)
        if mins <= 0 or self.bubble_busy():
            return
        now = datetime.now()
        due, soonest = [], None
        for o in self.today:
            if o["allday"]:
                continue
            left = (o["start"] - now).total_seconds() / 60
            k = (o["start"], o["summary"])
            if 0 < left <= mins and k not in self.notified:
                self.notified.add(k)
                soonest = int(left + 0.999) if soonest is None else min(soonest, int(left + 0.999))
                due.append("• %s  %s" % (o["start"].strftime("%H:%M"), o["summary"] or "(제목 없음)"))
        if due:
            self.say("%d분 뒤에 일정 있어!\n\n%s" % (soonest, "\n".join(due)), 40)

    def run(self):
        self.root.mainloop()


def main():
    lock = single_instance()
    if lock is None:
        try:
            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            messagebox.showinfo("캐릭터 위젯",
                                "캐릭터 위젯이 이미 켜져 있어요!\n\n"
                                                                "화면에서 캐릭터가 안 보이면 Ctrl+Shift+Esc(작업 관리자)에서\n"
                                "'Python' 또는 'pythonw' 를 작업 끝내기 한 뒤 다시 실행해 주세요.")
            root.destroy()
        except Exception:
            pass
        return
    try:
        app = App()
        app.run()
        if getattr(app, "restart_flag", False):
            try:
                ctypes.windll.kernel32.CloseHandle(lock)
            except Exception:
                pass
            subprocess.Popen([pythonw_path(), os.path.abspath(__file__)], cwd=DIR, close_fds=True)
    except Exception:
        err = traceback.format_exc()
        log(err)
        try:
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("캐릭터 위젯", "위젯 실행 중 오류가 났어요.\n같은 폴더의 error.log 파일을 확인해 주세요.\n\n" + err.strip().splitlines()[-1])
        except Exception:
            pass


if __name__ == "__main__":
    try:
        main()
    except BaseException:
        log("fatal: " + traceback.format_exc())
        raise
