# 3-VM Azure Execution Architecture

## Role discovery

Do not infer which VM is 2/8 or 4/16 from its rack role.

Live inventory determines:
- two 4-vCPU/~16-GiB nodes -> PRIMARY_A, PRIMARY_B;
- one 2-vCPU/~8-GiB node -> CONTROL_SECONDARY.

PRIMARY_A/B are lexical by alias among the two eligible primaries.

## Primary parallelism

PRIMARY_A and PRIMARY_B run concurrently.

Each primary runs exactly one timed PCR process at a time.

### Planned load per primary

Graph timing:
\[
30\times4\times5\times5=3000
\]

MDKP timing:
\[
40\times5\times5=1000
\]

Graph capacity characterization:
\[
30\times4=120
\]

Profiling:
- graph: 10 cases × 2 levels × 5 policies = 100
- MDKP: 10 cases × 5 policies = 50

Total excluding development:
\[
4270
\]
executions per primary.

## Control/secondary VM

During primary timing:
- light orchestration only;
- no CPU-intensive analysis/bootstrap/calibration;
- no packet capture;
- no K3s workload.

After primary completeness, it runs the prespecified secondary hardware block.

## K3s

Kubernetes is not part of PCR's runtime claim.

All three nodes' experiment-related services are quiesced for the primary timing campaign.

Private VNet is only for SSH/orchestration/file transfer outside timed intervals.

## Azure host stability

Capture Azure VM size and CPU model.

B-series/burstable primary VMs are not accepted for the runtime campaign.

Once a primary shard begins, keep that VM allocated until its shard completes whenever operationally possible.
