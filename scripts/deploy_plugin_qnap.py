#!/usr/bin/env python
"""部署任意 MoviePilot V2/V3 插件目录到 qnap MP 容器（可重复执行的幂等流程）。

用法（Niubash，仓库根目录）：
    micromamba run -n base python -X utf8 scripts/deploy_plugin_qnap.py plugins.v3/autoptcheckin
    micromamba run -n base python -X utf8 scripts/deploy_plugin_qnap.py plugins.v2/rousi --no-reload

流程（对应 2026-11 实测踩坑后的固定顺序）：
  1. 从 <plugin_dir>/__init__.py 读 plugin_version / plugin_name
  2. python tarfile 生成 ustar：uid/gid=0、文件 644、目录 755、arcname 顶层 <dirname>/、跳过 __pycache__
     （arcname 顶层必须是插件目录名本身，不能带 plugins.v3/ 前缀，否则容器内多一层）
  3. scp 上传到 qnap 持久卷（勿用宿主 /tmp，仅 64MB）
  4. docker cp 进容器 /tmp，再解压到 <container-plugins>（先 rm -rf 旧目录，保证无旧码残留）
     BusyBox tar 恢复目录权限会报 "Cannot change mode ... Bad address"（退出码 2），
     文件本体已解出，属可容忍错误，下一步 chmod 统一补齐
  5. 容器内 find chmod：目录 755 / 文件 644
  6. POST /api/v1/plugin/reload/<plugin_name>；API key 从远端 key 文件读取（不进 git、不出现在命令行参数）
  7. 验证：容器内 grep plugin_version + /api/v1/plugin/ 运行态版本比对

API key 一次性落到 qnap 宿主（仅本机可读）：
    ssh qnap "umask 077 && echo '<KEY>' > /share/DockerData/moviepilot-v3/config/.mp_api_key"
"""

import argparse
import os
import posixpath
import re
import subprocess
import sys
import tarfile

# qnap docker 在 container-station 非标路径，仅 /etc/profile 注入（login shell）；
# subprocess 直连 ssh 是非交互 shell 拿不到，远端命令统一前置 PATH
REMOTE_DOCKER_BIN = "/share/CACHEDEV9_DATA/.qpkg/container-station/bin"
REMOTE_PATH = f"export PATH={REMOTE_DOCKER_BIN}:$PATH; "

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)


def _remote_tmp(tar_name):
    """本地 tar 产物目录：Windows 原生 Python 的 /tmp 会落到当前盘根，
    与 MSYS 类工具的 /tmp 映射不一致，统一用显式盘符路径。"""
    if os.name == "nt":
        return f"D:/tmp/{tar_name}"
    return posixpath.join("/tmp", tar_name)



def read_plugin_meta(plugin_dir):
    """reload id = 插件类名（MP 以 class 名为插件 id，非中文 plugin_name 显示名）。"""
    init_py = os.path.join(plugin_dir, "__init__.py")
    if not os.path.isfile(init_py):
        sys.exit(f"[deploy] 找不到 {init_py}（插件目录必须含 __init__.py）")
    text = open(init_py, encoding="utf-8").read()
    m_ver = re.search(r'^\s*plugin_version\s*=\s*["\']([^"\']+)["\']', text, re.M)
    if not m_ver:
        sys.exit(f"[deploy] {init_py} 中未找到 plugin_version")
    # 优先取 _PluginBase 子类：文件里的辅助类（异常、dataclass）会排在真正的插件类之前
    m_cls = re.search(r"^class\s+(\w+)\s*\(\s*_PluginBase[^)]*\)\s*:", text, re.M)
    if not m_cls:
        m_cls = re.search(r"^class\s+(\w+)\s*\(", text, re.M)
    if not m_cls:
        sys.exit(f"[deploy] {init_py} 中未找到插件类定义（reload 需要插件 id）")
    m_name = re.search(r'^\s*plugin_name\s*=\s*["\']([^"\']+)["\']', text, re.M)
    return m_cls.group(1), m_ver.group(1), (m_name.group(1) if m_name else "")


def make_tar(plugin_dir, arcname, version):
    """ustar：uid/gid=0、文件 644、目录 755、顶层 arcname、跳过 __pycache__。"""
    tar_name = f"{arcname}-{version}.tar"
    tar_path = _remote_tmp(tar_name)
    count = 0
    with tarfile.open(tar_path, "w", format=tarfile.USTAR_FORMAT) as tf:
        for root, dirs, files in os.walk(plugin_dir):
            dirs[:] = sorted(d for d in dirs if d != "__pycache__")
            for d in dirs:
                p = os.path.join(root, d)
                ti = tf.gettarinfo(p, arcname=arcname + "/" +
                                   os.path.relpath(p, plugin_dir).replace("\\", "/"))
                ti.uid = ti.gid = 0
                ti.uname = ti.gname = ""
                ti.mode = 0o755
                tf.addfile(ti)
            for f in sorted(files):
                if f == "__pycache__":
                    continue
                p = os.path.join(root, f)
                ti = tf.gettarinfo(p, arcname=arcname + "/" +
                                   os.path.relpath(p, plugin_dir).replace("\\", "/"))
                ti.uid = ti.gid = 0
                ti.uname = ti.gname = ""
                ti.mode = 0o644
                with open(p, "rb") as fh:
                    tf.addfile(ti, fh)
                count += 1
    print(f"[deploy] tar 就绪：{tar_path}（{count} 个文件，{os.path.getsize(tar_path)} 字节）")
    return tar_path, tar_name


