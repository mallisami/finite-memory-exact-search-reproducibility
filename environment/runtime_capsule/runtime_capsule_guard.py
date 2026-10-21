import sys,os,json,platform,sysconfig,hashlib,subprocess
from pathlib import Path
import numpy,scipy,sklearn,threadpoolctl
R=Path('/work');P=R/'P2';sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
info=threadpoolctl.threadpool_info()
libs=[{k:d.get(k) for k in ['user_api','internal_api','version','architecture','num_threads','threading_layer']}|{'binary_sha256':sha(d['filepath'])} for d in info]
flags=next((l.split(':',1)[1].strip().split() for l in Path('/proc/cpuinfo').read_text().splitlines() if l.startswith('flags')),[])
lock={'purpose':'Pins this retained VM3 runtime capsule for future engineering reproducibility. Not the missing original frozen-evidence environment and not proof of exact reproduction.','python':sys.version,'platform':platform.platform(),'libc':platform.libc_ver(),'python_binary_sha256':sha(sys.executable),'build':{k:sysconfig.get_config_var(k) for k in ['CONFIG_ARGS','CC','CFLAGS','SOABI']},'pip_freeze':subprocess.check_output([sys.executable,'-m','pip','freeze'],text=True).splitlines(),'numerical_libraries':libs,'cpu_flags':sorted(flags),'thread_environment':{k:os.getenv(k) for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','PYTHONHASHSEED','OPENBLAS_CORETYPE']},'package_manifest_sha256':sha(P/'06_MANIFESTS/SHA256SUMS.csv')}
lock=json.loads(json.dumps(lock))
path=R/'VM3_RUNTIME_CAPSULE_LOCK.json'
if sys.argv[1]=='capture':path.write_text(json.dumps(lock,indent=2)+'\n');print('RUNTIME CAPTURED; frozen-evidence exact reproduction remains unresolved')
else:
 expected=json.loads(path.read_text());diff=[k for k in lock if lock[k]!=expected[k]]
 report={'guard_pass':not diff,'changed_fields':diff,'scientific_runs_launched':False};print(json.dumps(report));sys.exit(0 if not diff else 2)

