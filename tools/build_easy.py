# -*- coding: utf-8 -*-
"""'파이썬 포함판' zip 만들기.

python.org 의 공식 파일(설치 없이 쓰는 Python + tkinter 부품)을 내려받아
위젯과 함께 묶어요. 공식 파일은 하나도 고치지 않아요 (서명이 그대로 유지돼요).

사용법 (Linux, msitools 필요):  python3 tools/build_easy.py
결과: CharacterWidget_v1.0_Easy.zip
"""
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile

PY_VER = "3.12.10"
OUT_NAME = "CharacterWidget_v1.0_Easy.zip"
TOP = "캐릭터위젯"
BASE = "https://www.python.org/ftp/python/%s/" % PY_VER
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 압축 푼 폴더 맨 위에 둬야 하는 파일 (실행 파일이 바로 옆에서 찾는 것들)
TOP_FILES = {"python312.dll", "python3.dll", "vcruntime140.dll", "vcruntime140_1.dll"}
SKIP_EMBED = {"python.exe", "python312._pth", "python.cat"}
TCL_KEEP = {"tcl8.6", "tk8.6", "tcl8", "dde1.4", "reg1.3"}      # tix(서명 없음·안 씀)와 개발용 파일은 뺌
USER_DATA = {"memo.txt", "pos.txt", "diag.txt", "decor.json", "names.json", "state.json",
             "character_choice.txt", "error.log", "launch.log", "install_error.log"}

PTH = "runtime\\python312.zip\r\nruntime\r\nimport site\r\n"


def fetch(name, dest):
    with urllib.request.urlopen(BASE + name) as r, open(dest, "wb") as f:
        shutil.copyfileobj(r, f)


def copy_tree(src, dst, skip_dirs=()):
    for root, dirs, files in os.walk(src):
        dirs[:] = [d for d in dirs if d not in skip_dirs and d != "characters" and d != ".anim"]
        rel = os.path.relpath(root, src)
        out = os.path.normpath(os.path.join(dst, rel))
        os.makedirs(out, exist_ok=True)
        for f in files:
            if f in USER_DATA or f.endswith((".pyc", ".log")):
                continue
            shutil.copy2(os.path.join(root, f), os.path.join(out, f))


def main():
    work = tempfile.mkdtemp()
    stage = os.path.join(work, "stage", TOP)
    rt = os.path.join(stage, "runtime")
    os.makedirs(rt)

    # 1) 설치 없이 쓰는 공식 Python
    embed_zip = os.path.join(work, "embed.zip")
    fetch("python-%s-embed-amd64.zip" % PY_VER, embed_zip)
    with zipfile.ZipFile(embed_zip) as z:
        for info in z.infolist():
            n = info.filename
            if n in SKIP_EMBED:
                continue
            if n == "pythonw.exe":
                target = os.path.join(stage, "설치하기.exe")
            elif n in TOP_FILES:
                target = os.path.join(stage, n)
            else:
                target = os.path.join(rt, n)
            with z.open(info) as s, open(target, "wb") as d:
                shutil.copyfileobj(s, d)

    # 2) 공식 tkinter 부품 (그림 창)
    msi = os.path.join(work, "tcltk.msi")
    fetch("amd64/tcltk.msi", msi)
    tk_dir = os.path.join(work, "tcltk")
    os.makedirs(tk_dir)
    subprocess.run(["msiextract", "-C", tk_dir, msi], check=True, stdout=subprocess.DEVNULL)
    for f in ("_tkinter.pyd", "tcl86t.dll", "tk86t.dll", "zlib1.dll"):
        shutil.copy2(os.path.join(tk_dir, "DLLs", f), os.path.join(rt, f))
    shutil.copytree(os.path.join(tk_dir, "Lib", "tkinter"), os.path.join(rt, "tkinter"))
    for d in TCL_KEEP:
        shutil.copytree(os.path.join(tk_dir, "tcl", d), os.path.join(rt, "tcl", d))

    # 3) 시작 도우미 + 설치 도우미 + 경로 파일
    shutil.copy2(os.path.join(REPO, "bundle", "sitecustomize.py"), os.path.join(rt, "sitecustomize.py"))
    shutil.copy2(os.path.join(REPO, "설치하기.pyw"), os.path.join(rt, "installer.pyw"))
    with open(os.path.join(stage, "python312._pth"), "w", encoding="utf-8", newline="") as f:
        f.write(PTH)

    # 4) 위젯 본체와 설명서 (개인 데이터는 넣지 않아요)
    copy_tree(os.path.join(REPO, "app"), os.path.join(stage, "app"))
    shutil.copy2(os.path.join(REPO, "bundle", "사용설명서.txt"), os.path.join(stage, "사용설명서.txt"))

    # 5) zip 으로 묶기
    out = os.path.join(REPO, OUT_NAME)
    if os.path.exists(out):
        os.remove(out)
    base = os.path.dirname(stage)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for root, dirs, files in os.walk(stage):
            dirs.sort()
            for f in sorted(files):
                p = os.path.join(root, f)
                z.write(p, os.path.relpath(p, base))
    shutil.rmtree(work, ignore_errors=True)
    print("made", out, os.path.getsize(out) // 1024, "KB")


if __name__ == "__main__":
    sys.exit(main())
