#!/usr/bin/env python3
"""
sync_repo.py — 把本地最新开发的脚本同步到 GitHub 仓库。

适用场景：你在本机修改了开发目录（默认 ../claim_points）里的脚本，
想一键把改动同步到这个开源仓库并推送到 GitHub。

用法（在你本机、网络正常时）：
    python sync_repo.py

它会：
  1. 从开发目录复制核心文件到本仓库目录
  2. git add / commit / push 到 origin main

可通过环境变量覆盖：
    SRC_DIR   开发目录（含 claim_cdp.py 等），默认 ../claim_points
    REPO_DIR  本仓库目录，默认本脚本所在目录
"""
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.environ.get("SRC_DIR", os.path.join(HERE, "..", "claim_points"))

# 需要同步的核心文件（不含隐私/运行时文件）
FILES = [
    "claim_cdp.py",
    "run.bat",
    "start_workbuddy_debug.bat",
    "register_task.ps1",
    "calibration.json",
    "requirements.txt",
]


def run(cmd):
    print(">", " ".join(cmd))
    return subprocess.run(cmd, cwd=HERE).returncode


def main():
    src_abs = os.path.abspath(SRC)
    missing = [f for f in FILES if not os.path.exists(os.path.join(src_abs, f))]
    if missing:
        print(f"源目录缺少文件: {missing}\nSRC_DIR = {src_abs}")
        sys.exit(1)

    for f in FILES:
        shutil.copy2(os.path.join(src_abs, f), os.path.join(HERE, f))
        print("copied", f)

    if run(["git", "add", "-A"]) != 0:
        print("git add 失败"); sys.exit(1)

    st = subprocess.run(["git", "status", "--porcelain"],
                        cwd=HERE, capture_output=True, text=True)
    if not st.stdout.strip():
        print("没有改动，无需同步。"); return

    if run(["git", "commit", "-m", "chore: sync latest scripts"]) != 0:
        print("git commit 失败"); sys.exit(1)
    if run(["git", "push", "origin", "main"]) != 0:
        print("git push 失败（若本机无推送能力，请改用 GitHub Web 手动上传）。")
        sys.exit(1)

    print("✅ 已同步并推送到 GitHub。")


if __name__ == "__main__":
    main()
