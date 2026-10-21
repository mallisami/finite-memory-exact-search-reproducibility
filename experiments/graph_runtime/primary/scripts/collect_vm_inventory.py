#!/usr/bin/env python3
import json, os, platform, socket, subprocess, urllib.request
from pathlib import Path

def sh(cmd):
    try:
        return subprocess.check_output(["bash","-lc",cmd], text=True, stderr=subprocess.STDOUT).strip()
    except Exception as e:
        return f"ERROR: {e}"

def azure_metadata():
    url="http://169.254.169.254/metadata/instance?api-version=2021-02-01"
    try:
        req=urllib.request.Request(url, headers={"Metadata":"true"})
        with urllib.request.urlopen(req, timeout=2.0) as r:
            j=json.load(r)
        c=j.get("compute",{})
        return {
            "vmSize":c.get("vmSize"),
            "location":c.get("location"),
            "offer":c.get("offer"),
            "sku":c.get("sku"),
            "version":c.get("version"),
        }
    except Exception as e:
        return {"error":str(e)}

mem=None
try:
    for line in Path("/proc/meminfo").read_text().splitlines():
        if line.startswith("MemTotal:"):
            mem=int(line.split()[1]); break
except Exception:
    pass

out={
    "hostname":socket.gethostname(),
    "fqdn":socket.getfqdn(),
    "vcpu":os.cpu_count(),
    "mem_total_gib":round(mem/1024/1024,3) if mem else None,
    "os_release":sh(". /etc/os-release; printf '%s %s' \"$NAME\" \"$VERSION\""),
    "kernel":platform.release(),
    "machine":platform.machine(),
    "cpu_model":sh("lscpu | sed -n 's/^Model name:[[:space:]]*//p' | head -n1"),
    "clocksource":sh("cat /sys/devices/system/clocksource/clocksource0/current_clocksource 2>/dev/null || true"),
    "boot_id":sh("cat /proc/sys/kernel/random/boot_id"),
    "uptime_seconds":float(Path("/proc/uptime").read_text().split()[0]),
    "loadavg":list(os.getloadavg()),
    "python3":platform.python_version(),
    "azure":azure_metadata(),
    "services":{
        s:sh(f"systemctl is-active {s} 2>/dev/null || true")
        for s in ["k3s","k3s-agent","docker.socket","docker","containerd","zeek","unattended-upgrades","apt-daily.timer","apt-daily-upgrade.timer"]
    }
}
print(json.dumps(out,indent=2,sort_keys=True))
