import subprocess, base64, os, sys, json

REPO = "workbuddyboy/workbuddy-Points-auto-claim"
BRANCH = "main"
GH = r"C:\Program Files\GitHub CLI\gh.exe"
TOKEN = os.environ.get("GH_TOKEN", "")

files = subprocess.run(
    ["git", "ls-files"], capture_output=True, text=True,
    cwd=os.path.dirname(os.path.abspath(__file__))
).stdout.splitlines()
files = [f.strip() for f in files if f.strip()]
print("待上传文件:", files)


def run_gh(args, with_token=True):
    cmd = [GH] + args
    env = dict(os.environ)
    if with_token and TOKEN:
        env["GH_TOKEN"] = TOKEN
    return subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=60)


def gh_api(method, path, fields):
    cmd = ["api", f"repos/{REPO}/{path}", "-X", method]
    for k, v in fields.items():
        cmd += ["-f", f"{k}={v}"]
    r = run_gh(cmd)
    return r.returncode, r.stdout, r.stderr


def get_sha(path):
    r = run_gh(["api", f"repos/{REPO}/contents/{path}?ref={BRANCH}"], with_token=True)
    if r.returncode != 0:
        return None
    try:
        return json.loads(r.stdout).get("sha")
    except Exception:
        return None


ok = 0
for f in files:
    try:
        with open(f, "rb") as fh:
            b64 = base64.b64encode(fh.read()).decode()
    except Exception as e:
        print(f"SKIP {f}: read error {e}")
        continue
    code, out, err = gh_api("PUT", f"contents/{f}",
                            {"message": f"add {f}", "content": b64, "branch": BRANCH})
    if code == 0:
        print(f"OK   {f}")
        ok += 1
        continue
    # 已存在则带 sha 更新
    sha = get_sha(f)
    if sha:
        code2, _, err2 = gh_api("PUT", f"contents/{f}",
                                {"message": f"update {f}", "content": b64,
                                 "branch": BRANCH, "sha": sha})
        if code2 == 0:
            print(f"OK(update) {f}")
            ok += 1
            continue
    print(f"FAIL {f}: {err.strip()[:150]}")

print(f"\n=== 完成：成功 {ok}/{len(files)} ===")
