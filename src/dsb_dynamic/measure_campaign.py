from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

from .packet_tools import compose_inventory, parse_pcap
from .workload_tools import load_config, parse_quantity_bytes, parse_wrk_output, profile_schedule, deterministic_seed

APP_ORDER = ["socialNetwork", "hotelReservation", "mediaMicroservices"]
REGIMES = ["step", "burst", "ramp"]


def run(cmd, *, cwd=None, env=None, check=True, capture=False, log: Path | None=None):
    if log is not None:
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open("w", encoding="utf-8") as f:
            p = subprocess.run(cmd, cwd=cwd, env=env, text=True, stdout=f, stderr=subprocess.STDOUT)
    else:
        p = subprocess.run(cmd, cwd=cwd, env=env, text=True, capture_output=capture)
    if check and p.returncode != 0:
        raise RuntimeError(f"command failed {p.returncode}: {' '.join(map(str,cmd))}")
    return p


def wait_port(port: int, timeout_s: int = 180):
    import socket
    deadline=time.time()+timeout_s
    while time.time()<deadline:
        try:
            with socket.create_connection(("127.0.0.1", int(port)), timeout=2):
                return
        except OSError:
            time.sleep(3)
    raise RuntimeError(f"frontend port did not become ready: {port}")


def docker_compose(docker: str, project: str, app_dir: Path, *args: str, log: Path | None=None):
    return run([docker,"compose","-p",project,*args],cwd=app_dir,log=log)




def record_image_lock(docker: str, project: str, path: Path):
    ids=subprocess.check_output([docker,"ps","-q","--filter",f"label=com.docker.compose.project={project}"],text=True).split()
    if not ids: raise RuntimeError(f"no containers available for image lock: {project}")
    docs=json.loads(subprocess.check_output([docker,"inspect",*ids],text=True))
    rows=[]
    for d in docs:
        labels=d.get("Config",{}).get("Labels",{}) or {}; service=labels.get("com.docker.compose.service",d.get("Name","").lstrip("/"))
        image_id=d.get("Image",""); configured=d.get("Config",{}).get("Image","")
        repo_digests=[]
        try:
            im=json.loads(subprocess.check_output([docker,"image","inspect",image_id],text=True))[0]
            repo_digests=im.get("RepoDigests",[]) or []
        except Exception: pass
        rows.append({"service":service,"container":d.get("Name","").lstrip("/"),"configured_image":configured,"image_id":image_id,"repo_digests":repo_digests})
    path.write_text(json.dumps(sorted(rows,key=lambda x:x["service"]),indent=2),encoding="utf-8")

def initialize_app(app: str, repo: Path, python: str, docker: str, project: str, logs: Path):
    appdir=repo/{"socialNetwork":"socialNetwork","hotelReservation":"hotelReservation","mediaMicroservices":"mediaMicroservices"}[app]
    if app=="socialNetwork":
        run([python,"scripts/init_social_graph.py","--graph=socfb-Reed98","--limit=100"],cwd=appdir,log=logs/"init.log")
    elif app=="hotelReservation":
        # Hotel Reservation seeds its backing data from the service implementation.
        run(["curl","-fsS","--max-time","10","http://127.0.0.1:5000/hotels?inDate=2015-04-09&outDate=2015-04-10&lat=38.0235&lon=-122.095"],log=logs/"init.log")
    elif app=="mediaMicroservices":
        # Register users using benchmark script, then register the movie titles used by the official compose-review workload.
        run(["bash","scripts/register_users.sh"],cwd=appdir,log=logs/"register_users.log")
        lua=(appdir/"wrk2/scripts/media-microservices/compose-review.lua").read_text(encoding="utf-8",errors="replace")
        block=re.search(r"local movie_titles\s*=\s*\{(.*?)\n\}",lua,re.S)
        if not block: raise RuntimeError("could not parse media movie_titles from pinned workload")
        titles=re.findall(r'"((?:[^"\\]|\\.)*)"',block.group(1))
        if len(titles)<50: raise RuntimeError(f"unexpectedly few media titles: {len(titles)}")
        script=logs/"register_titles.py"
        script.write_text("""import sys, urllib.parse, urllib.request\nfor i,title in enumerate(sys.stdin.read().splitlines(),1):\n data=urllib.parse.urlencode({'title':title,'movie_id':str(i)}).encode()\n try:\n  urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:8080/wrk2-api/movie/register',data=data),timeout=5).read()\n except Exception as e:\n  print('ERROR',i,title,repr(e)); raise\nprint('registered',i)\n""",encoding="utf-8")
        p=subprocess.run([python,str(script)],input="\n".join(titles),text=True,cwd=appdir,capture_output=True)
        (logs/"register_titles.log").write_text(p.stdout+p.stderr,encoding="utf-8")
        if p.returncode!=0: raise RuntimeError("media title registration failed")
    else: raise ValueError(app)


