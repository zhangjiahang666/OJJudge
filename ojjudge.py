# -*- coding: utf-8 -*-
"""
OJJudge —— 本地 OI 评测软件（为张嘉航打造）
功能：
  1) 单题模式：选一个源码 + 一个数据目录，一键评测。
  2) 多题模式：添加任意多道题（题名/源码/数据目录），一键全部评测，结果按题分组汇总。
  3) 对拍：主程序 vs 暴力/标程，随机数据揪 bug。
  4) 造数据：自动生成随机 .in 与 .out。
  表格显示每组 AC/WA、得分、用时、期望/实际输出。
  用 tkinter 实现，打包为独立 .exe，不依赖外部环境。
"""
import os, re, sys, subprocess, threading, time, glob, random, json, queue
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

DEFAULT_GXX = r"C:\mingw64\bin\g++.exe"

# ---------- 主题配色（现代简洁 · 靛青渐变） ----------
BG       = "#eef1f7"   # 窗口背景（浅灰蓝）
CARD     = "#ffffff"   # 卡片/输入框背景
BORDER   = "#dfe4ee"   # 卡片/控件描边
HEADER_A = "#4f46e5"   # 标题栏渐变起（靛蓝）
HEADER_B = "#7c3aed"   # 标题栏渐变止（紫）
HEADER_T = "#c7d2fe"   # 标题栏副文字
PRIMARY  = "#6366f1"   # 主靛蓝
PRIMARY_D= "#4f46e5"
ACCENT   = "#22d3ee"   # 青蓝点缀
GREEN    = "#10b981"
RED      = "#ef4444"
AMBER    = "#f59e0b"
GRAY     = "#9aa3b2"
ROW_ALT  = "#f7f9fc"
SEL_BG   = "#eef0ff"   # 表格选中行背景


def _blend(c1, c2, t):
    """两个十六进制颜色按比例混合（t: 0~1）。"""
    r = int(int(c1[1:3], 16) * (1 - t) + int(c2[1:3], 16) * t)
    g = int(int(c1[3:5], 16) * (1 - t) + int(c2[3:5], 16) * t)
    b = int(int(c1[5:7], 16) * (1 - t) + int(c2[5:7], 16) * t)
    return "#%02x%02x%02x" % (r, g, b)


def _default_import_path():
    """返回「题目导入.json」的默认位置：程序所在目录（exe 或脚本同目录）。"""
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "题目导入.json")


def _records_path():
    """评测记录文件位置：程序所在目录。"""
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "评测记录.json")


def load_records(path=None):
    """读取评测记录列表（list of dict）。"""
    path = path or _records_path()
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                d = json.load(f)
            return d.get("evaluations", [])
        except Exception:
            pass
    return []


def save_records(records, path=None):
    """把评测记录列表写回文件。"""
    path = path or _records_path()
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"evaluations": records}, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


# 改动日志：记录每次迭代做了什么，可在软件「记录」页查看
CHANGELOG = """OJJudge 评测软件 · 改动记录
────────────────────────────
v1.0  （基础版）
  · 单题评测：一个源码 + 一个数据目录，一键出分（AC/WA/TLE、得分、用时、期望/实际）。
  · 多题评测：添加多道题，一键全部评测，结果按题分组汇总。
  · 对拍：主程序 vs 暴力/标程，用随机数据揪 bug。
  · 造数据：自动生成随机 .in 与 .out。

v1.1  （增强）
  · 新增「随机数据」：填输入格式/范围/数量 + AC 代码，自动生成可测数据（无需 freopen 手写生成器）。
  · 界面美化：靛紫渐变标题栏、胶囊标签页、分区色条、卡片、斑马纹表格，整体对齐网页版风格。

v1.2  （对拍不中断）
  · 对拍遇到错误不再中途停止：跑完全部轮，统计并一次性列出所有不一致/异常。
  · 结果表状态徽章：AC 浅绿 / WA 浅红 / 其他浅黄，一眼看清。

v1.3  （导入与稳定）
  · 多题支持启动自动导入：exe 同目录的「题目导入.json」自动填进多题列表，也可手动「导入题目」。
  · 修复多题评测"只测一个就跳过"：改为线程安全队列模式，工作线程不碰界面控件，单题异常不中断后续。

v1.4  （记录）
  · 新增「记录」页：评测记录（单题/多题/对拍每次运行自动保存，可回看历史）+ 改动日志。
  · 评测记录持久化到 exe 同目录的「评测记录.json」。
"""


def setup_style(root):
    """配置 ttk 全局主题（现代简洁风，仿主流桌面应用）。"""
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except Exception:
        pass

    # 基础容器 / 文本
    style.configure("TFrame", background=BG)
    style.configure("TLabel", background=BG, foreground="#2b3344", font=("微软雅黑", 10))
    style.configure("Card.TFrame", background=CARD)
    style.configure("Card.TLabel", background=CARD, foreground="#2b3344", font=("微软雅黑", 10))
    style.configure("Section.TLabel", background=BG, foreground="#3a4256",
                    font=("微软雅黑", 11, "bold"))
    style.configure("TLabelframe", background=BG, bordercolor=BORDER)
    style.configure("TLabelframe.Label", background=BG, foreground="#4b5563",
                    font=("微软雅黑", 10, "bold"))

    # 按钮：主按钮（靛蓝）、次按钮（白底描边）、危险按钮（浅红）
    style.configure("Accent.TButton", font=("微软雅黑", 10, "bold"), padding=(16, 8),
                    background=PRIMARY, foreground="#ffffff", bordercolor=PRIMARY,
                    focuscolor="#ffffff", relief="flat")
    style.map("Accent.TButton",
              background=[("active", PRIMARY_D), ("pressed", PRIMARY_D), ("disabled", "#c7d2fe")],
              foreground=[("disabled", "#ffffff")])
    style.configure("TButton", font=("微软雅黑", 10), padding=(12, 6),
                    background="#ffffff", foreground="#3a4256", bordercolor=BORDER,
                    focuscolor="#ffffff", relief="flat")
    style.map("TButton",
              background=[("active", "#f2f4f9"), ("pressed", "#e9ecf4"), ("disabled", "#f3f5f9")],
              foreground=[("disabled", "#b6bdc9")])
    style.configure("Danger.TButton", font=("微软雅黑", 10), padding=(12, 6),
                    background="#fee2e2", foreground="#dc2626", bordercolor="#fecaca",
                    focuscolor="#ffffff", relief="flat")
    style.map("Danger.TButton", background=[("active", "#fecaca"), ("disabled", "#fde8e8")])

    # 输入框
    style.configure("TEntry", font=("微软雅黑", 10), fieldbackground=CARD,
                    foreground="#2b3344", bordercolor=BORDER, insertcolor=PRIMARY, padding=5)
    style.map("TEntry", bordercolor=[("focus", PRIMARY)], lightcolor=[("focus", PRIMARY)])
    style.configure("TCombobox", font=("微软雅黑", 10), fieldbackground=CARD,
                    background="#ffffff", foreground="#2b3344", arrowcolor="#7b8494",
                    bordercolor=BORDER, padding=4)
    style.map("TCombobox", bordercolor=[("focus", PRIMARY)])
    style.configure("TSpinbox", font=("微软雅黑", 10), fieldbackground=CARD,
                    background="#ffffff", foreground="#2b3344", bordercolor=BORDER, padding=4)
    style.map("TSpinbox", bordercolor=[("focus", PRIMARY)])
    style.configure("TCheckbutton", background=BG, foreground="#3a4256", font=("微软雅黑", 10))
    style.map("TCheckbutton", background=[("active", BG)])
    style.configure("TRadiobutton", background=BG, foreground="#3a4256", font=("微软雅黑", 10))

    # Tab：胶囊式
    style.configure("TNotebook", background=BG, borderwidth=0, tabmargins=(12, 8, 12, 0))
    style.configure("TNotebook.Tab", font=("微软雅黑", 11, "bold"),
                    padding=(22, 9), background="#e2e8f2", foreground="#5b6b82")
    style.map("TNotebook.Tab",
              background=[("selected", PRIMARY), ("active", "#cdd6e8")],
              foreground=[("selected", "#ffffff"), ("active", "#334155")],
              bordercolor=[("selected", PRIMARY), ("active", "#cdd6e8")])

    # 表格
    style.configure("Treeview", font=("微软雅黑", 10), rowheight=28,
                    background=CARD, fieldbackground=CARD, foreground="#2b3344",
                    bordercolor=BORDER, relief="flat")
    style.map("Treeview",
              background=[("selected", SEL_BG), ("active", ROW_ALT)],
              foreground=[("selected", "#3730a3")])
    style.configure("Treeview.Heading", font=("微软雅黑", 10, "bold"),
                    background="#eef1f7", foreground="#5b6b82", padding=(8, 7), relief="flat")
    style.map("Treeview.Heading", background=[("active", "#e2e8f2")])

    # 滚动条
    style.configure("Vertical.TScrollbar", background="#cfd6e4", troughcolor=BG,
                    borderwidth=0, arrowcolor="#8a93a5")
    style.configure("Horizontal.TScrollbar", background="#cfd6e4", troughcolor=BG,
                    borderwidth=0, arrowcolor="#8a93a5")

    # 状态 / 提示
    style.configure("Status.TLabel", font=("微软雅黑", 10, "bold"), foreground=PRIMARY, background=BG)
    style.configure("Hint.TLabel", font=("微软雅黑", 9), foreground="#8a93a5", background=BG)
    return style


