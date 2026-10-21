#!/usr/bin/env python3
import argparse,json,os,platform,subprocess,sys,urllib.request
from pathlib import Path
ap=argparse.ArgumentParser(); ap.add_argument('--role',choices=['primary','secondary'],required=True); ap.add_argument('--min-uptime',type=float,default=300); ap.add_argument('--required-cpus',default='0'); ap.add_argument('--max-load',type=float,default=1.0); ap.add_argument('--expected-vcpus',type=int); a=ap.parse_args()
required=[int(x) for x in a.required_cpus.split(',') if x.strip()!='']
def sh(c):
    try:return subprocess.check_output(['bash','-lc',c],text=True,stderr=subprocess.STDOUT).strip()
    except Exception as e:return f'ERROR:{e}'
vcpu=os.cpu_count() or 0; mem_kb=next(int(x.split()[1]) for x in Path('/proc/meminfo').read_text().splitlines() if x.startswith('MemTotal:')); mem=mem_kb/1024/1024; uptime=float(Path('/proc/uptime').read_text().split()[0]); load=os.getloadavg()[0]
threads={k:os.getenv(k) for k in ['OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS','PYTHONHASHSEED']}; services={s:sh(f'systemctl is-active {s} 2>/dev/null || true') for s in ['k3s','k3s-agent','docker.socket','docker','containerd','zeek','unattended-upgrades','apt-daily.timer','apt-daily-upgrade.timer']}
azure={}
try:
    req=urllib.request.Request('http://169.254.169.254/metadata/instance/compute?api-version=2021-02-01',headers={'Metadata':'true'}); azure=json.loads(urllib.request.urlopen(req,timeout=1.0).read().decode())
except Exception: pass
bad=[]
try: allowed=sorted(os.sched_getaffinity(0))
except AttributeError: allowed=list(range(vcpu))
missing=[c for c in required if c not in allowed]
if missing: bad.append(f'required CPUs unavailable: {missing}; allowed={allowed}')
if a.expected_vcpus is not None and vcpu != a.expected_vcpus: bad.append(f'expected exactly {a.expected_vcpus} logical CPUs, found {vcpu}')
if a.role=='primary':
    if vcpu<4:bad.append('primary requires >=4 logical CPUs')
    if mem<14:bad.append('primary requires >=14 GiB RAM')
else:
    if vcpu<2:bad.append('secondary requires >=2 logical CPUs')
    if mem<7:bad.append('secondary requires >=7 GiB RAM')
if uptime<a.min_uptime:bad.append(f'uptime {uptime:.1f}s < {a.min_uptime}s')
if load>a.max_load:bad.append(f'load1 {load:.3f} > {a.max_load}')
for k in ['OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS']:
    if threads[k]!='1':bad.append(f'{k} must equal 1')
if threads['PYTHONHASHSEED']!='0':bad.append('PYTHONHASHSEED must equal 0')
for s,v in services.items():
    if v=='active':bad.append(f'{s} is active; quiesce timing services first')
size=str(azure.get('vmSize',''))
if a.role=='primary' and size.lower().startswith('standard_b'):bad.append(f'burstable Azure size not accepted for primary timing: {size}')
out={'status':'PASS' if not bad else 'FAIL','role':a.role,'hostname':platform.node(),'vcpu':vcpu,'mem_total_gib':round(mem,3),'uptime_seconds':uptime,'load1':load,'max_load':a.max_load,'cpu_model':sh("lscpu | sed -n 's/^Model name:[[:space:]]*//p' | head -n1"),'clocksource':sh('cat /sys/devices/system/clocksource/clocksource0/current_clocksource 2>/dev/null || true'),'kernel':platform.release(),'python':sys.version,'threads':threads,'services':services,'azure_vm_size':size or None,'required_cpus':required,'expected_vcpus':a.expected_vcpus,'allowed_cpus':allowed,'errors':bad}
print(json.dumps(out,indent=2,sort_keys=True)); raise SystemExit(0 if not bad else 2)