def start_app(app: str, cfg: dict, repo: Path, docker: str, python: str, logs: Path) -> tuple[str, Path]:
    project=f"pcrdsb_{app.lower()}"
    appdir=repo/cfg["applications"][app]["directory"]
    docker_compose(docker,project,appdir,"down","-v","--remove-orphans",log=logs/"pre_down.log")
    if app=="hotelReservation":
        docker_compose(docker,project,appdir,"up","-d","--build",log=logs/"compose_up.log")
    else:
        docker_compose(docker,project,appdir,"up","-d",log=logs/"compose_up.log")
    port=int(cfg["applications"][app]["frontend_port"])
    wait_port(port,240)
    time.sleep(15)
    initialize_app(app,repo,python,docker,project,logs)
    time.sleep(5)
    return project,appdir


def stop_app(appdir: Path, docker: str, project: str, logs: Path):
    try: docker_compose(docker,project,appdir,"down","-v","--remove-orphans",log=logs/"compose_down.log")
    except Exception as e: (logs/"compose_down_error.txt").write_text(repr(e),encoding="utf-8")


def run_wrk(wrk: Path, script: Path, url: str, rps: int, seed: int, duration_s: int, threads: int, conns: int, log: Path):
    env=os.environ.copy(); env["PCR_SEED"]=str(seed)
    cmd=[str(wrk),"-D","exp","-t",str(threads),"-c",str(conns),"-d",str(duration_s),"-L","-s",str(script),url,"-R",str(rps)]
    with log.open("w",encoding="utf-8") as f:
        p=subprocess.Popen(cmd,stdout=f,stderr=subprocess.STDOUT,text=True,env=env)
    return p,cmd