def build_header(root):
    """顶部渐变标题栏 + 徽标 + 副标语 + 底部渐变细条。"""
    h = tk.Canvas(root, height=76, highlightthickness=0, bd=0)
    h.pack(fill="x")

    def draw():
        h.delete("all")
        w = max(h.winfo_width(), 400)
        steps = 84
        for i in range(steps):
            t = i / (steps - 1)
            h.create_rectangle(0, i, w, i + 1, fill=_blend(HEADER_A, HEADER_B, t), outline="")
        # 徽标
        h.create_oval(20, 15, 54, 49, fill="#ffffff", outline="")
        h.create_text(37, 32, text="OJ", fill=PRIMARY, font=("Segoe UI", 13, "bold"))
        # 标题与副标题
        h.create_text(68, 22, text="OJJudge 评测软件", anchor="w", fill="#ffffff",
                      font=("微软雅黑", 15, "bold"))
        h.create_text(68, 47, text="单题 · 多题 · 对拍 · 造数据", anchor="w", fill=HEADER_T,
                      font=("微软雅黑", 9))
        # 右侧标语
        h.create_text(w - 20, 38, text="本地 OI 评测 · 一键出分", anchor="e", fill=HEADER_T,
                      font=("微软雅黑", 9))
    h.bind("<Configure>", lambda e: draw())
    draw()

    # 底部渐变细条（靛 → 青）
    strip = tk.Frame(root, height=4)
    strip.pack(fill="x")
    strip.pack_propagate(False)
    n = 6
    for i in range(n):
        seg = tk.Frame(strip, bg=_blend(PRIMARY, ACCENT, i / (n - 1)))
        seg.pack(side="left", fill="x", expand=True)
    # 标题栏下方的柔和投影线（网页风层次感）
    shadow = tk.Frame(root, height=2, bg="#d7dced")
    shadow.pack(fill="x")
    return h


def natural_key(name):
    m = re.search(r"(\d+)", os.path.basename(name))
    return int(m.group(1)) if m else 0


def run_battle(main_src, brute_src, gen_src, gxx, std, opt, rounds,
               workdir, report=None, timeout_ms=5000):
    """
    对拍：数据生成器造随机数据 -> 主程序与暴力/标程同跑 -> 比对输出。
    report 回调: report(kind, message)，kind in {info, warn, fail, ok, error}
    发现不一致/异常不会中途停止，会跑完全部轮并累计，最后汇总报告。
    返回 True=全部一致，False=至少一处问题。数据保存在 workdir。
    """
    def rep(kind, msg):
        if report:
            report(kind, msg)

    # 编译三个程序（生成器、主程序、暴力）
    gen_exe = os.path.join(workdir, "_gen.exe")
    main_exe = os.path.join(workdir, "_main.exe")
    brute_exe = os.path.join(workdir, "_brute.exe")
    for tag, s, exe in (("生成器", gen_src, gen_exe),
                        ("主程序", main_src, main_exe),
                        ("暴力", brute_src, brute_exe)):
        p = compile_one(gxx, s, exe, std, opt)
        if p.returncode != 0:
            rep("error", f"{tag}编译失败:\n{(p.stderr or p.stdout or '')[:500]}")
            return False

    data_in = os.path.join(workdir, "data.in")
    main_out = os.path.join(workdir, "main.out")
    brute_out = os.path.join(workdir, "brute.out")

    issues = []          # 累计所有不一致 / 异常轮
    consistent = 0       # 一致轮数

    for r in range(1, rounds + 1):
        # 1) 生成数据：生成器 stdout -> data.in
        try:
            with open(data_in, "wb") as fo:
                subprocess.run([gen_exe], cwd=workdir, stdout=fo,
                               timeout=timeout_ms / 1000.0)
        except subprocess.TimeoutExpired:
            rep("warn", f"第{r}轮: 数据生成器超时（继续）")
            issues.append(f"第{r}轮: 数据生成器超时")
            continue
        except Exception as e:
            rep("warn", f"第{r}轮: 生成器出错 {e}（继续）")
            issues.append(f"第{r}轮: 生成器出错 {e}")
            continue

        # 2) 主程序 与 暴力程序 各跑一遍
        def run_one(exe, out_file):
            with open(data_in, "rb") as fi, open(out_file, "wb") as fo:
                try:
                    subprocess.run([exe], cwd=workdir, stdin=fi, stdout=fo,
                                   timeout=timeout_ms / 1000.0)
                except subprocess.TimeoutExpired:
                    return "TLE"
                except Exception as e:
                    return f"ERR:{e}"
            return "OK"

        s_main = run_one(main_exe, main_out)
        s_brute = run_one(brute_exe, brute_out)

        # 3) 比对
        m = _read_text(main_out).strip() if os.path.isfile(main_out) else ""
        b = _read_text(brute_out).strip() if os.path.isfile(brute_out) else ""
        d = _read_text(data_in).strip() if os.path.isfile(data_in) else ""
        if s_main != "OK" or s_brute != "OK":
            rep("warn", f"第{r}轮: 运行异常 主[{s_main}] 暴力[{s_brute}]（继续）")
            issues.append(f"第{r}轮: 运行异常 主[{s_main}] 暴力[{s_brute}]\n输入:\n{d}")
            continue
        if m != b:
            rep("warn", f"第{r}轮: 输出不一致（继续）")
            issues.append(f"第{r}轮: 输出不一致\n--- 输入 ---\n{d}\n--- 主程序输出 ---\n{m}\n--- 暴力/标程输出 ---\n{b}")
            continue
        consistent += 1
        rep("info", f"第{r}轮: 一致 ({m[:30]})")

    if issues:
        summary = (f"对拍完成：共 {rounds} 轮，一致 {consistent} 轮，发现 {len(issues)} 处问题：\n"
                   + "\n".join(issues))
        rep("fail", summary)
        return False
    rep("ok", f"对拍完成：共 {rounds} 轮全部一致，没有发现问题。")
    return True


def generate_data(gen_src, ans_src, task, rounds, outdir, gxx, std, opt,
                  ext=".out", report=None, timeout_ms=5000):
    """
    造数据：数据生成器每轮造一组随机输入 -> 存为 <task><n>.in；
            答案程序读该输入 -> 存为 <task><n>.out（或 .ans）。
    report(kind, msg)。返回 (成功组数, 总组数)。
    要求生成器、答案程序都用标准输入输出（stdout 出、stdin 进）。
    """
    def rep(kind, msg):
        if report:
            report(kind, msg)

    if not os.path.isdir(outdir):
        os.makedirs(outdir, exist_ok=True)

    gen_exe = os.path.join(outdir, "_gendata_gen.exe")
    ans_exe = os.path.join(outdir, "_gendata_ans.exe")
    for tag, s, exe in (("生成器", gen_src, gen_exe), ("答案程序", ans_src, ans_exe)):
        p = compile_one(gxx, s, exe, std, opt)
        if p.returncode != 0:
            rep("error", f"{tag}编译失败:\n{(p.stderr or p.stdout or '')[:500]}")
            return 0, rounds

    ok_count = 0
    for r in range(1, rounds + 1):
        in_path = os.path.join(outdir, f"{task}{r}{'.in'}")
        out_path = os.path.join(outdir, f"{task}{r}{ext}")
        # 1) 生成输入
        try:
            with open(in_path, "wb") as fo:
                subprocess.run([gen_exe], cwd=outdir, stdout=fo,
                               timeout=timeout_ms / 1000.0)
        except subprocess.TimeoutExpired:
            rep("error", f"第{r}组: 生成器超时"); continue
        except Exception as e:
            rep("error", f"第{r}组: 生成器出错 {e}"); continue
        # 2) 答案程序跑出输出
        try:
            with open(in_path, "rb") as fi, open(out_path, "wb") as fo:
                subprocess.run([ans_exe], cwd=outdir, stdin=fi, stdout=fo,
                               timeout=timeout_ms / 1000.0)
        except subprocess.TimeoutExpired:
            rep("error", f"第{r}组: 答案程序超时"); continue
        except Exception as e:
            rep("error", f"第{r}组: 答案程序出错 {e}"); continue
        ok_count += 1
        rep("info", f"第{r}组: 已生成 {task}{r}.in 和 {task}{r}{ext}")

    # 清理
    for f in (gen_exe, ans_exe):
        try:
            if os.path.exists(f):
                os.remove(f)
        except Exception:
            pass
    rep("ok", f"造数据完成：成功 {ok_count}/{rounds} 组 → {outdir}")
    return ok_count, rounds


