# Locked Statistical Analysis Plan

## RQ2 primary family

\[
S^\pi_{c,\ell}=\log(T_{restart,c,\ell}/T_{\pi,c,\ell}).
\]

A. Opportunity conversion:
\[
D^{opp}_c=S^{learned-pW}_{c,L4}-S^{learned-pW}_{c,L1}.
\]

B. Compute-aware refinement:
\[
D^{value}_c=\log(T_{learned-pW,c,L4}/T_{learned-pC,c,L4}).
\]

C. Net acceleration:
\[
D^{net}_c=\log(T_{restart,c,L4}/T_{learned-pC,c,L4}).
\]

Holm-adjust the three two-sided paired tests.

## RQ3 primary family

A:
\[
\log(T_{learned-pW}/T_{learned-pC}).
\]

B:
\[
\log(T_{restart}/T_{learned-pC}).
\]

C:
\[
\log(T_{empirical-pC}/T_{learned-pC}).
\]

Holm-adjust the three two-sided paired tests.

## Estimation

For every primary contrast:
- mean case-level log effect;
- exponentiated geometric mean runtime ratio;
- percentage effect;
- mean paired ms;
- median paired ms;
- 95% bootstrap CI, 10,000 resamples;
- two-sided paired Wilcoxon as secondary inferential summary.

## Bootstrap strata

Graph:
- PRIMARY_A/B × Generic/Workflow/Microservice.

MDKP:
- PRIMARY_A/B.

Resampling preserves original total weighting.

## Secondary outcomes

- exact-search process CPU;
- new branch nodes;
- deterministic compute units executed;
- deterministic compute units reused;
- useful compatible resumes;
- byte-time;
- profiling overhead buckets;
- objective.

No secondary endpoint substitutes for the primary runtime result.

## Second-hardware block

Descriptive only:
- same paired log-ratio effect definitions;
- 95% bootstrap intervals;
- no additional superiority family.
