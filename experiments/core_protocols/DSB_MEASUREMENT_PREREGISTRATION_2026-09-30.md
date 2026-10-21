# E-DSB preregistration — measured dynamic repeated-repair confirmation

## Purpose
This is the single final empirical strengthening campaign for PCR. It replaces the abandoned WfCommons temporal-replay route, which stopped before solver trials after failing its frozen metadata gates. The study tests whether persistent certifying repair has an operational effect under measured, changing microservice communication while preserving the paper's existing feasibility and numerical contract.

## Applications and population
The primary environment runs three released DeathStarBench applications from repository commit `6ecb09706140f8730b5385c08f1386c654c3c526`: Social Network, Hotel Reservation, and Media Service. Applications are run one at a time on the primary Azure VM. Ten independent measured sequences are collected for each application-regime cell.

## Dynamic regimes
Each sequence has ten workload states. `step` uses five low-rate states followed by five high-rate states. `burst` uses the frozen pattern L,L,H,L,L,H,L,L,H,L. `ramp` uses ten monotonically increasing commanded rates from low to high and is a prespecified low-recurrence operating-boundary control. Low and high are fixed from a pre-outcome per-application load calibration at 25% and 75% of the highest sustainable calibrated rate.

Each state executes wrk2 for 30 s. The first 10 s are warm-up/calibration; packet and container-resource measurement cover the final 20 s. The official benchmark workload script is copied from the pinned repository and transformed only to make the RNG seed explicit; the Hotel Reservation copy additionally inserts the missing local latitude/longitude variables in the reservation branch. The source commit, transformation, and generated script hashes are recorded.

## Measurement and state construction
Traffic is captured on the Docker Compose bridge for the active application. Container IP addresses are mapped to Compose service names. Directed interaction weight `w_ij` is the measured Ethernet-frame byte rate (MB/s) from included component `i` to included component `j` during the 20-s measurement interval. Host-to-frontend traffic and components containing `jaeger`, `dns-media`, or `consul` in their Compose service name are excluded. Databases, caches, frontends, and application microservices remain included.

Repeated occurrences of the same commanded profile within one measured sequence are canonicalized prospectively by averaging their raw measured matrices and assigning that fixed profile matrix to every occurrence of that profile. Raw occurrence matrices are retained for construct validation. This removes packet-count noise from the exact PCR compatibility test without using solver outcomes. Ramp states remain separately measured profile states.

Per-component fixed CPU and memory demands are calculated before solver execution from the application's complete primary measurement campaign: p95 observed CPU cores and p95 memory MB, with only small nonzero floors for components whose observed p95 is zero. These fixed demands are then used for every state of that application.

## Construct-validation gate
No solver outcomes are generated until the full primary measurement set is complete and the following frozen gate passes: (1) every planned state has a valid traffic matrix and resource samples; (2) at least 95% of measured states achieve at least 90% of commanded RPS and have <=2% HTTP non-2xx responses; (3) every state contains positive internal application traffic; (4) for each application, the median total internal byte rate of high-profile states is at least 1.20 times the median low-profile rate across step and burst measurements. Failure stops the campaign before solver trials. No gate may be relaxed after inspection.

## Placement model
The measured component graph is evaluated on ten hosts sampled from an eligible Internet Topology Zoo topology. Host-to-host cost is the normalized shortest-path geographical cost already used by the PCR paper. Fixed component demands come from the measurement stage. Equal per-host resource capacity starts at `max(total/(10*0.70), 1.05*largest_component)` for each resource and is increased deterministically in 5% increments only if required to construct the common feasible worst-fit incumbent. This construction is performed without solver outcomes and its realized load is recorded. For the same application and repetition index, step, burst, and ramp use the same topology, capacities, and common initial placement.

## Shadow-replay boundary
The DeathStarBench stacks are used to measure dynamic communication/resource states. Solver arms are executed after measurement on the frozen, hash-verified state sequence; solver placements are not redeployed into the live benchmark during this study. The evidence therefore validates PCR under measured end-to-end benchmark dynamics, not production migration latency or live application-SLO improvement.

## Solver arms
Three matched arms are run on every sequence: `pcr_persistent`, `pcr_state_reset`, and `alns_highs`. The adaptive-LNS outer controller, destroy size, state sequence, starting placement, random seeds, and 10-s state budget are identical. Persistent and reset PCR share the exact state-0 execution; the treatment begins only at the first external state transition. Reset PCR discards all cross-state proof state at every transition. Persistent PCR keeps only checkpoints whose complete local cache remains exactly equal on `external_gain`, `pair_gain`, and `residual_capacity`. ALNS+HiGHS is the existing P6 matched repair policy with at most 1 s per repair call and is budget-capped. The solver stage sets standard numerical-library thread environment variables to one thread for reproducible CPU accounting.

## Endpoints and hypotheses
The independent unit is a complete measured application/regime/repetition sequence. The primary endpoint is sequence-normalized anytime cost, averaged over the ten states. H1 compares persistent PCR with reset PCR on the prespecified recurrent regimes `step` and `burst`. H2 compares persistent PCR with ALNS+HiGHS on the same recurrent regimes. Both tests are two-sided paired Wilcoxon tests; Holm adjusts across H1 and H2. Mean paired differences receive 95% stratified bootstrap intervals resampling repetitions within application-regime cells. Negative persistent-minus-comparator values favor persistent PCR.

The `ramp` regime is a prespecified operating-boundary control, not a third confirmatory hypothesis. Secondary/mechanistic outputs include final normalized objective, compatible checkpoint fraction, cross-state resumed calls, transition overhead, accepted moves, and discarded/recomputed search work. A non-significant result is reported as unresolved, not equivalence.

## Second-environment robustness subset
After the Azure primary campaign, the identical package is to be run on one physically distinct second host in `second-host` mode for the burst regime only, five repetitions per application. This subset is a robustness check and is not pooled into the primary confirmatory p-values.

## Stopping rules
Application deployment, workload initialization, calibration, capture, construct validation, solver feasibility, or integrity failure stops the affected stage with a nonzero exit status. Failed or incomplete cells are never silently dropped. No additional benchmark, solver, regime, threshold, or endpoint is added after outcome inspection.