def run(cmd, desc, allow_fail=False):
    """cmd 为 list 时直接 exec（不经过本地 shell，$ 变量原样透传远端）。"""
    printable = cmd if isinstance(cmd, str) else subprocess.list2cmdline(cmd)
    print(f"[deploy] {desc}\n          $ {printable}")
    if isinstance(cmd, str):
        proc = subprocess.run(cmd, shell=True)
    else:
        proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode:
        tail = ""
        if isinstance(cmd, list) and (proc.stdout or proc.stderr):
            tail = " | " + ((proc.stderr or "") + (proc.stdout or "")).strip().splitlines()[-1][:200]
        if allow_fail:
            print(f"[deploy]   （可容忍失败，继续：rc={proc.returncode}{tail}）")
            return proc
        sys.exit(f"[deploy] 失败：{desc}（rc={proc.returncode}{tail}）")
    if isinstance(cmd, list) and proc.stdout:
        print("          " + proc.stdout.strip().replace("\n", "\n          "))
    return proc


def main():
    ap = argparse.ArgumentParser(description="部署插件目录到 qnap MP 容器")
    ap.add_argument("plugin_dir", help="插件目录（相对仓库根），如 plugins.v3/autoptcheckin")
    ap.add_argument("--host", default="qnap", help="ssh_config 主机名（默认 qnap）")
    ap.add_argument("--container", default="MP", help="MP 容器名（默认 MP）")
    ap.add_argument("--remote-dir", default="/share/DockerData/moviepilot-v3/config",
                    help="qnap 持久卷目录（默认 MP v3 config）")
    ap.add_argument("--container-plugins", default="/app/app/plugins",
                    help="容器内插件根目录（默认 /app/app/plugins）")
    ap.add_argument("--api", default="http://127.0.0.1:3001", help="MP API 地址（qnap 本机）")
    ap.add_argument("--api-key-file", default=None,
                    help="qnap 宿主上的 API key 文件（默认 <remote-dir>/.mp_api_key）")
    ap.add_argument("--no-reload", action="store_true", help="只传文件解压，不 reload 不验证")
    args = ap.parse_args()

    plugin_dir = os.path.normpath(os.path.join(REPO, args.plugin_dir))
    if not os.path.isdir(plugin_dir):
        sys.exit(f"[deploy] 插件目录不存在：{plugin_dir}")
    arcname = os.path.basename(plugin_dir.rstrip("\\/"))
    key_file = args.api_key_file or posixpath.join(args.remote_dir, ".mp_api_key")

    reload_id, version, display_name = read_plugin_meta(plugin_dir)
    print(f"[deploy] {arcname} v{version}（reload id: {reload_id}，显示名: {display_name}）→ {args.host}:{args.container}")

    tar_path, tar_name = make_tar(plugin_dir, arcname, version)

    run(["scp", tar_path, f"{args.host}:{args.remote_dir}/{tar_name}"],
        f"上传 tar 到持久卷 {args.remote_dir}")
    run(["ssh", args.host,
         REMOTE_PATH + f"docker cp {args.remote_dir}/{tar_name} {args.container}:/tmp/{arcname}.tar"],
        "docker cp 进容器")
    run(["ssh", args.host,
         REMOTE_PATH + f"docker exec {args.container} sh -c "
         f"'cd {args.container_plugins} && rm -rf {arcname} && "
         f"tar -xf /tmp/{arcname}.tar && rm -f /tmp/{arcname}.tar'"],
        f"容器内解压到 {args.container_plugins}（BusyBox 目录 mode 报错可容忍）",
        allow_fail=True)
    run(["ssh", args.host,
         REMOTE_PATH + f"docker exec {args.container} sh -c "
         f"'find {args.container_plugins}/{arcname} -type d -exec chmod 755 {{}} + && "
         f"find {args.container_plugins}/{arcname} -type f -exec chmod 644 {{}} + && "
         f"grep -m1 plugin_version {args.container_plugins}/{arcname}/__init__.py'"],
        "容器内统一权限并核对版本")
    if args.no_reload:
        print(f"[deploy] --no-reload：跳过 reload 与运行态验证（v{version} 文件已就位）")
        return

    run(["ssh", args.host,
         REMOTE_PATH + f"curl -sS -X POST {args.api}/api/v1/plugin/reload/{reload_id} "
         f"-H \"X-API-KEY: $(cat {key_file})\" -H 'Content-Type: application/json' -d '{{}}'"],
        f"reload {reload_id}")
    verify = run(["ssh", args.host,
                  REMOTE_PATH + f"curl -sS {args.api}/api/v1/plugin/ -H \"X-API-KEY: $(cat {key_file})\" "
                  f"| tr '}}' '\\n' | grep '{reload_id}' "
                  f"| grep -o '\"plugin_version\":\"[^\"]*\"' | head -1"],
                 "验证运行态 plugin_version")
    runtime = (verify.stdout or "").strip()
    if version in runtime:
        print(f"[deploy] 完成：{arcname} v{version} 已部署且运行态版本一致 ✓")
    else:
        sys.exit(f"[deploy] 运行态版本异常：期望 {version}，实际 '{runtime}'（可能 reload 未生效）")


if __name__ == "__main__":
    main()