# ---------- 随机数据生成（按格式+范围，无需手写生成器） ----------
def _range_int(s):
    """把范围端点转成整数，支持 1e9 / -1e9 这类写法；失败返回 None。"""
    s = s.strip().replace("e", "E")
    try:
        return int(float(s))
    except Exception:
        return None


def parse_ranges(ranges_str):
    """解析「输入范围」为 {字母: (最小, 最大)}。支持 a=1~100 或 a 1 100 写法。"""
    res = {}
    if not ranges_str:
        return res
    for part in re.split(r"[;,，\s]+", ranges_str):
        part = part.strip()
        if not part:
            continue
        m = re.match(r"([A-Za-z])\s*=\s*(.+?)\s*[~～\-]\s*(.+)", part)
        if not m:
            m = re.match(r"([A-Za-z])\s+(.+?)\s+([^\s]+)\s*$", part)
        if m:
            v, a, b = m.group(1), m.group(2), m.group(3)
            lo, hi = _range_int(a), _range_int(b)
            if lo is not None and hi is not None:
                if lo > hi:
                    lo, hi = hi, lo
                res[v] = (lo, hi)
    return res


def parse_format(format_str):
    """解析「输入格式」为行列表。
    每行元素: ('single', [占位变量]) 或 ('repeat', ('var'|'num', 计数), [占位变量]).
    例： `{n}`            → 输出一行一个随机数 n
         `{n} 行: {a} {b}` → 按 n 的值重复输出多行，每行一个 a、一个 b
    """
    rows = []
    for raw in format_str.splitlines():
        line = raw.strip()
        if not line:
            continue
        colon = [loc for loc in (line.find(":"), line.find("：")) if loc != -1]
        if colon:
            idx = min(colon)
            left, right = line[:idx], line[idx + 1:]
            cm = re.search(r"\{([A-Za-z])\}", left)
            if cm:
                count = ("var", cm.group(1))
            else:
                dm = re.match(r"\s*(\d+)\s*", left)
                if dm:
                    count = ("num", int(dm.group(1)))
                else:
                    vm = re.search(r"([A-Za-z])", left)
                    count = ("var", vm.group(1)) if vm else ("num", 1)
            pattern = re.findall(r"\{([A-Za-z])\}", right)
            rows.append(("repeat", count, pattern))
        else:
            rows.append(("single", None, re.findall(r"\{([A-Za-z])\}", line)))
    return rows


def _rand_in(ranges, var, default=(1, 1000)):
    lo, hi = ranges.get(var, default)
    return random.randint(lo, hi)


def gen_one_input(rows, ranges):
    """按格式与范围生成一组随机输入文本。
    规则：出现在首行或作为重复次数的变量，同一组内只取一个值并全局复用；
    只出现在重复行数据里的变量（如每行的 a、b），每一行都重新随机。
    """
    global_vars = set()
    for kind, count, pattern in rows:
        if kind == "single":
            global_vars.update(pattern)
        else:
            if count[0] == "var":
                global_vars.add(count[1])
    gvals = {v: _rand_in(ranges, v) for v in global_vars}

    out = []
    for kind, count, pattern in rows:
        if kind == "single":
            out.append(" ".join(str(gvals[v]) for v in pattern))
        else:
            if count[0] == "var":
                c = gvals[count[1]]
            else:
                c = count[1]
            c = max(0, c)
            for _ in range(c):
                vals = []
                for v in pattern:
                    if v in gvals:
                        vals.append(str(gvals[v]))
                    else:
                        vals.append(str(_rand_in(ranges, v)))
                out.append(" ".join(vals))
    return "\n".join(out) + "\n"


def generate_random_data(format_str, ranges_str, count, ac_src, outdir, gxx, std, opt,
                         task="test", ext=".out", report=None, timeout_ms=10000):
    """
    随机造数据：按「输入格式/输入范围」生成随机 .in。
    AC 代码可选：提供了则编译并跑出 .out（可直接用于评测）；留空则只生成 .in。
    全程用标准输入输出（不用 freopen）。
    返回 (成功组数, 总组数)。
    """
    def rep(kind, msg):
        if report:
            report(kind, msg)

    rows = parse_format(format_str)
    ranges = parse_ranges(ranges_str)
    if not rows:
        rep("error", "输入格式无法解析（请用 {字母} 占位，如 {n} 或 {n} 行: {a} {b}）")
        return 0, 0
    if not os.path.isdir(outdir):
        os.makedirs(outdir, exist_ok=True)

    # AC 代码可选：留空则只出 .in，不出 .out
    ac_exe = None
    if ac_src.strip():
        ac_exe = os.path.join(outdir, "_random_ac.exe")
        p = compile_one(gxx, ac_src, ac_exe, std, opt)
        if p.returncode != 0:
            rep("error", "AC 代码编译失败:\n" + (p.stderr or p.stdout or "")[:500])
            return 0, 0

    ok = 0
    for i in range(1, count + 1):
        in_path = os.path.join(outdir, f"{task}{i}.in")
        out_path = os.path.join(outdir, f"{task}{i}{ext}")
        try:
            with open(in_path, "w", encoding="utf-8") as f:
                f.write(gen_one_input(rows, ranges))
        except Exception as e:
            rep("error", f"第{i}组: 写输入失败 {e}")
            continue
        if ac_exe is None:
            ok += 1
            rep("info", f"第{i}组: 已生成 {task}{i}.in（未提供 AC 代码，无 .out）")
            continue
        try:
            with open(in_path, "rb") as fi, open(out_path, "wb") as fo:
                subprocess.run([ac_exe], cwd=outdir, stdin=fi, stdout=fo,
                               timeout=timeout_ms / 1000.0)
        except subprocess.TimeoutExpired:
            rep("error", f"第{i}组: AC 运行超时")
            continue
        except Exception as e:
            rep("error", f"第{i}组: AC 运行出错 {e}")
            continue
        ok += 1
        rep("info", f"第{i}组: 已生成 {task}{i}.in 和 {task}{i}{ext}")

    try:
        if ac_exe and os.path.exists(ac_exe):
            os.remove(ac_exe)
    except Exception:
        pass
    rep("ok", f"随机数据完成：成功 {ok}/{count} 组 → {outdir}")
    return ok, count


def _read_text(path):
    for enc in ("utf-8", "gbk", "latin-1"):
        try:
            with open(path, "r", encoding=enc) as f:
                return f.read()
        except Exception:
            continue
    return ""


def _copy_file(src, dst):
    with open(src, "rb") as fi, open(dst, "wb") as fo:
        fo.write(fi.read())


def compile_one(gxx, src, exe, std, opt):
    """编译，返回 subprocess.run 结果。"""
    cmd = [gxx, "-o", exe, src, "-std=" + std]
    if opt:
        cmd.append("-O2")
    # g++ 中文诊断输出是系统代码页（cp936），用 mbcs 编码读，避免 utf-8 解码崩溃
    return subprocess.run(cmd, capture_output=True, text=True,
                          encoding="mbcs", errors="replace", timeout=120)


def evaluate_one(src, data, gxx, std, opt, score_per, report=None, timeout_ms=10000):
    """
    评测单题。report 为可选回调 report(label, status, score, ms, expect, actual)。
    返回 (ac_count, total_score, group_count)。
    """
    task = os.path.splitext(os.path.basename(src))[0]
    exe = os.path.join(data, task + ".exe")

    def rep(label, status, score, ms, expect, actual):
        if report:
            report(label, status, score, ms, expect, actual)

    # 编译
    p = compile_one(gxx, src, exe, std, opt)
    if p.returncode != 0:
        rep("编译", "CE", 0, 0, "", (p.stderr or p.stdout or "编译失败"))
        return 0, 0, 0

    # 收集样例
    ins = sorted(glob.glob(os.path.join(data, "*.in")), key=natural_key)
    if not ins:
        rep("数据", "无样例", 0, 0, "", "目录里没有 .in 文件")
        return 0, 0, 0

    total = 0
    ac = 0
    for in_f in ins:
        base = os.path.splitext(in_f)[0]
        ref = None
        for ext in (".out", ".ans"):
            cand = base + ext
            if os.path.isfile(cand):
                ref = cand
                break
        if not ref:
            rep(os.path.basename(base), "缺答案", 0, 0, "", "")
            continue

        tmp_in = os.path.join(data, task + ".in")
        tmp_out = os.path.join(data, task + ".out")
        _copy_file(in_f, tmp_in)
        if os.path.exists(tmp_out):
            os.remove(tmp_out)
        t0 = time.time()
        try:
            # 把输入经 stdin 喂给程序（兼容 cin/cout 写法；freopen 写法会忽略 stdin 读文件）
            with open(in_f, "rb") as fi:
                rp = subprocess.run([exe], cwd=data, stdin=fi,
                                    capture_output=True, timeout=timeout_ms / 1000.0)
        except subprocess.TimeoutExpired:
            rep(os.path.basename(base), "TLE", 0, int(timeout_ms), "", "超时")
            continue
        ms = int((time.time() - t0) * 1000)

        # 优先用 freopen 写出的 <task>.out；否则用标准输出（cin/cout 程序）
        mine = None
        if os.path.isfile(tmp_out):
            mine = _read_text(tmp_out).strip()
        elif rp.stdout:
            mine = rp.stdout.decode("utf-8", "replace").strip()
        if mine is None:
            rep(os.path.basename(base), "无输出", 0, ms, "", "")
            continue
        ans = _read_text(ref).strip()
        if mine == ans:
            ac += 1
            total += score_per
            rep(os.path.basename(base), "AC", score_per, ms, ans, mine)
        else:
            rep(os.path.basename(base), "WA", 0, ms, ans, mine)

    # 清理
    for tmp in (exe, tmp_in, tmp_out):
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except Exception:
            pass
    return ac, total, len(ins)