def calibration(app: str,cfg:dict,wrk:Path,script:Path,out:Path)->dict:
    out.mkdir(parents=True,exist_ok=True)
    appcfg=cfg["applications"][app]; m=cfg["measurement"]
    port=appcfg["frontend_port"]; url=f"http://127.0.0.1:{port}"
    rows=[]; highest=None
    for j,rps in enumerate(appcfg["calibration_candidates_rps"]):
        log=out/f"candidate_{rps}.log"; seed=deterministic_seed(20260930,APP_ORDER.index(app),j)
        p,_=run_wrk(wrk,script,url,int(rps),seed,int(m["state_total_seconds"]),int(m["wrk_threads"]),int(m["wrk_connections"]),log)
        rc=p.wait();
        if rc!=0: rows.append({"requested_rps":rps,"passed":0,"reason":f"wrk_exit_{rc}"}); break
        metrics=parse_wrk_output(log.read_text(errors="replace"),rps)
        passed=(math.isfinite(float(metrics["p99_ms"])) and float(metrics["p99_ms"])<=float(m["calibration_p99_limit_ms"]) and
                float(metrics["achieved_fraction"])>=float(m["calibration_achieved_fraction_min"]) and
                float(metrics["non2xx_fraction"])<=float(m["calibration_non2xx_fraction_max"]) and
                float(metrics["socket_error_fraction"])<=0.01)
        metrics["passed"]=int(passed); rows.append(metrics)
        if passed: highest=int(rps)
        else: break
    if highest is None or highest<4: raise RuntimeError(f"{app}: no sustainable calibrated rate >=4 RPS")
    low=max(1,int(round(highest*float(m["low_fraction_of_capacity"]))))
    high=max(low+1,int(round(highest*float(m["high_fraction_of_capacity"]))))
    high=min(high,highest)
    if high<=low: raise RuntimeError(f"{app}: calibration cannot create distinct low/high rates")
    out.mkdir(parents=True,exist_ok=True)
    if rows:
        fields=sorted({k for r in rows for k in r})
        with (out/"calibration.csv").open("w",newline="",encoding="utf-8") as f:
            w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
    result={"app":app,"capacity_rps":highest,"low_rps":low,"high_rps":high,"criteria":{
        "p99_limit_ms":m["calibration_p99_limit_ms"],"achieved_fraction_min":m["calibration_achieved_fraction_min"],"non2xx_fraction_max":m["calibration_non2xx_fraction_max"]}}
    (out/"calibration.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    return result


def collect_stats(docker:str, container_ids:list[str], service_by_name:dict[str,str], period:float, stop:threading.Event, rows:list[dict]):
    while not stop.is_set():
        t=time.time()
        p=subprocess.run([docker,"stats","--no-stream","--format","{{json .}}",*container_ids],text=True,capture_output=True)
        if p.returncode==0:
            for line in p.stdout.splitlines():
                try: d=json.loads(line)
                except Exception: continue
                name=d.get("Name",""); service=service_by_name.get(name)
                if not service: continue
                try: cpu=float(str(d.get("CPUPerc","0")).rstrip("%"))/100.0
                except Exception: cpu=float("nan")
                try: mem=parse_quantity_bytes(str(d.get("MemUsage","0B")))/1e6
                except Exception: mem=float("nan")
                rows.append({"epoch":t,"service":service,"cpu_cores":cpu,"memory_mb":mem})
        stop.wait(period)


def measure_state(app:str,cfg:dict,docker:str,tshark:str,wrk:Path,script:Path,project:str,rps:int,seed:int,state_dir:Path,keep_pcap:bool):
    m=cfg["measurement"]; state_dir.mkdir(parents=True,exist_ok=True)
    done=state_dir/"DONE.json"
    if done.is_file(): return json.loads(done.read_text())
    inv=compose_inventory(docker,project,m["excluded_service_substrings"])
    bridge=inv["bridge_interface"]
    if not Path("/sys/class/net",bridge).exists(): raise RuntimeError(f"Docker bridge interface not found: {bridge}")
    (state_dir/"inventory.json").write_text(json.dumps(inv,indent=2),encoding="utf-8")
    included={s:d for s,d in inv["services"].items() if d["include"]}
    ids=[d["container_id"] for d in included.values()]
    service_by_name={d["container_name"]:s for s,d in included.items()}
    port=cfg["applications"][app]["frontend_port"]; url=f"http://127.0.0.1:{port}"
    wrklog=state_dir/"wrk.log"; p,cmd=run_wrk(wrk,script,url,rps,seed,int(m["state_total_seconds"]),int(m["wrk_threads"]),int(m["wrk_connections"]),wrklog)
    time.sleep(float(m["warmup_seconds"]))
    pcap=state_dir/"capture.pcap"
    tcp=subprocess.Popen(["sudo","-n","tcpdump","-i",bridge,"-n","-s","0","-U","-w",str(pcap)],stdout=subprocess.DEVNULL,stderr=(state_dir/"tcpdump.log").open("w"))
    stop=threading.Event(); stats=[]; th=threading.Thread(target=collect_stats,args=(docker,ids,service_by_name,float(m["stats_period_seconds"]),stop,stats),daemon=True); th.start()
    time.sleep(float(m["capture_seconds"]))
    stop.set(); th.join(timeout=10)
    tcp.send_signal(signal.SIGINT)
    try: tcp.wait(timeout=15)
    except subprocess.TimeoutExpired: tcp.kill(); tcp.wait()
    rc=p.wait()
    if rc!=0: raise RuntimeError(f"wrk failed for {app} at {rps} RPS, exit={rc}")
    metrics=parse_wrk_output(wrklog.read_text(errors="replace"),rps)
    edge_meta=parse_pcap(tshark,pcap,inv,float(m["capture_seconds"]),state_dir/"edges.csv")
    if not stats: raise RuntimeError("no docker stats samples")
    with (state_dir/"stats.csv").open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(stats[0]));w.writeheader();w.writerows(stats)
    import hashlib
    pcap_sha=hashlib.sha256(pcap.read_bytes()).hexdigest()
    meta={"app":app,"requested_rps":rps,"seed":seed,"wrk_command":cmd,**metrics,**edge_meta,
          "pcap_sha256":pcap_sha,"capture_seconds":m["capture_seconds"],"included_services":sorted(included)}
    done.write_text(json.dumps(meta,indent=2),encoding="utf-8")
    if not keep_pcap: pcap.unlink(missing_ok=True)
    return meta


