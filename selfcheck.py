# -*- coding: utf-8 -*-
"""OJJudge 核心逻辑自检：用真实 lucky 数据验证评测正确性（无 GUI）"""
import os, sys, subprocess
sys.path.insert(0, r"D:\OJJudge")
import ojjudge

src = r"D:\code\cpp\day01\01_CPP\10.1\SN-XXX\day3\DAY3大样例\DAY3大样例\lucky\lucky.cpp"
data = r"D:\code\cpp\day01\01_CPP\10.1\SN-XXX\day3\DAY3大样例\DAY3大样例\lucky"
gxx = r"C:\mingw64\bin\g++.exe"

task = os.path.splitext(os.path.basename(src))[0]
exe = os.path.join(data, task + ".exe")
p = subprocess.run([gxx, "-o", exe, src, "-std=c++14", "-O2"],
                   capture_output=True, text=True, timeout=120)
print("编译 returncode:", p.returncode)
if p.returncode != 0:
    print("编译错误:", p.stderr)
    sys.exit(1)
print("编译 OK, exe 存在:", os.path.exists(exe))

import glob, time, re

def natural_key(name):
    m = re.search(r"(\d+)", os.path.basename(name))
    return int(m.group(1)) if m else 0

ins = sorted(glob.glob(os.path.join(data, "*.in")), key=natural_key)
total = ac = 0
for in_f in ins:
    base = os.path.splitext(in_f)[0]
    ref = next((base + e for e in (".out", ".ans") if os.path.isfile(base + e)), None)
    tmp_in, tmp_out = os.path.join(data, task+".in"), os.path.join(data, task+".out")
    ojjudge.shutil_force(in_f, tmp_in)
    if os.path.exists(tmp_out): os.remove(tmp_out)
    sub = subprocess.run([exe], cwd=data, capture_output=True, timeout=10)
    if not os.path.isfile(tmp_out):
        print("无输出", os.path.basename(base)); continue
    mine = ojjudge.read_text(tmp_out).strip()
    ans = ojjudge.read_text(ref).strip()
    ok = mine == ans
    ac += ok
    total += 20 if ok else 0
    print(f"{os.path.basename(base)}: {'AC' if ok else 'WA'}  期望[{ans}] 实际[{mine}]")
print(f"==== {ac}/{len(ins)} AC, 总分 {total}/{len(ins)*20} ====")
