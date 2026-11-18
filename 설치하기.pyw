# -*- coding: utf-8 -*-
"""캐릭터 위젯 설치 도우미 - 더블클릭해서 실행하세요. (Python 기본 기능만 사용)"""
import ctypes
import os
import shutil
import subprocess
import sys
import traceback
from ctypes import POINTER, WINFUNCTYPE, byref, c_int, c_void_p, c_wchar_p, wintypes

import tkinter as tk
from tkinter import messagebox

# "파이썬 포함판"에서는 설치하기.exe 가 이 파일을 실행하면서 CW_BUNDLE_ROOT 에 압축 푼 폴더를 알려줘요.
BUNDLE_ROOT = os.environ.get("CW_BUNDLE_ROOT", "")
HERE = BUNDLE_ROOT or os.path.dirname(os.path.abspath(__file__))
BUNDLED = bool(BUNDLE_ROOT) and os.path.isdir(os.path.join(BUNDLE_ROOT, "runtime"))
SRC = os.path.join(HERE, "app")
APP_TITLE = "캐릭터 위젯"
RUN_NAME = "DesktopBuddyWidget"            # same name the widget uses for "자동 실행"
MUTEX = "DesktopBuddyWidget_Python"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
# the user's own data - never overwritten when updating
KEEP = {"settings.ini", "decor.json", "names.json", "state.json", "memo.txt", "pos.txt",
        "character_choice.txt"}
BG, LINE, TEXT, YEL = "#fffaf0", "#e6d6bf", "#5a4636", "#ffd27a"


def special_folder(csidl):
    buf = ctypes.create_unicode_buffer(520)
    try:
        ctypes.windll.shell32.SHGetFolderPathW(None, csidl, None, 0, buf)
    except Exception:
        return ""
    return buf.value


LOCAL = special_folder(0x1C) or os.path.join(os.path.expanduser("~"), "AppData", "Local")
DEST = os.path.join(LOCAL, "CharacterWidget")
DESKTOP = special_folder(0x10) or os.path.join(os.path.expanduser("~"), "Desktop")
PROGRAMS = special_folder(0x02)
LNK_NAME = APP_TITLE + ".lnk"
PY_DIR = os.path.join(DEST, "python")       # bundled Python is copied here (파이썬 포함판)


def pythonw():
    if BUNDLED:
        return os.path.join(PY_DIR, "pythonw.exe")
    exe = sys.executable or ""
    cands = []
    if exe and "\\program files\\windowsapps\\" not in exe.lower():
        cands.append(os.path.join(os.path.dirname(exe), "pythonw.exe"))
    cands += [shutil.which("pythonw.exe"), shutil.which("pyw.exe")]
    for c in cands:
        if c and os.path.exists(c):
            return c
    return exe


def is_running():
    try:
        k32 = ctypes.windll.kernel32
        h = k32.OpenMutexW(0x00100000, False, MUTEX)
        if h:
            k32.CloseHandle(h)
            return True
    except Exception:
        pass
    return False


def is_installed():
    return os.path.exists(os.path.join(DEST, "start_widget.pyw"))


# ---------------------------------------------------------------- shortcut (.lnk) via the Windows shell, no extra modules
class GUID(ctypes.Structure):
    _fields_ = [("Data1", ctypes.c_ulong), ("Data2", ctypes.c_ushort), ("Data3", ctypes.c_ushort),
                ("Data4", ctypes.c_ubyte * 8)]


def _guid(text):
    g = GUID()
    ctypes.windll.ole32.CLSIDFromString(c_wchar_p(text), byref(g))
    return g


def _method(obj, index, *argtypes):
    vtbl = ctypes.cast(obj, POINTER(POINTER(c_void_p))).contents
    fn = WINFUNCTYPE(ctypes.HRESULT, c_void_p, *argtypes)(vtbl[index])
    return lambda *args: fn(obj, *args)


