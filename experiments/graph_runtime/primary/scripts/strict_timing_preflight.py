#!/usr/bin/env python3
import argparse,json,os,platform,subprocess,time
from pathlib import Path
ap=argparse.ArgumentParser();ap.add_argument("--min-uptime",type=float,default=300);ap.add_argument("--max-load1",type=float,default=1.0);ap.add_argument("--require-services-inactive",action="store_true");a=ap.parse_args()
def sh(c):
    try:return subprocess.check_output(["bash","-lc",c],text=True,stderr=subprocess.STDOUT).strip()
    except Exception as e:return f"ERROR:{e}"
upt=float(Path("/proc/uptime").read_text().split()[0]); load=os.getloadavg()[0]
services={s:sh(f"systemctl is-active {s} 2>/dev/null || true") for s in ["k3s","k3s-agent","docker.socket","docker","containerd","zeek","unattended-upgrades","apt-daily.timer","apt-daily-upgrade.timer"]}
threads={k:os.getenv(k) for k in ["OMP_NUM_THREADS","MKL_NUM_THREADS","OPENBLAS_NUM_THREADS","NUMEXPR_NUM_THREADS","PYTHONHASHSEED"]}
bad=[]
if upt<a.min_uptime:bad.append(f"uptime<{a.min_uptime}")
if load>a.max_load1:bad.append(f"load1>{a.max_load1}")
for k in ["OMP_NUM_THREADS","MKL_NUM_THREADS","OPENBLAS_NUM_THREADS","NUMEXPR_NUM_THREADS"]:
    if threads[k]!="1":bad.append(f"{k}!=1")
if threads["PYTHONHASHSEED"]!="0":bad.append("PYTHONHASHSEED!=0")
if a.require_services_inactive:
    for s,v in services.items():
        if v=="active":bad.append(f"{s}=active")
out={"status":"PASS" if not bad else "FAIL","hostname":sh("hostname"),"boot_id":sh("cat /proc/sys/kernel/random/boot_id"),"uptime_seconds":upt,"load1":load,"kernel":platform.release(),"cpu_model":sh("lscpu | sed -n 's/^Model name:[[:space:]]*//p' | head -n1"),"clocksource":sh("cat /sys/devices/system/clocksource/clocksource0/current_clocksource 2>/dev/null || true"),"threads":threads,"services":services,"errors":bad}
print(json.dumps(out,indent=2,sort_keys=True))
raise SystemExit(0 if not bad else 2)
