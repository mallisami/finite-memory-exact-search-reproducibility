from __future__ import annotations

import argparse
import csv
import ipaddress
import json
import re
import subprocess
from collections import defaultdict
from pathlib import Path


def docker_json(cmd: list[str]) -> object:
    return json.loads(subprocess.check_output(cmd, text=True))


def compose_inventory(docker: str, project: str, excluded_substrings: list[str]) -> dict:
    # docker is an executable wrapper path; Compose labels give stable service names.
    ids = subprocess.check_output([docker, "ps", "-q", "--filter", f"label=com.docker.compose.project={project}"], text=True).split()
    if not ids:
        raise RuntimeError(f"no running containers for compose project {project}")
    docs = docker_json([docker, "inspect", *ids])
    excluded = tuple(x.lower() for x in excluded_substrings)
    services: dict[str, dict] = {}
    networks: dict[str, int] = defaultdict(int)
    for d in docs:
        labels = d.get("Config", {}).get("Labels", {}) or {}
        service = labels.get("com.docker.compose.service") or d["Name"].lstrip("/")
        service_l = service.lower()
        include = not any(x in service_l for x in excluded)
        nets = d.get("NetworkSettings", {}).get("Networks", {}) or {}
        for n in nets:
            networks[n] += 1
        services[service] = {
            "container_id": d["Id"], "container_name": d["Name"].lstrip("/"),
            "include": include,
            "networks": {n: x.get("IPAddress", "") for n, x in nets.items()},
        }
    # Use network covering the largest number of project containers; compose default wins naturally.
    network_name = sorted(networks, key=lambda n: (-networks[n], n))[0]
    net_doc = docker_json([docker, "network", "inspect", network_name])[0]
    network_id = net_doc["Id"]
    bridge = "br-" + network_id[:12]
    ip_to_service = {}
    for service, d in services.items():
        ip = d["networks"].get(network_name, "")
        if d["include"] and ip:
            ip_to_service[ip] = service
    if len(ip_to_service) < 5:
        raise RuntimeError(f"too few included application components ({len(ip_to_service)}) for {project}")
    return {"project": project, "network_name": network_name, "network_id": network_id,
            "bridge_interface": bridge, "services": services, "ip_to_service": ip_to_service}


def parse_pcap(tshark: str, pcap: Path, inventory: dict, capture_seconds: float, out_csv: Path) -> dict:
    cmd = [tshark, "-r", str(pcap), "-Y", "ip", "-T", "fields", "-E", "separator=|",
           "-e", "ip.src", "-e", "ip.dst", "-e", "frame.len"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    ipmap = inventory["ip_to_service"]
    bytes_by = defaultdict(int)
    packet_count = 0
    assert proc.stdout is not None
    for line in proc.stdout:
        parts = line.rstrip("\n").split("|")
        if len(parts) < 3:
            continue
        src = parts[0].split(",")[0].strip(); dst = parts[1].split(",")[0].strip()
        try: nbytes = int(parts[2].split(",")[0])
        except Exception: continue
        a = ipmap.get(src); b = ipmap.get(dst)
        if a is None or b is None or a == b:
            continue
        bytes_by[(a,b)] += nbytes; packet_count += 1
    stderr = proc.stderr.read() if proc.stderr else ""
    rc = proc.wait()
    if rc != 0:
        raise RuntimeError(f"tshark failed ({rc}): {stderr[-2000:]}")
    rows = []
    for (a,b), nbytes in sorted(bytes_by.items()):
        rows.append({"src":a,"dst":b,"bytes":nbytes,"mb_per_s":nbytes/1e6/max(capture_seconds,1e-12)})
    if not rows:
        raise RuntimeError(f"no included internal traffic in {pcap}")
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    return {"packets_mapped": packet_count, "directed_edges": len(rows),
            "total_internal_bytes": int(sum(r["bytes"] for r in rows)),
            "total_internal_mb_per_s": float(sum(r["mb_per_s"] for r in rows))}


def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--docker",required=True); ap.add_argument("--project",required=True)
    ap.add_argument("--excluded",default="jaeger,dns-media,consul"); ap.add_argument("--inventory-out",required=True)
    args=ap.parse_args(); inv=compose_inventory(args.docker,args.project,[x for x in args.excluded.split(",") if x])
    Path(args.inventory_out).write_text(json.dumps(inv,indent=2),encoding="utf-8"); print(json.dumps(inv,indent=2))
if __name__=="__main__": main()