def make_shortcut(lnk_path, target, args, workdir, icon, desc):
    ole32 = ctypes.windll.ole32
    ole32.CoInitialize(None)
    psl, ppf = c_void_p(), c_void_p()
    hr = ole32.CoCreateInstance(byref(_guid("{00021401-0000-0000-C000-000000000046}")), None, 1,
                                byref(_guid("{000214F9-0000-0000-C000-000000000046}")), byref(psl))
    if hr != 0 or not psl.value:
        raise OSError("바로가기를 만들 수 없어요 (0x%08X)" % (hr & 0xFFFFFFFF))
    try:
        _method(psl, 20, c_wchar_p)(target)                 # SetPath
        _method(psl, 11, c_wchar_p)(args)                   # SetArguments
        _method(psl, 9, c_wchar_p)(workdir)                 # SetWorkingDirectory
        if icon and os.path.exists(icon):
            _method(psl, 17, c_wchar_p, c_int)(icon, 0)     # SetIconLocation
        _method(psl, 7, c_wchar_p)(desc)                    # SetDescription
        _method(psl, 0, POINTER(GUID), POINTER(c_void_p))(
            byref(_guid("{0000010b-0000-0000-C000-000000000046}")), byref(ppf))   # QueryInterface(IPersistFile)
        _method(ppf, 6, c_wchar_p, wintypes.BOOL)(lnk_path, True)                # Save
    finally:
        for p in (ppf, psl):
            if p.value:
                try:
                    _method(p, 2)()                         # Release
                except Exception:
                    pass


def set_autostart(on, target=None, script=None):
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
        if on:
            winreg.SetValueEx(k, RUN_NAME, 0, winreg.REG_SZ, '"%s" "%s"' % (target, script))
        else:
            try:
                winreg.DeleteValue(k, RUN_NAME)
            except FileNotFoundError:
                pass


# ---------------------------------------------------------------- install / uninstall
def copy_app():
    copied = 0
    for root, dirs, files in os.walk(SRC):
        rel_dir = os.path.relpath(root, SRC)
        out_dir = DEST if rel_dir == "." else os.path.join(DEST, rel_dir)
        os.makedirs(out_dir, exist_ok=True)
        for f in files:
            dst = os.path.join(out_dir, f)
            rel = f if rel_dir == "." else os.path.join(rel_dir, f)
            if rel in KEEP and os.path.exists(dst):
                continue                                    # keep the user's settings/notes on update
            shutil.copy2(os.path.join(root, f), dst)
            copied += 1
    os.makedirs(os.path.join(DEST, "characters"), exist_ok=True)
    return copied


def _same(a, b):
    try:
        sa, sb = os.stat(a), os.stat(b)
    except OSError:
        return False
    return sa.st_size == sb.st_size and int(sa.st_mtime) == int(sb.st_mtime)


def _copy(src, dst):
    if _same(src, dst):
        return                                      # unchanged -> no need to touch files that may be in use
    try:
        shutil.copy2(src, dst)
    except PermissionError:
        raise OSError("켜져 있는 위젯을 먼저 꺼 주세요. (캐릭터 우클릭 → 끄기)")


def copy_runtime():
    """파이썬 포함판: 함께 들어 있는 Python 을 설치 폴더 안 python\\ 으로 복사해요."""
    os.makedirs(PY_DIR, exist_ok=True)
    _copy(sys.executable, os.path.join(PY_DIR, "pythonw.exe"))     # 설치하기.exe = 공식 pythonw.exe
    for f in os.listdir(BUNDLE_ROOT):
        if f.lower().endswith((".dll", "._pth")):
            _copy(os.path.join(BUNDLE_ROOT, f), os.path.join(PY_DIR, f))
    src = os.path.join(BUNDLE_ROOT, "runtime")
    for root, dirs, files in os.walk(src):
        out_dir = os.path.normpath(os.path.join(PY_DIR, "runtime", os.path.relpath(root, src)))
        os.makedirs(out_dir, exist_ok=True)
        for f in files:
            _copy(os.path.join(root, f), os.path.join(out_dir, f))


