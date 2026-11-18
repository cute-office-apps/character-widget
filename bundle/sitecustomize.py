# -*- coding: utf-8 -*-
"""캐릭터 위젯 '파이썬 포함판' 시작 도우미.

함께 들어 있는 공식 Python 이 켜질 때마다 자동으로 먼저 실행돼요.
- 그림 창(tkinter)이 쓰는 Tcl/Tk 폴더 위치를 알려줘요.
- '설치하기.exe' 를 그냥 더블클릭했으면 설치 도우미를 띄워요.
- 위젯을 실행할 때는 위젯 폴더를 모듈 찾는 경로에 넣어줘요.
"""
import os
import sys

_RT = os.path.dirname(os.path.abspath(__file__))
os.environ["TCL_LIBRARY"] = os.path.join(_RT, "tcl", "tcl8.6")
os.environ["TK_LIBRARY"] = os.path.join(_RT, "tcl", "tk8.6")

_argv = list(getattr(sys, "orig_argv", None) or sys.argv)
_exe_name = os.path.basename(sys.executable or "").lower()


def _script():
    for a in _argv[1:]:
        if a.lower().endswith((".py", ".pyw")):
            return a
    return None


if len(_argv) <= 1 and _exe_name not in ("python.exe", "pythonw.exe"):
    # 설치하기.exe 를 더블클릭한 경우 -> 설치 도우미 실행
    _root = os.path.dirname(os.path.abspath(sys.executable))
    os.environ["CW_BUNDLE_ROOT"] = _root
    _code = 0
    try:
        import runpy
        sys.argv = [os.path.join(_RT, "installer.pyw")]
        runpy.run_path(sys.argv[0], run_name="__main__")
    except SystemExit as _ex:
        _code = _ex.code if isinstance(_ex.code, int) else 0
    except BaseException:
        _code = 1
        try:
            import traceback
            with open(os.path.join(os.environ.get("TEMP", _root), "install_error.log"), "a",
                      encoding="utf-8") as _f:
                _f.write(traceback.format_exc())
        except Exception:
            pass
    finally:
        os._exit(_code)
else:
    _s = _script()
    if _s:
        _d = os.path.dirname(os.path.abspath(_s))
        if _d not in sys.path:
            sys.path.insert(0, _d)
