# Paper 2 P6 — Frozen Prediction Protocol Before Model Training

## 1. Scientific target
Predict at each decision epoch

\[
p_i^{use}=P(\text{at least one legally compatible recurrence within 40 controller iterations}\mid\text{decision-time information}).
\]

Reusable exact work `W_i^{invested}` is known under the validated exact-repeat semantics and is not a learned target.

## 2. Development and final-test separation
### Development corpus
Use all 45 P5.5 base cases (675 rows) as the development corpus. The old train/validation/test labels are retained for provenance but no longer define the final test.

### Development folds
Use deterministic 5-fold grouped cross-validation. Within each domain, assign the 15 P5.5 seeds to five folds by seed-list position modulo 5, giving 3 base cases/domain (9 base cases total) per held-out fold. No `(domain, instance_seed)` group may cross folds.

### Final blind test
Use the sealed 15-case P5.6 holdout only once after model family, hyperparameters, feature set, calibration rule, and decision selector are frozen. Do not inspect its sealed labels before that release point.

## 3. Default feature matrix
Use exactly the 23 fields in `P56_FEATURE_FIREWALL.json`.

Feature-family ablations are frozen as:

### H — recurrence/history
- `history_count_same_context`
- `iterations_since_last_context`
- `recent_same_context_count_20`

### S — checkpoint/search state
- `invested_branch_pops`
- `checkpoint_bytes`
- `additive_gap_at_checkpoint`
- `queue_size`
- `partial_branches_pruned`
- `child_branches_generated`
- `root_upper_bound`

### D — dynamic controller context
- `current_destroy_op_index`
- `current_repair_arm_index`
- `current_objective_before`
- `current_best_objective`
- `current_temperature`
- `recent_accept_rate_10`
- `recent_accept_rate_20`
- `recent_moved_node_overlap_10`
- `recent_adjacent_move_count_10`
- `recent_moved_node_overlap_20`
- `recent_adjacent_move_count_20`
- `objective_improvement_last_10`
- `objective_improvement_last_20`

Report H, S, D, H+S, H+D, and H+S+D.

`domain` is not included in the default model. It may appear only as a separately labelled context ablation.

## 4. Model hierarchy
Models are evaluated in this order; later complexity is justified only by development evidence.

1. constant training-prevalence predictor;
2. history-frequency baseline;
3. logistic regression;
4. histogram gradient-boosted trees;
5. small MLP.

No GNN is permitted in the primary P6 run. A GNN requires a separate post-P6 gate showing that graph-structured information is available at decision time and that simpler models leave meaningful blind-test/controller headroom.

## 5. Hyperparameter search — frozen before training
### Logistic regression
- L2 penalty;
- `C ∈ {0.1, 1.0, 10.0}`;
- no class weighting;
- continuous features standardized using training folds only;
- destroy/repair operator indices one-hot encoded using training-fold categories.

### Histogram gradient boosting
Grid:
- learning rate `{0.03, 0.10}`;
- max leaf nodes `{7, 15, 31}`;
- max iterations `{100, 250}`;
- L2 regularization `{0.0, 1.0}`.

### MLP
- hidden layers `{(32,), (64,32)}`;
- alpha `{1e-4, 1e-3}`;
- learning rate `1e-3`;
- max iterations `500`;
- fixed random seeds `{17, 29, 43}`; use the mean probability across the three fitted replicas for evaluation.

No hyperparameter range may be changed after blind-test labels are released.

## 6. Model selection and calibration
Primary development selection metric: **group-fold mean log loss**.

Tie-breakers, in order:
1. Brier score;
2. AUPRC;
3. simpler model.

For the selected configuration, obtain out-of-fold probabilities over all 45 development cases. Compare:
- no post-hoc calibration;
- sigmoid/Platt calibration fit only to out-of-fold development predictions.

Choose calibration by development log loss, tie by Brier score. Then refit the base model on all development cases and carry the frozen calibrator to the blind final test.

## 7. Reported prediction metrics
Primary:
- log loss;
- Brier score.

Secondary:
- AUROC;
- AUPRC;
- calibration intercept/slope;
- reliability plot.

Confidence intervals must resample base cases, not individual rows.

## 8. Retention-value mapping
For controller use:

\[
\hat v_i = \hat p_i^{use} W_i^{invested} - C_i^{restore}
\]

with bytes enforced by the exact P5.6 selector. The primary allocation comparator is exact predicted-value selection; greedy value-density remains an ablation/baseline.

No future/oracle information is permitted in prediction or selection.

## 9. Blind-test release rule
The sealed label file may be opened only after:
- final 23-feature set is fixed;
- model configuration is selected by development CV;
- calibration is fixed;
- exact allocation selector is fixed;
- all prediction metrics and bootstrap procedure are fixed;
- model artifacts and development results are hashed.

The blind test is evaluated once. No model/hyperparameter/feature change is allowed in response to blind-test performance. Any later change creates a new model version and requires a new independent final holdout.

## 10. Interpretation boundary
P6 establishes predictability/generalization of useful compatible recurrence. It does not establish end-to-end optimization benefit. That is reserved for P7 on-policy online-controller evaluation.