def install(desktop, startmenu, autostart):
    copy_app()
    if BUNDLED:
        copy_runtime()
    exe = pythonw()
    script = os.path.join(DEST, "start_widget.pyw")
    icon = os.path.join(DEST, "icon.ico")
    made = []
    for want, folder in ((desktop, DESKTOP), (startmenu, PROGRAMS)):
        lnk = os.path.join(folder, LNK_NAME) if folder else None
        if not lnk:
            continue
        if want:
            make_shortcut(lnk, exe, '"%s"' % script, DEST, icon, "바탕화면 캐릭터 메모·일정 위젯")
            made.append(lnk)
        elif os.path.exists(lnk):
            os.remove(lnk)
    set_autostart(autostart, exe, script)
    return exe, script, made


def uninstall(delete_data):
    for folder in (DESKTOP, PROGRAMS):
        lnk = os.path.join(folder, LNK_NAME) if folder else None
        if lnk and os.path.exists(lnk):
            os.remove(lnk)
    try:
        set_autostart(False)
    except Exception:
        pass
    if delete_data and os.path.isdir(DEST):
        shutil.rmtree(DEST, ignore_errors=True)


# ---------------------------------------------------------------- window
class Installer:
    def __init__(self):
        r = self.root = tk.Tk()
        r.title("%s 설치" % APP_TITLE)
        r.config(bg=BG)
        r.resizable(False, False)
        icon = os.path.join(SRC, "icon.ico")
        if os.path.exists(icon):
            try:
                r.iconbitmap(icon)
            except Exception:
                pass
        self.body = tk.Frame(r, bg=BG)
        self.body.pack(padx=26, pady=20)
        if not os.path.isdir(SRC):
            self.message("압축을 먼저 풀어 주세요!",
                         "zip 파일 안에서 바로 실행하면 설치할 수 없어요.\n\n"
                         "zip 파일을 우클릭 → '압축 풀기' 한 다음,\n"
                         "풀린 폴더 안의 '설치하기'를 다시 실행해 주세요.")
        else:
            self.home()
        r.update_idletasks()
        w, h = r.winfo_width(), r.winfo_height()
        r.geometry("+%d+%d" % ((r.winfo_screenwidth() - w) // 2, (r.winfo_screenheight() - h) // 3))

    def clear(self):
        for w in self.body.winfo_children():
            w.destroy()

    def title(self, text, sub=None):
        tk.Label(self.body, text=text, bg=BG, fg=TEXT, font=("Malgun Gothic", 15, "bold")).pack(anchor="w")
        if sub:
            tk.Label(self.body, text=sub, bg=BG, fg="#8a7360", font=("Malgun Gothic", 9),
                     justify="left").pack(anchor="w", pady=(4, 12))

    def button(self, parent, text, cmd, primary=False):
        b = tk.Button(parent, text=text, command=cmd, font=("Malgun Gothic", 10, "bold" if primary else "normal"),
                      bg=YEL if primary else "white", relief="groove", padx=16, pady=3, cursor="hand2")
        b.pack(side="right", padx=(8, 0))
        return b

    def message(self, head, text, buttons=None):
        self.clear()
        self.title(head)
        tk.Label(self.body, text=text, bg=BG, fg=TEXT, font=("Malgun Gothic", 10), justify="left").pack(
            anchor="w", pady=(10, 16))
        row = tk.Frame(self.body, bg=BG)
        row.pack(fill="x")
        for text_, cmd, primary in reversed(buttons or [("닫기", self.root.destroy, True)]):
            self.button(row, text_, cmd, primary)

    def home(self):
        self.clear()
        installed = is_installed()
        self.title("%s %s" % (APP_TITLE, "업데이트" if installed else "설치"),
                   "바탕화면에 캐릭터가 떠 있다가, 클릭하면 메모가 열리고\n"
                   "구글 캘린더 일정을 알려주는 위젯이에요.")
        if not BUNDLED and sys.version_info < (3, 8):
            tk.Label(self.body, text="Python 3.8 이상이 필요해요. Microsoft Store에서 Python을 설치해 주세요.",
                     bg=BG, fg="#c0504d", font=("Malgun Gothic", 9)).pack(anchor="w")
        self.v_desk = tk.BooleanVar(value=True)
        self.v_start = tk.BooleanVar(value=True)
        self.v_auto = tk.BooleanVar(value=True)
        for text, var in (("바탕화면에 '%s' 바로가기 만들기" % APP_TITLE, self.v_desk),
                          ("시작 메뉴에 추가하기", self.v_start),
                          ("컴퓨터 켤 때 자동으로 실행하기", self.v_auto)):
            tk.Checkbutton(self.body, text=text, variable=var, bg=BG, activebackground=BG,
                           font=("Malgun Gothic", 10), anchor="w").pack(anchor="w")
        tk.Label(self.body, text="설치 위치: %s" % DEST, bg=BG, fg="#a08a76",
                 font=("Malgun Gothic", 8)).pack(anchor="w", pady=(10, 2))
        if installed:
            tk.Label(self.body, text="이미 설치되어 있어요. 내 메모·캐릭터·설정은 그대로 두고 프로그램만 새로 바꿔요.",
                     bg=BG, fg="#a08a76", font=("Malgun Gothic", 8)).pack(anchor="w")
        row = tk.Frame(self.body, bg=BG)
        row.pack(fill="x", pady=(16, 0))
        self.button(row, "업데이트하기" if installed else "설치하기", self.do_install, True)
        if installed:
            self.button(row, "제거하기", self.do_uninstall)
        self.button(row, "닫기", self.root.destroy)

    def do_install(self):
        running = is_running()
        try:
            exe, script, made = install(self.v_desk.get(), self.v_start.get(), self.v_auto.get())
        except Exception as ex:
            self.log(traceback.format_exc())
            self.message("앗, 설치하지 못했어요",
                         "%s\n\n같은 폴더의 install_error.log 내용을 알려주시면 도와드릴게요." % ex)
            return
        self.exe, self.script = exe, script
        if running:
            text = ("이미 켜져 있는 위젯이 있어요.\n"
                    "캐릭터를 우클릭 → '다시 시작'을 누르면 새 버전이 적용돼요.")
            buttons = [("닫기", self.root.destroy, True)]
        else:
            text = ("이제 바탕화면의 '%s' 바로가기를 누르면 실행돼요.\n"
                    "처음 켜면 점선 네모를 눌러 캐릭터로 쓸 그림을 등록해 주세요!" % APP_TITLE)
            buttons = [("닫기", self.root.destroy, False), ("지금 실행하기", self.launch, True)]
        if (self.v_desk.get() or self.v_start.get()) and not made:
            text += "\n\n(바로가기는 만들지 못했어요. 설치 위치의 start_widget 을 실행해 주세요.)"
        self.message("설치 완료! ♪", text, buttons)

    def launch(self):
        try:
            subprocess.Popen([self.exe, self.script], cwd=DEST)
        except Exception as ex:
            messagebox.showerror(APP_TITLE, "실행하지 못했어요: %s" % ex, parent=self.root)
            return
        self.root.destroy()

    def do_uninstall(self):
        if is_running():
            messagebox.showinfo(APP_TITLE, "먼저 위젯을 꺼 주세요.\n(캐릭터 우클릭 → 끄기)", parent=self.root)
            return
        ans = messagebox.askyesnocancel(
            "%s 제거" % APP_TITLE,
            "바로가기와 자동 실행을 지울게요.\n\n내 메모·캐릭터 그림·설정까지 모두 지울까요?\n"
            "[예] 모두 지우기    [아니요] 바로가기만 지우기", parent=self.root)
        if ans is None:
            return
        try:
            uninstall(delete_data=ans)
        except Exception as ex:
            self.log(traceback.format_exc())
            messagebox.showerror(APP_TITLE, "제거 중 문제가 생겼어요: %s" % ex, parent=self.root)
            return
        self.message("제거했어요", "그동안 사용해 주셔서 고마워요!" + ("" if ans else "\n(메모와 그림은 %s 에 남아 있어요)" % DEST))

    def log(self, text):
        for folder in (HERE, os.environ.get("TEMP", "")):
            try:
                with open(os.path.join(folder, "install_error.log"), "a", encoding="utf-8") as f:
                    f.write(text + "\n")
                return
            except Exception:
                continue

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    try:
        Installer().run()
    except Exception:
        try:
            with open(os.path.join(os.environ.get("TEMP", HERE), "install_error.log"), "a", encoding="utf-8") as f:
                f.write(traceback.format_exc())
        except Exception:
            pass
        raise
