# Timing and Noise-Control Protocol

## Pre-campaign quiescence

On all three VMs, save service state then quiesce if active:
- k3s
- k3s-agent
- docker.socket
- docker
- standalone containerd
- zeek
- unattended-upgrades
- apt-daily.timer
- apt-daily-upgrade.timer

Do not stop:
- ssh
- networking
- required system logging.

## Startup stabilization

After VM start:
- wait >=300 seconds;
- capture boot ID;
- confirm no VM reboot occurred;
- confirm low idle CPU/load;
- confirm timing services remain quiesced;
- confirm thread caps.

## Primary timer

`time.perf_counter_ns()` around the complete comparable controller execution.

Secondary:
`time.process_time_ns()` around the same scope.

No file writes or network I/O in the timed interval.

## Policy ordering

Five policies × five repeats.

For case/level key \(K\), let:
\[
o = \operatorname{SHA256}(K)\bmod5.
\]

Repeat \(r\) runs the cyclic order rotated by:
\[
(o+r)\bmod5.
\]

Each policy occupies each ordinal position exactly once.

## CPU affinity

If stable affinity is available, use one fixed logical CPU per primary for the full campaign.

Freeze the choice during development; do not change after untouched cases begin.

## Warm-up

After quiescence and before authoritative timing:
- one dedicated non-sample warm-up case per backend/policy path.

No confirmatory case receives special outcome-dependent warming.

## Detailed profiling

Do not run nested component timers inside primary timing.

Detailed bucket timing is a separate fixed profiling subset.

## Cross-primary concurrency

The two primary VMs may run concurrently.

Their schedules are independently hash-offset so policy order is not synchronized by design.
