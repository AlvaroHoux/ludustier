#!/usr/bin/env python3
#
# run.py - Launch LudusTier in development / standalone mode
#
# SPDX-License-Identifier: GPL-3.0-or-later

import os
import sys
import subprocess

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

# Automatically compile gresource if missing or outdated
res_path = os.path.join(REPO_ROOT, "src", "ludustier.gresource")
xml_path = os.path.join(REPO_ROOT, "src", "ludustier.gresource.xml")
ui_path = os.path.join(REPO_ROOT, "src", "window.ui")
css_path = os.path.join(REPO_ROOT, "src", "style.css")

needs_compile = False
if not os.path.exists(res_path):
    needs_compile = True
else:
    res_mtime = os.path.getmtime(res_path)
    for src_f in [xml_path, ui_path, css_path]:
        if os.path.exists(src_f) and os.path.getmtime(src_f) > res_mtime:
            needs_compile = True
            break

if needs_compile:
    try:
        subprocess.run(
            [
                "glib-compile-resources",
                "--target=src/ludustier.gresource",
                "--sourcedir=src",
                "src/ludustier.gresource.xml",
            ],
            cwd=REPO_ROOT,
            check=True,
        )
    except Exception as e:
        print(f"[LudusTier] Aviso: Não foi possível compilar recursos automaticamente: {e}")

from src.main import main

if __name__ == "__main__":
    sys.exit(main())