class JudgeApp:
    def __init__(self, root):
        self.root = root
        self.style = setup_style(root)
        root.title("OJJudge 评测软件")
        root.geometry("960x660")
        root.minsize(780, 540)
        root.configure(bg=BG)

        self.var_gxx = tk.StringVar(value=DEFAULT_GXX)
        self.var_std = tk.StringVar(value="c++14")
        self.var_opt = tk.BooleanVar(value=True)
        self.var_score = tk.IntVar(value=20)

        self._running = False
        build_header(root)
        # 线程安全：工作线程只把 UI 更新动作丢进队列，主线程轮询执行
        self._ui_queue = queue.Queue()
        self.root.after(80, self._poll_ui)
        self._nb = ttk.Notebook(root)
        self._nb.pack(fill="both", expand=True, padx=10, pady=(6, 0))
        self._build_single_tab()
        self._build_multi_tab()
        self._build_battle_tab()
        self._build_gen_tab()
        self._build_random_tab()
        # 评测记录（软件内持久化）
        self._records = load_records()
        self._battle_ok = None
        self._build_record_tab()
        # 启动时自动导入「题目导入.json」里预置的题目（如未配置则跳过）
        self._loaded_import_count = self._load_problem_import()

        # 底部通用选项：网页风卡片（白底 + 细描边 + 底部柔和投影线）
        bar = tk.Frame(root, bg=CARD, bd=0, highlightthickness=1, highlightbackground=BORDER)
        bar.pack(fill="x", padx=10, pady=(6, 2))
        bar_shadow = tk.Frame(root, bg="#e3e7f0", height=2)
        bar_shadow.pack(fill="x", padx=14, pady=(0, 8))
        ttk.Label(bar, text="编译器:", style="Card.TLabel").pack(side="left", padx=(10, 4), pady=8)
        ttk.Entry(bar, textvariable=self.var_gxx, width=46).pack(side="left", pady=8)
        ttk.Button(bar, text="浏览", command=self._pick_gxx).pack(side="left", padx=4, pady=8)
        ttk.Label(bar, text="标准:", style="Card.TLabel").pack(side="left", padx=(12, 4), pady=8)
        ttk.Combobox(bar, textvariable=self.var_std, width=7,
                     values=["c++11", "c++14", "c++17", "c++20"]).pack(side="left", pady=8)
        ttk.Checkbutton(bar, text="O2 优化", variable=self.var_opt, style="TCheckbutton").pack(side="left", padx=8, pady=8)
        ttk.Label(bar, text="每组分:", style="Card.TLabel").pack(side="left", padx=(8, 4), pady=8)
        ttk.Spinbox(bar, from_=1, to=100, textvariable=self.var_score, width=5).pack(side="left", pady=8)

    # ---------- 分区标题 ----------
    def _section_label(self, parent, text):
        """带左侧色条的分区标题，让界面分区更清晰。"""
        row = tk.Frame(parent, bg=BG)
        row.pack(fill="x", padx=12, pady=(10, 4))
        tk.Frame(row, bg=ACCENT, width=4, height=16).pack(side="left", pady=2)
        tk.Label(row, text=text, bg=BG, fg="#3a4256",
                 font=("微软雅黑", 11, "bold")).pack(side="left", padx=7)
        return row

    # ---------- 单题模式 ----------
    def _build_single_tab(self):
        tab = ttk.Frame(self._nb)
        self._nb.add(tab, text="  单题  ")
        pad = {"padx": 10, "pady": 5}
        self._section_label(tab, "源码与数据")

        r1 = ttk.Frame(tab); r1.pack(fill="x", **pad)
        ttk.Label(r1, text="源码(.cpp):").pack(side="left")
        self.var_src = tk.StringVar()
        ttk.Entry(r1, textvariable=self.var_src).pack(side="left", fill="x", expand=True, padx=6)
        ttk.Button(r1, text="浏览", command=lambda: self._pick_file(self.var_src)).pack(side="left")

        r2 = ttk.Frame(tab); r2.pack(fill="x", **pad)
        ttk.Label(r2, text="数据目录:").pack(side="left")
        self.var_data = tk.StringVar()
        ttk.Entry(r2, textvariable=self.var_data).pack(side="left", fill="x", expand=True, padx=6)
        ttk.Button(r2, text="浏览", command=lambda: self._pick_dir(self.var_data)).pack(side="left")

        r3 = ttk.Frame(tab); r3.pack(fill="x", **pad)
        self.btn_single = ttk.Button(r3, text="开始评测", style="Accent.TButton", command=self._start_single)
        self.btn_single.pack(side="left")
        self.status_single = ttk.Label(r3, text="就绪", style="Status.TLabel")
        self.status_single.pack(side="left", padx=12)

        self._section_label(tab, "评测结果")
        cols = ("组", "状态", "得分", "用时(ms)", "期望", "实际")
        self.tree_s = ttk.Treeview(tab, columns=cols, show="headings", height=14)
        for c in cols:
            self.tree_s.heading(c, text=c)
        self.tree_s.column("组", width=70, anchor="center")
        self.tree_s.column("状态", width=70, anchor="center")
        self.tree_s.column("得分", width=55, anchor="center")
        self.tree_s.column("用时(ms)", width=70, anchor="center")
        self.tree_s.column("期望", width=160, anchor="w")
        self.tree_s.column("实际", width=160, anchor="w")
        self.tree_s.tag_configure("AC", background="#e7f9f1", foreground=GREEN, font=("微软雅黑", 10, "bold"))
        self.tree_s.tag_configure("WA", background="#fdeeee", foreground=RED, font=("微软雅黑", 10, "bold"))
        self.tree_s.tag_configure("other", background="#fdf3e3", foreground=AMBER)
        self.tree_s.tag_configure("alt", background=ROW_ALT)
        self.tree_s.pack(fill="both", expand=True, padx=10, pady=2)
        sb = ttk.Scrollbar(tab, command=self.tree_s.yview)
        self.tree_s.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.total_s = tk.Label(tab, text="总分: - / -", font=("微软雅黑", 13, "bold"),
                                bg=BG, fg=PRIMARY, anchor="w")
        self.total_s.pack(fill="x", padx=12, pady=6)

    # ---------- 多题模式 ----------
    def _build_multi_tab(self):
        tab = ttk.Frame(self._nb)
        self._nb.add(tab, text="  多题  ")
        pad = {"padx": 10, "pady": 5}

        bar = ttk.Frame(tab); bar.pack(fill="x", **pad)
        ttk.Button(bar, text="添加题目", command=self._add_problem).pack(side="left")
        ttk.Button(bar, text="导入题目", command=self._import_problems_dialog).pack(side="left", padx=6)
        ttk.Button(bar, text="删除选中", style="Danger.TButton",
                   command=self._del_problem).pack(side="left", padx=6)
        ttk.Button(bar, text="清空列表", command=self._clear_problems).pack(side="left", padx=6)
        ttk.Button(bar, text="开始评测全部", style="Accent.TButton",
                   command=self._start_multi).pack(side="left", padx=10)
        self.status_multi = ttk.Label(bar, text="就绪（0 题）", style="Status.TLabel")
        self.status_multi.pack(side="left", padx=12)

        # 题目列表
        self._section_label(tab, "题目列表")
        self.problem_tree = ttk.Treeview(tab, columns=("题名", "源码", "数据目录"),
                                         show="headings", height=5)
        for c, w in (("题名", 90), ("源码", 300), ("数据目录", 300)):
            self.problem_tree.heading(c, text=c)
            self.problem_tree.column(c, width=w, anchor="w")
        self.problem_tree.pack(fill="x", padx=10, pady=2)


        # 结果表格
        self._section_label(tab, "评测结果")
        cols = ("题", "组", "状态", "得分", "用时(ms)", "期望", "实际")
        self.tree_m = ttk.Treeview(tab, columns=cols, show="headings", height=9)
        for c in cols:
            self.tree_m.heading(c, text=c)
        self.tree_m.column("题", width=90, anchor="w")
        self.tree_m.column("组", width=90, anchor="center")
        self.tree_m.column("状态", width=70, anchor="center")
        self.tree_m.column("得分", width=55, anchor="center")
        self.tree_m.column("用时(ms)", width=70, anchor="center")
        self.tree_m.column("期望", width=120, anchor="w")
        self.tree_m.column("实际", width=120, anchor="w")
        self.tree_m.tag_configure("AC", background="#e7f9f1", foreground=GREEN, font=("微软雅黑", 10, "bold"))
        self.tree_m.tag_configure("WA", background="#fdeeee", foreground=RED, font=("微软雅黑", 10, "bold"))
        self.tree_m.tag_configure("other", background="#fdf3e3", foreground=AMBER)
        self.tree_m.pack(fill="both", expand=True, padx=10, pady=2)
        self.total_m = tk.Label(tab, text="汇总: - / -", font=("微软雅黑", 13, "bold"),
                                bg=BG, fg=PRIMARY, anchor="w")
        self.total_m.pack(fill="x", padx=12, pady=6)

    # ---------- 工具 ----------
    def _pick_gxx(self):
        f = filedialog.askopenfilename(title="选择编译器 g++.exe", filetypes=[("可执行文件", "*.exe")])
        if f:
            self.var_gxx.set(f)

    def _pick_file(self, var):
        f = filedialog.askopenfilename(title="选择文件", filetypes=[("C++ 源码", "*.cpp"), ("所有文件", "*.*")])
        if f:
            var.set(f)

    def _pick_dir(self, var):
        d = filedialog.askdirectory(title="选择目录")
        if d:
            var.set(d)

    # ---------- 对拍模式 ----------
    def _build_battle_tab(self):
        tab = ttk.Frame(self._nb)
        self._nb.add(tab, text="  对拍  ")
        pad = {"padx": 10, "pady": 5}
        self._section_label(tab, "参数设置")

        r1 = ttk.Frame(tab); r1.pack(fill="x", **pad)
        ttk.Label(r1, text="主程序(.cpp):").pack(side="left")
        self.var_b_main = tk.StringVar()
        ttk.Entry(r1, textvariable=self.var_b_main).pack(side="left", fill="x", expand=True, padx=6)
        ttk.Button(r1, text="浏览", command=lambda: self._pick_file(self.var_b_main)).pack(side="left")

        r2 = ttk.Frame(tab); r2.pack(fill="x", **pad)
        ttk.Label(r2, text="暴力/标程(.cpp):").pack(side="left")
        self.var_b_brute = tk.StringVar()
        ttk.Entry(r2, textvariable=self.var_b_brute).pack(side="left", fill="x", expand=True, padx=6)
        ttk.Button(r2, text="浏览", command=lambda: self._pick_file(self.var_b_brute)).pack(side="left")

        r3 = ttk.Frame(tab); r3.pack(fill="x", **pad)
        ttk.Label(r3, text="数据生成器(.cpp):").pack(side="left")
        self.var_b_gen = tk.StringVar()
        ttk.Entry(r3, textvariable=self.var_b_gen).pack(side="left", fill="x", expand=True, padx=6)
        ttk.Button(r3, text="浏览", command=lambda: self._pick_file(self.var_b_gen)).pack(side="left")

        r4 = ttk.Frame(tab); r4.pack(fill="x", **pad)
        ttk.Label(r4, text="对拍轮数:").pack(side="left")
        self.var_b_rounds = tk.IntVar(value=100)
        ttk.Spinbox(r4, from_=1, to=100000, textvariable=self.var_b_rounds, width=8).pack(side="left", padx=6)
        self.btn_battle = ttk.Button(r4, text="开始对拍", style="Accent.TButton", command=self._start_battle)
        self.btn_battle.pack(side="left", padx=12)
        self.status_battle = ttk.Label(r4, text="就绪", style="Status.TLabel")
        self.status_battle.pack(side="left", padx=6)

        # 说明
        tip = ("对拍说明：数据生成器每轮生成一组随机输入，主程序与暴力/标程分别运行并比对输出；\n"
               "三者约定通过标准输入输出读写（生成器往 stdout 写数据，主/暴力从 stdin 读并往 stdout 写）。\n"
               "若你的程序用了 freopen 读写固定文件名，请改用标准输入输出，否则无法对拍。")
        ttk.Label(tab, text=tip, style="Hint.TLabel", wraplength=780, justify="left").pack(anchor="w", padx=10)

        # 日志
        self._section_label(tab, "对拍日志")
        self.battle_log = tk.Text(tab, height=12, state="disabled", wrap="word",
                                  bg="#0f172a", fg="#e2e8f0",
                                  insertbackground="#e2e8f0", relief="flat",
                                  font=("Consolas", 10), padx=8, pady=6)
        self.battle_log.pack(fill="both", expand=True, padx=10, pady=4)
        self.battle_log.tag_configure("ok", foreground="#4ade80")
        self.battle_log.tag_configure("fail", foreground="#f87171")
        self.battle_log.tag_configure("err", foreground="#fbbf24")
        sb = ttk.Scrollbar(tab, command=self.battle_log.yview)
        self.battle_log.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")

    def _battle_log_append(self, msg, tag=None):
        self.battle_log.configure(state="normal")
        self.battle_log.insert("end", msg + "\n", tag)
        self.battle_log.see("end")
        self.battle_log.configure(state="disabled")

    def _start_battle(self):
        if self._running:
            return
        main = self.var_b_main.get().strip()
        brute = self.var_b_brute.get().strip()
        gen = self.var_b_gen.get().strip()
        gxx = self.var_gxx.get().strip()
        if not main or not brute or not gen or not gxx:
            messagebox.showwarning("提示", "主程序/暴力/生成器/编译器都要填")
            return
        for label, p in (("主程序", main), ("暴力", brute), ("生成器", gen)):
            if not os.path.isfile(p):
                messagebox.showwarning("提示", f"{label}文件不存在: {p}")
                return
        rounds = max(1, self.var_b_rounds.get())

        self._running = True
        self.btn_battle.state(["disabled"])
        self.battle_log.configure(state="normal")
        self.battle_log.delete("1.0", "end")
        self.battle_log.configure(state="disabled")
        self.status_battle.config(text="对拍中...")
        std = self.var_std.get().strip() or "c++14"
        opt = self.var_opt.get()
        threading.Thread(target=self._run_battle, args=(main, brute, gen, rounds, gxx, std, opt), daemon=True).start()

    def _run_battle(self, main, brute, gen, rounds, gxx, std, opt):
        workdir = os.path.join(os.path.dirname(main), "_battle_tmp")
        os.makedirs(workdir, exist_ok=True)

        def rep(kind, msg):
            if kind == "info":
                self._ui(lambda m=msg: (self._battle_log_append(m, "ok"),
                                        self.status_battle.config(text="对拍中")))
            elif kind == "warn":
                # 每一处不一致/异常：记录到日志，但继续对拍，不弹窗
                self._ui(lambda m=msg: self._battle_log_append(m, "fail"))
            elif kind in ("fail", "error"):
                tag = "fail" if kind == "fail" else "err"
                self._ui(lambda m=msg, t=tag: (self._battle_log_append(m, t),
                                               self.status_battle.config(text="发现问题"),
                                               messagebox.showwarning("对拍发现不一致", m)))
            else:
                self._ui(lambda m=msg: (self._battle_log_append(m, "ok"),
                                        self.status_battle.config(text="通过")))

        try:
            ok = run_battle(main, brute, gen, gxx, std, opt, rounds, workdir, report=rep)
            self._battle_ok = ok
        except Exception as e:
            self._battle_ok = None
            self._ui(lambda: messagebox.showerror("错误", str(e)))
        finally:
            self._ui(self._battle_done)
            # 清理临时文件（保留最后一份 data 便于查看）
            for f in ("_gen.exe", "_main.exe", "_brute.exe", "main.out", "brute.out"):
                try:
                    p = os.path.join(workdir, f)
                    if os.path.exists(p):
                        os.remove(p)
                except Exception:
                    pass

    def _battle_done(self):
        self._running = False
        self.btn_battle.state(["!disabled"])
        ok = self._battle_ok
        summary = ("对拍全部一致" if ok else ("对拍发现问题" if ok is False else "对拍异常"))
        detail = self.battle_log.get("1.0", "end").strip()
        self._add_eval_record("对拍", summary, detail)
        self._battle_ok = None

    # ---------- 造数据模式 ----------
    def _build_gen_tab(self):
        tab = ttk.Frame(self._nb)
        self._nb.add(tab, text="  造数据  ")
        pad = {"padx": 10, "pady": 5}
        self._section_label(tab, "参数设置")

        r1 = ttk.Frame(tab); r1.pack(fill="x", **pad)
        ttk.Label(r1, text="题名前缀:").pack(side="left")
        self.var_g_task = tk.StringVar(value="test")
        ttk.Entry(r1, textvariable=self.var_g_task, width=12).pack(side="left", padx=6)
        ttk.Label(r1, text="输出目录:").pack(side="left")
        self.var_g_dir = tk.StringVar()
        ttk.Entry(r1, textvariable=self.var_g_dir).pack(side="left", fill="x", expand=True, padx=6)
        ttk.Button(r1, text="浏览", command=lambda: self._pick_dir(self.var_g_dir)).pack(side="left")

        r2 = ttk.Frame(tab); r2.pack(fill="x", **pad)
        ttk.Label(r2, text="数据生成器(.cpp):").pack(side="left")
        self.var_g_gen = tk.StringVar()
        ttk.Entry(r2, textvariable=self.var_g_gen).pack(side="left", fill="x", expand=True, padx=6)
        ttk.Button(r2, text="浏览", command=lambda: self._pick_file(self.var_g_gen)).pack(side="left")

        r3 = ttk.Frame(tab); r3.pack(fill="x", **pad)
        ttk.Label(r3, text="答案程序(.cpp):").pack(side="left")
        self.var_g_ans = tk.StringVar()
        ttk.Entry(r3, textvariable=self.var_g_ans).pack(side="left", fill="x", expand=True, padx=6)
        ttk.Button(r3, text="浏览", command=lambda: self._pick_file(self.var_g_ans)).pack(side="left")

        r4 = ttk.Frame(tab); r4.pack(fill="x", **pad)
        ttk.Label(r4, text="组数:").pack(side="left")
        self.var_g_rounds = tk.IntVar(value=10)
        ttk.Spinbox(r4, from_=1, to=1000, textvariable=self.var_g_rounds, width=6).pack(side="left", padx=6)
        ttk.Label(r4, text="答案后缀:").pack(side="left")
        self.var_g_ext = tk.StringVar(value=".out")
        ttk.Combobox(r4, textvariable=self.var_g_ext, width=6,
                     values=[".out", ".ans"]).pack(side="left", padx=6)
        self.btn_gen = ttk.Button(r4, text="开始生成", style="Accent.TButton", command=self._start_gen)
        self.btn_gen.pack(side="left", padx=12)
        self.status_gen = ttk.Label(r4, text="就绪", style="Status.TLabel")
        self.status_gen.pack(side="left", padx=6)

        tip = ("造数据说明：数据生成器每轮造一组随机输入（往 stdout 写），存为 <前缀><n>.in；\n"
               "答案程序读取该输入（stdin）、往 stdout 写答案，存为 <前缀><n>.out/.ans。\n"
               "生成的数据即可用于「单题/多题」评测。若已有同名文件会被覆盖。")
        ttk.Label(tab, text=tip, style="Hint.TLabel", wraplength=780, justify="left").pack(anchor="w", padx=10)

        self._section_label(tab, "生成日志")
        self.gen_log = tk.Text(tab, height=12, state="disabled", wrap="word",
                               bg="#0f172a", fg="#e2e8f0", insertbackground="#e2e8f0",
                               relief="flat", font=("Consolas", 10), padx=8, pady=6)
        self.gen_log.pack(fill="both", expand=True, padx=10, pady=4)
        self.gen_log.tag_configure("ok", foreground="#4ade80")
        self.gen_log.tag_configure("err", foreground="#fbbf24")
        sb = ttk.Scrollbar(tab, command=self.gen_log.yview)
        self.gen_log.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")

    def _gen_log_append(self, msg, tag=None):
        self.gen_log.configure(state="normal")
        self.gen_log.insert("end", msg + "\n", tag)
        self.gen_log.see("end")
        self.gen_log.configure(state="disabled")

    def _start_gen(self):
        if self._running:
            return
        task = self.var_g_task.get().strip() or "test"
        outdir = self.var_g_dir.get().strip()
        gen = self.var_g_gen.get().strip()
        ans = self.var_g_ans.get().strip()
        gxx = self.var_gxx.get().strip()
        if not outdir or not gen or not ans or not gxx:
            messagebox.showwarning("提示", "输出目录/生成器/答案程序/编译器都要填")
            return
        for label, p in (("生成器", gen), ("答案程序", ans)):
            if not os.path.isfile(p):
                messagebox.showwarning("提示", f"{label}文件不存在: {p}")
                return
        rounds = max(1, self.var_g_rounds.get())

        self._running = True
        self.btn_gen.state(["disabled"])
        self.gen_log.configure(state="normal")
        self.gen_log.delete("1.0", "end")
        self.gen_log.configure(state="disabled")
        self.status_gen.config(text="生成中...")
        std = self.var_std.get().strip() or "c++14"
        opt = self.var_opt.get()
        ext = self.var_g_ext.get().strip() or ".out"
        threading.Thread(target=self._run_gen, args=(task, outdir, gen, ans, rounds, gxx, std, opt, ext), daemon=True).start()

    def _run_gen(self, task, outdir, gen, ans, rounds, gxx, std, opt, ext):
        def rep(kind, msg):
            if kind == "info":
                self._ui(lambda m=msg: (self._gen_log_append(m, "ok"),
                                        self.status_gen.config(text="生成中")))
            elif kind in ("fail", "error"):
                self._ui(lambda m=msg: (self._gen_log_append("【错误】" + m, "err"),
                                        self.status_gen.config(text="出错")))
            else:
                self._ui(lambda m=msg: (self._gen_log_append(m, "ok"),
                                        self.status_gen.config(text="完成")))

        try:
            generate_data(gen, ans, task, rounds, outdir, gxx, std, opt,
                          ext=ext, report=rep)
        except Exception as e:
            self._ui(lambda: messagebox.showerror("错误", str(e)))
        finally:
            self._ui(self._gen_done)

    def _gen_done(self):
        self._running = False
        self.btn_gen.state(["!disabled"])
        detail = self.gen_log.get("1.0", "end").strip()
        self._add_eval_record("造数据", "造数据完成", detail)

    # ---------- 随机数据模式（按格式+范围，无需手写生成器） ----------
    def _build_random_tab(self):
        tab = ttk.Frame(self._nb)
        self._nb.add(tab, text="  随机数据  ")
        pad = {"padx": 10, "pady": 4}
        self._section_label(tab, "输入格式")

        r0 = ttk.Frame(tab); r0.pack(fill="x", **pad)
        ttk.Label(r0, text="输入格式：").pack(side="left")
        self.var_r_format = tk.Text(r0, width=60, height=3, wrap="none",
                                    bg="#ffffff", fg="#2b3344",
                                    insertbackground=PRIMARY, relief="flat",
                                    highlightbackground=BORDER, highlightthickness=1,
                                    font=("Consolas", 10), padx=6, pady=4)
        self.var_r_format.pack(side="left", fill="x", expand=True, padx=6)
        self.var_r_format.insert("1.0", "{n}\n{n} 行: {a} {b}")

        r1 = ttk.Frame(tab); r1.pack(fill="x", **pad)
        ttk.Label(r1, text="输入范围：").pack(side="left")
        self.var_r_range = tk.StringVar(value="n=1~100000 a=-1e9~1e9 b=-1e9~1e9")
        ttk.Entry(r1, textvariable=self.var_r_range).pack(side="left", fill="x", expand=True, padx=6)

        r2 = ttk.Frame(tab); r2.pack(fill="x", **pad)
        ttk.Label(r2, text="AC 代码(.cpp)（可留空）:").pack(side="left")
        self.var_r_ac = tk.StringVar()
        ttk.Entry(r2, textvariable=self.var_r_ac).pack(side="left", fill="x", expand=True, padx=6)
        ttk.Button(r2, text="浏览", command=lambda: self._pick_file(self.var_r_ac)).pack(side="left")

        r3 = ttk.Frame(tab); r3.pack(fill="x", **pad)
        ttk.Label(r3, text="生成位置:").pack(side="left")
        self.var_r_dir = tk.StringVar()
        ttk.Entry(r3, textvariable=self.var_r_dir).pack(side="left", fill="x", expand=True, padx=6)
        ttk.Button(r3, text="浏览", command=lambda: self._pick_dir(self.var_r_dir)).pack(side="left")

        r4 = ttk.Frame(tab); r4.pack(fill="x", **pad)
        ttk.Label(r4, text="数量:").pack(side="left")
        self.var_r_count = tk.IntVar(value=20)
        ttk.Spinbox(r4, from_=1, to=1000, textvariable=self.var_r_count, width=6).pack(side="left", padx=6)
        ttk.Label(r4, text="前缀:").pack(side="left")
        self.var_r_task = tk.StringVar(value="test")
        ttk.Entry(r4, textvariable=self.var_r_task, width=8).pack(side="left", padx=6)
        ttk.Label(r4, text="后缀:").pack(side="left")
        self.var_r_ext = tk.StringVar(value=".out")
        ttk.Combobox(r4, textvariable=self.var_r_ext, width=6,
                     values=[".out", ".ans"]).pack(side="left", padx=6)
        self.btn_random = ttk.Button(r4, text="开始生成", style="Accent.TButton",
                                     command=self._start_random)
        self.btn_random.pack(side="left", padx=12)
        self.status_random = ttk.Label(r4, text="就绪", style="Status.TLabel")
        self.status_random.pack(side="left", padx=6)

        tip = ("格式说明：{字母} 表示随机数，空格分隔；单行 `{n} {m}` 输出一行；"
               "重复用 `{n} 行: {a} {b}` 表示按 n 的值输出多行。\n"
               "范围用 `字母=最小~最大`（支持 1e9），多个用空格分开。"
               "AC 代码编译后对每组输入跑出 .out，走标准输入输出（不用 freopen）。")
        ttk.Label(tab, text=tip, style="Hint.TLabel", wraplength=820,
                  justify="left").pack(anchor="w", padx=10, pady=(2, 2))

        self._section_label(tab, "生成日志")
        self.random_log = tk.Text(tab, height=10, state="disabled", wrap="word",
                                  bg="#0f172a", fg="#e2e8f0", insertbackground="#e2e8f0",
                                  relief="flat", font=("Consolas", 10), padx=8, pady=6)
        self.random_log.pack(fill="both", expand=True, padx=10, pady=4)
        self.random_log.tag_configure("ok", foreground="#4ade80")
        self.random_log.tag_configure("err", foreground="#fbbf24")
        sb = ttk.Scrollbar(tab, command=self.random_log.yview)
        self.random_log.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")

    def _random_log_append(self, msg, tag=None):
        self.random_log.configure(state="normal")
        self.random_log.insert("end", msg + "\n", tag)
        self.random_log.see("end")
        self.random_log.configure(state="disabled")

    def _start_random(self):
        if self._running:
            return
        fmt = self.var_r_format.get("1.0", "end")
        rng = self.var_r_range.get().strip()
        ac = self.var_r_ac.get().strip()
        outdir = self.var_r_dir.get().strip()
        gxx = self.var_gxx.get().strip()
        if not fmt.strip() or not outdir or not gxx:
            messagebox.showwarning("提示", "输入格式 / 生成位置 / 编译器 都要填")
            return
        if ac and not os.path.isfile(ac):
            messagebox.showwarning("提示", "AC 代码文件不存在: " + ac)
            return
        count = max(1, self.var_r_count.get())

        self._running = True
        self.btn_random.state(["disabled"])
        self.random_log.configure(state="normal")
        self.random_log.delete("1.0", "end")
        self.random_log.configure(state="disabled")
        self.status_random.config(text="生成中...")
        std = self.var_std.get().strip() or "c++14"
        opt = self.var_opt.get()
        task = self.var_r_task.get().strip() or "test"
        ext = self.var_r_ext.get().strip() or ".out"
        threading.Thread(target=self._run_random,
                         args=(fmt, rng, count, ac, outdir, gxx, std, opt, task, ext), daemon=True).start()

    def _run_random(self, fmt, rng, count, ac, outdir, gxx, std, opt, task, ext):
        def rep(kind, msg):
            if kind == "info":
                self._ui(lambda m=msg: (self._random_log_append(m, "ok"),
                                        self.status_random.config(text="生成中")))
            elif kind in ("fail", "error"):
                self._ui(lambda m=msg: (self._random_log_append("【错误】" + m, "err"),
                                        self.status_random.config(text="出错")))
            else:
                self._ui(lambda m=msg: (self._random_log_append(m, "ok"),
                                        self.status_random.config(text="完成")))

        try:
            generate_random_data(fmt, rng, count, ac, outdir, gxx, std, opt,
                                 task=task, ext=ext, report=rep)
        except Exception as e:
            self._ui(lambda: messagebox.showerror("错误", str(e)))
        finally:
            self._ui(self._random_done)

    def _random_done(self):
        self._running = False
        self.btn_random.state(["!disabled"])
        detail = self.random_log.get("1.0", "end").strip()
        self._add_eval_record("随机数据", "随机数据完成", detail)

    # ---------- 记录页（评测记录 + 改动日志） ----------
    def _build_record_tab(self):
        tab = ttk.Frame(self._nb)
        self._nb.add(tab, text="  记录  ")
        pad = {"padx": 10, "pady": 5}

        bar = ttk.Frame(tab); bar.pack(fill="x", **pad)
        self.btn_rec_evals = ttk.Button(bar, text="评测记录", command=lambda: self._show_record_view("evals"))
        self.btn_rec_log = ttk.Button(bar, text="改动日志", command=lambda: self._show_record_view("log"))
        self.btn_rec_evals.pack(side="left")
        self.btn_rec_log.pack(side="left", padx=6)
        ttk.Button(bar, text="清空记录", style="Danger.TButton",
                   command=self._clear_records).pack(side="left", padx=6)
        self.rec_status = ttk.Label(bar, text=f"评测记录 {len(self._records)} 条", style="Status.TLabel")
        self.rec_status.pack(side="left", padx=12)

        self._section_label(tab, "记录列表")
        self.rec_tree = ttk.Treeview(tab, columns=("时间", "模式", "结果"), show="headings", height=8)
        for c, w in (("时间", 150), ("模式", 60), ("结果", 440)):
            self.rec_tree.heading(c, text=c)
            self.rec_tree.column(c, width=w, anchor="w")
        self.rec_tree.pack(fill="x", padx=10, pady=2)
        self.rec_tree.bind("<<TreeviewSelect>>", self._on_rec_select)

        self._section_label(tab, "详情 / 日志")
        self.rec_detail = tk.Text(tab, bg="#0f172a", fg="#e2e8f0", font=("Consolas", 10),
                                  state="disabled", height=12, wrap="none")
        self.rec_detail.pack(fill="both", expand=True, padx=10, pady=2)
        self.rec_detail.tag_configure("ok", foreground="#4ade80")
        self.rec_detail.tag_configure("err", foreground="#fbbf24")

        self._refresh_record_tree()
        self._show_record_view("evals")

    def _refresh_record_tree(self):
        for i in self.rec_tree.get_children():
            self.rec_tree.delete(i)
        # 最新的放最上面
        for rec in reversed(self._records):
            self.rec_tree.insert("", "end", values=(
                rec.get("time", ""), rec.get("mode", ""), rec.get("summary", "")))
        self.rec_status.config(text=f"评测记录 {len(self._records)} 条")

    def _on_rec_select(self, event=None):
        sel = self.rec_tree.selection()
        if not sel:
            return
        idx = self.rec_tree.index(sel[0])
        rec = list(reversed(self._records))[idx]
        self._set_detail(rec.get("detail", rec.get("summary", "")))

    def _show_record_view(self, view):
        if view == "log":
            self.rec_tree.pack_forget()
            self._set_detail(CHANGELOG)
        else:
            self.rec_tree.pack(fill="x", padx=10, pady=2)
            sel = self.rec_tree.selection()
            if sel:
                self._on_rec_select()

    def _set_detail(self, text):
        self.rec_detail.configure(state="normal")
        self.rec_detail.delete("1.0", "end")
        self.rec_detail.insert("1.0", text)
        self.rec_detail.configure(state="disabled")

    def _add_eval_record(self, mode, summary, detail=""):
        self._records.append({"time": time.strftime("%Y-%m-%d %H:%M:%S"),
                              "mode": mode, "summary": summary, "detail": detail})
        save_records(self._records)
        self._refresh_record_tree()

    def _clear_records(self):
        if not self._records:
            return
        if not messagebox.askyesno("清空记录", "确定清空全部评测记录？"):
            return
        self._records = []
        save_records(self._records)
        self._refresh_record_tree()
        self._set_detail("")

    # ---------- 单题评测 ----------
    def _poll_ui(self):
        """主线程轮询 UI 队列，执行工作线程丢来的界面更新。"""
        try:
            while True:
                fn = self._ui_queue.get_nowait()
                fn()
        except queue.Empty:
            pass
        except Exception:
            pass
        self.root.after(80, self._poll_ui)

    def _ui(self, fn):
        """工作线程安全地把界面更新交给主线程执行。"""
        self._ui_queue.put(fn)

    def _start_single(self):
        if self._running:
            return
        src = self.var_src.get().strip()
        data = self.var_data.get().strip()
        gxx = self.var_gxx.get().strip()
        if not self._validate(src, data, gxx):
            return
        self._running = True
        self.btn_single.state(["disabled"])
        self.status_single.config(text="评测中...")
        for i in self.tree_s.get_children():
            self.tree_s.delete(i)
        self.total_s.config(text="总分: 评测中...")
        std = self.var_std.get().strip() or "c++14"
        opt = self.var_opt.get()
        sp = self.var_score.get()
        threading.Thread(target=self._run_single, args=(src, data, gxx, std, opt, sp), daemon=True).start()

    def _run_single(self, src, data, gxx, std, opt, sp):
        def rep(label, status, score, ms, expect, actual):
            tag = "AC" if status == "AC" else ("WA" if status == "WA" else "other")
            self._ui(lambda l=label, s=status, sc=score, m=ms, e=expect, a=actual, t=tag:
                     self.tree_s.insert("", "end", values=(l, s, sc, m, e, a), tags=(t,)))

        ac, total, n = evaluate_one(src, data, gxx, std, opt, sp, report=rep)
        self._ui(lambda t=total, a=ac, g=n: self._done_single(t, a, g))

    def _done_single(self, total, ac, n):
        self._running = False
        self.btn_single.state(["!disabled"])
        self.status_single.config(text="完成")
        sp = self.var_score.get()
        self.total_s.config(text=f"总分: {total} / {n * sp}   （{ac}/{n} 组 AC）")
        detail = "\n".join("  ".join(str(v) for v in self.tree_s.item(i, "values"))
                           for i in self.tree_s.get_children())
        self._add_eval_record("单题", f"总分 {total}/{n*sp}（{ac}/{n} AC）", detail)

    # ---------- 多题评测 ----------
    def _add_problem(self):
        # 用一个简单对话框收集题名/源码/数据目录
        dlg = tk.Toplevel(self.root)
        dlg.title("添加题目")
        dlg.geometry("520x160")
        dlg.transient(self.root)
        dlg.grab_set()
        name = tk.StringVar(value=f"题{self.problem_tree.get_children().__len__()+1}")
        src = tk.StringVar()
        data = tk.StringVar()
        r = ttk.Frame(dlg); r.pack(fill="x", padx=8, pady=4)
        ttk.Label(r, text="题名:").pack(side="left"); ttk.Entry(r, textvariable=name).pack(side="left", fill="x", expand=True)
        r = ttk.Frame(dlg); r.pack(fill="x", padx=8, pady=4)
        ttk.Label(r, text="源码:").pack(side="left"); ttk.Entry(r, textvariable=src).pack(side="left", fill="x", expand=True)
        ttk.Button(r, text="浏览", command=lambda: self._pick_file(src)).pack(side="left", padx=4)
        r = ttk.Frame(dlg); r.pack(fill="x", padx=8, pady=4)
        ttk.Label(r, text="数据:").pack(side="left"); ttk.Entry(r, textvariable=data).pack(side="left", fill="x", expand=True)
        ttk.Button(r, text="浏览", command=lambda: self._pick_dir(data)).pack(side="left", padx=4)
        btns = ttk.Frame(dlg); btns.pack(fill="x", padx=8, pady=6)
        def ok():
            if name.get().strip() and src.get().strip() and data.get().strip():
                self.problem_tree.insert("", "end",
                    values=(name.get().strip(), src.get().strip(), data.get().strip()))
                self._refresh_status_multi()
                dlg.destroy()
            else:
                messagebox.showwarning("提示", "题名/源码/数据目录都要填")
        ttk.Button(btns, text="确定", command=ok).pack(side="left")
        ttk.Button(btns, text="取消", command=dlg.destroy).pack(side="left", padx=6)

    def _del_problem(self):
        sel = self.problem_tree.selection()
        for i in sel:
            self.problem_tree.delete(i)
        self._refresh_status_multi()

    def _clear_problems(self):
        for i in self.problem_tree.get_children():
            self.problem_tree.delete(i)
        self._refresh_status_multi()

    def _import_problems_dialog(self):
        """手动导入：选择一个「题目导入.json」文件填入列表。"""
        path = filedialog.askopenfilename(
            title="选择题目导入文件", filetypes=[("JSON 导入文件", "*.json"), ("所有文件", "*.*")])
        if not path:
            return
        n = self._load_problem_import(path)
        if n >= 0:
            messagebox.showinfo("导入完成", f"已导入 {n} 道题。")

    def _load_problem_import(self, path=None):
        """从 JSON 导入题目到多题列表，返回导入的题数；文件不存在返回 0，解析失败返回 -1。"""
        path = path or _default_import_path()
        if not os.path.isfile(path):
            return 0
        try:
            with open(path, "r", encoding="utf-8") as f:
                entries = json.load(f)
        except Exception as e:
            messagebox.showwarning("导入失败", f"导入文件读取失败：\n{e}")
            return -1
        count = 0
        for e in entries:
            if not isinstance(e, dict):
                continue
            name = str(e.get("name", "")).strip()
            src = str(e.get("src", "")).strip()
            data = str(e.get("data", "")).strip()
            if name and src and data:
                self.problem_tree.insert("", "end", values=(name, src, data))
                count += 1
        self._refresh_status_multi()
        return count

    def _refresh_status_multi(self):
        n = len(self.problem_tree.get_children())
        self.status_multi.config(text=f"就绪（{n} 题）")

    def _start_multi(self):
        if self._running:
            return
        probs = []
        for i in self.problem_tree.get_children():
            vals = self.problem_tree.item(i, "values")
            probs.append((vals[0], vals[1], vals[2]))
        if not probs:
            messagebox.showwarning("提示", "请先添加题目")
            return
        for name, src, data in probs:
            if not self._validate(src, data, self.var_gxx.get().strip(), quiet=True):
                return
        self._running = True
        self.status_multi.config(text="评测中...")
        for i in self.tree_m.get_children():
            self.tree_m.delete(i)
        self.total_m.config(text="汇总: 评测中...")
        gxx = self.var_gxx.get().strip()
        std = self.var_std.get().strip() or "c++14"
        opt = self.var_opt.get()
        sp = self.var_score.get()
        threading.Thread(target=self._run_multi, args=(probs, gxx, std, opt, sp), daemon=True).start()

    def _run_multi(self, probs, gxx, std, opt, sp):
        grand_ac = 0
        grand_total = 0
        grand_groups = 0
        lines = []

        def rep(name, label, status, score, ms, expect, actual):
            tag = "AC" if status == "AC" else ("WA" if status == "WA" else "other")
            self._ui(lambda n=name, l=label, s=status, sc=score, m=ms, e=expect, a=actual, t=tag:
                     self.tree_m.insert("", "end", values=(n, l, s, sc, m, e, a), tags=(t,)))

        for name, src, data in probs:
            self._ui(lambda n=name: self.status_multi.config(text=f"评测中: {n}"))
            try:
                ac, total, n = evaluate_one(src, data, gxx, std, opt, sp,
                                            report=lambda l, s, sc, m, e, a, _n=name: rep(_n, l, s, sc, m, e, a))
            except Exception as ex:
                # 单题评测异常不中断后续题目
                self._ui(lambda nm=name, err=ex: self.tree_m.insert(
                    "", "end", values=(nm, "评测异常", 0, 0, "", str(err)), tags=("other",)))
                ac, total, n = 0, 0, 0
            grand_ac += ac
            grand_total += total
            grand_groups += n
            lines.append((name, ac, total, n))

        def finish():
            self._running = False
            self.status_multi.config(text="完成")
            detail = "  ".join(f"{n}:{a}/{c} AC({t}分)" for n, a, t, c in lines)
            self.total_m.config(text=f"汇总: {grand_total}/{grand_groups*sp}   （{grand_ac}/{grand_groups} 组 AC）")
            self._summary_multi = detail
            rows = "\n".join("  ".join(str(v) for v in self.tree_m.item(i, "values"))
                             for i in self.tree_m.get_children())
            self._add_eval_record("多题", f"汇总 {grand_total}/{grand_groups*sp}（{grand_ac}/{grand_groups} AC）",
                                  detail + "\n" + rows)
        self._ui(finish)

    # ---------- 校验 ----------
    def _validate(self, src, data, gxx, quiet=False):
        if not src or not data or not gxx:
            if not quiet:
                messagebox.showwarning("提示", "请填好源码/数据目录/编译器")
            return False
        if not os.path.isfile(src):
            if not quiet:
                messagebox.showwarning("提示", "源码文件不存在: " + src)
            return False
        if not os.path.isdir(data):
            if not quiet:
                messagebox.showwarning("提示", "数据目录不存在: " + data)
            return False
        if not os.path.isfile(gxx):
            if not quiet:
                messagebox.showwarning("提示", "编译器不存在: " + gxx)
            return False
        return True


def main():
    root = tk.Tk()
    JudgeApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