def sequence_order() -> list[tuple[int,str]]:
    base=REGIMES
    out=[]
    for rep in range(1,11):
        rot=(rep-1)%3; order=base[rot:]+base[:rot]
        for r in order: out.append((rep,r))
    return out


def run_primary(root:Path,cfg:dict,docker:str,python:str,tshark:str,mode:str):
    repo=root/"external/DeathStarBench"; wrk=repo/"wrk2/wrk"; generated=root/"workloads/generated"; results=root/"results/measurement"
    reps=10 if mode=="primary" else int(cfg["second_environment_subset"]["repetitions_per_application"])
    allowed_regimes=REGIMES if mode=="primary" else [cfg["second_environment_subset"]["regime"]]
    all_rows=[]
    for ai,app in enumerate(APP_ORDER):
        app_logs=results/app/"lifecycle"; app_logs.mkdir(parents=True,exist_ok=True)
        project=app_logs.joinpath("project.txt").read_text().strip() if app_logs.joinpath("project.txt").is_file() else f"pcrdsb_{app.lower()}"
        project,appdir=start_app(app,cfg,repo,docker,python,project_logs:=app_logs)
        (app_logs/"project.txt").write_text(project)
        record_image_lock(docker,project,app_logs/"IMAGE_LOCK.json")
        try:
            calpath=results/app/"calibration/calibration.json"
            if calpath.is_file(): cal=json.loads(calpath.read_text())
            else: cal=calibration(app,cfg,wrk,generated/f"{app}.lua",results/app/"calibration")
            low,high=int(cal["low_rps"]),int(cal["high_rps"])
            order=sequence_order() if mode=="primary" else [(rep,allowed_regimes[0]) for rep in range(1,reps+1)]
            for rep,regime in order:
                if rep>reps or regime not in allowed_regimes: continue
                seq=f"{app}_{regime}_r{rep:02d}"
                seqdir=results/app/"sequences"/seq
                completed=list(seqdir.glob("state_*/STATE.json")) if seqdir.exists() else []
                if completed and len(completed)!=10:
                    shutil.rmtree(seqdir)
                schedule=profile_schedule(regime,low,high)
                for si,(profile,rps) in enumerate(schedule):
                    state_dir=results/app/"sequences"/seq/f"state_{si:02d}"
                    keep=(rep==1 and si in (0,9))
                    seed=deterministic_seed(20260930,ai,rep,REGIMES.index(regime),si)
                    meta=measure_state(app,cfg,docker,tshark,wrk,generated/f"{app}.lua",project,rps,seed,state_dir,keep)
                    meta.update({"sequence":seq,"regime":regime,"repetition":rep,"state_index":si,"profile":profile})
                    all_rows.append(meta)
                    (state_dir/"STATE.json").write_text(json.dumps(meta,indent=2),encoding="utf-8")
        finally:
            stop_app(appdir,docker,project,app_logs)
    # Rebuild complete state index from disk, so resume runs are complete.
    rows=[]
    for p in sorted(results.glob("*/sequences/*/state_*/STATE.json")):
        rows.append(json.loads(p.read_text()))
    if not rows: raise RuntimeError("measurement produced no states")
    fields=sorted({k for r in rows for k in r if not isinstance(r[k],(dict,list))})
    with (results/"MEASUREMENT_INDEX.csv").open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows([{k:r.get(k,"") for k in fields} for r in rows])
    (results/"MODE.txt").write_text(mode+"\n")


def main():
    ap=argparse.ArgumentParser();ap.add_argument("--root",required=True);ap.add_argument("--config",required=True);ap.add_argument("--docker",required=True)
    ap.add_argument("--python",default=sys.executable);ap.add_argument("--tshark",default="tshark");ap.add_argument("--mode",choices=["primary","second-host"],default="primary")
    a=ap.parse_args();run_primary(Path(a.root),load_config(Path(a.config)),a.docker,a.python,a.tshark,a.mode)

if __name__=="__main__": main()
