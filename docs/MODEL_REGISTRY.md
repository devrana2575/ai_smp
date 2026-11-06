# Model Registry

The model registry is the Phase 4 lifecycle layer for research models. It stores
versioned candidates, keeps an append-only audit trail, and controls which
registered version may serve v2 registered-model predictions.

The registry is deliberately separate from `saved_models/`. Training a candidate
never overwrites the legacy production artifacts, and activating a registered
version changes only the v2 registered-model prediction path. The existing
legacy prediction flow is unchanged.

## 1. Storage layout

```text
ai-service/model_registry/
├── registry.json                  # Metadata, versions, active version, history
├── audit.jsonl                    # Append-only lifecycle audit records
└── artifacts/
    └── {SYMBOL}/
        ├── v0/
        │   ├── linear_regression.pkl
        │   ├── decision_tree.pkl
        │   ├── random_forest.pkl
        │   ├── svr.pkl
        │   ├── svr_scaler.pkl
        │   └── xgboost.pkl
        └── v1/
            └── ...
```

`registry.json` is written through a temporary file and atomically replaced. An
existing version's artifact directory is never reused or overwritten. A failed
training run removes its partial registry entry and artifact directory before
returning an error.

## 2. Versioning

- Versions are monotonic per symbol: `v0`, `v1`, `v2`, ...
- A version's `model_id` is `{SYMBOL}:{version}`.
- The next version number is derived from the existing version keys, not from a
  timestamp or a mutable counter.
- If a candidate fails during training or artifact writing, the reserved version
  is removed and the next attempt uses the same number.
- Artifacts are immutable once written. Replacing a model means creating a new
  version, not editing `vN`.

## 3. Lifecycle

```text
train candidate -> candidate (approved=false)
approve         -> candidate (approved=true)
activate        -> active
deactivate      -> inactive (active_version=null)
rollback        -> previous active version becomes active again
```

Important rules:

1. **Training does not activate.** A newly trained candidate has
   `status = "candidate"` and `approved = false`.
2. **Approval is explicit.** `approve_version` records `approved_by` and
   `approved_at`, and writes an audit event.
3. **Activation requires `approved=true`.** The service rejects activation
   without explicit approval, even if the version is already marked approved.
4. **One active version per symbol.** Activating a version marks any other
   active version `inactive`.
5. **Rollback requires a prior activation.** The most recent different version
   in the activation history is selected; if none exists, the request fails.
6. **Artifact validation precedes activation and prediction.** A version whose
   feature schema, artifact schema version, model files, or scaler is missing or
   incompatible cannot be activated or loaded.
7. **Deactivation does not delete artifacts.** It clears `active_version` and
   marks the prior active version inactive.

## 4. Candidate training

`POST /api/v2/models/{symbol}/train` submits a background job that calls
`ModelRegistryService.train_candidate()`.

Training details:

| Item | Behavior |
|------|----------|
| History | Request `period` or `TRAINING_PERIOD` (default `1y`) |
| Minimum rows | 80 feature rows |
| Split | Chronological 80/20 (`TRAIN_TEST_SPLIT = 0.2`) |
| Models | Linear regression, decision tree, random forest, SVR (with scaler), XGBoost |
| Validation | Metrics on the later 20% only |
| Ensemble | Fixed equal-weight mean of the five models |
| Baseline | Naive persistence (`current_close`) |
| Artifacts | Written under `model_registry/artifacts/{SYMBOL}/{version}/` |
| Legacy artifacts | Never touched |
| Status | `candidate` |
| Audit | `candidate_created` |

The candidate entry stores:

- feature columns and feature-schema version;
- data source, synthetic-data flag, raw/clean row counts, and a SHA-256
  fingerprint of the exact cleaned OHLCV rows used for training;
- training start/end and sample counts;
- validation metrics for every model, the ensemble, and the baseline;
- `candidate_vs_active` comparison when a prior active version exists;
- artifact filenames and relative artifact directory;
- hyperparameters and SVR preprocessing diagnostics;
- `production_artifact_unchanged: true`.

The data fingerprint and source label make the candidate's training evidence
distinguishable from a walk-forward report and from real-market evaluation.

## 5. Approval and activation

Approval and activation are separate, explicit actions. Training never approves
or activates a candidate.

### Attach evaluation evidence

```http
POST /api/v2/models/TATASTEEL.NS/evidence/v0
Authorization: Bearer <admin-jwt>
Content-Type: application/json

{ "report_id": "TATASTEEL_NS_walk_forward.json" }
```

The report must be a completed walk-forward report for the same symbol. The
registry validates its status, selected model, development metrics, baseline
comparison, generation time, data fingerprint, random seed, and exact feature
schema. It stores:

- report ID, SHA-256 hash, and generation/attachment timestamps;
- dataset period, data source, and dataset fingerprint;
- random seed and full evaluation configuration;
- feature schema and selected model;
- development metrics, final holdout metrics, and baseline comparison.

Reproducibility metadata is therefore part of the approval record, not only the
report file. Attaching new evidence resets any existing approval.

### Approve

```http
POST /api/v2/models/TATASTEEL.NS/approve/v0
Authorization: Bearer <admin-jwt>
Content-Type: application/json

{
  "approved": true,
  "evaluation_report_id": "TATASTEEL_NS_walk_forward.json"
}
```

Approval first attaches and validates the completed walk-forward report, then
sets `approved`, `approved_at`, and `approved_by`. A candidate without completed
evaluation evidence cannot be approved. The Express proxy fills `approved_by`
from the authenticated user; do not rely on a client-supplied identity.

### Activate

```http
POST /api/v2/models/TATASTEEL.NS/activate/v0
Authorization: Bearer <admin-jwt>
Content-Type: application/json

{ "approved": true }
```

Activation:

1. loads the version entry;
2. requires that the version is already approved with attached evidence;
3. re-validates the evidence and artifact manifest;
4. marks other active versions inactive;
5. marks this version `active`;
6. records `activated_at`, `activated_by`, and activation history;
7. writes a `version_activated` audit event.

If validation fails, no active version changes. A request to activate an
unapproved candidate fails rather than auto-approving it.

### Rollback

```http
POST /api/v2/models/TATASTEEL.NS/rollback
Authorization: Bearer <admin-jwt>
Content-Type: application/json

{ "approved": true }
```

Selects the most recent previously active version that is not the current one,
validates its artifacts, and activates it. A rollback with no prior activation
fails rather than guessing.

### Deactivate

```http
POST /api/v2/models/TATASTEEL.NS/deactivate
Authorization: Bearer <admin-jwt>
```

Clears the active version and marks the previous active entry inactive. There is
no registered-model prediction until another version is activated.

## 6. Artifact compatibility

Each version stores:

```json
{
  "artifact_compatibility": {
    "schema_version": 1,
    "feature_columns": ["Open", "High", "..."],
    "target_formulation": "absolute_price",
    "model_names": ["linear_regression", "decision_tree", "random_forest", "svr", "xgboost"],
    "has_svr_scaler": true
  }
}
```

Validation checks:

- the registry directory is not inside (and does not equal) `saved_models`;
- the artifact directory resolves under the registry root;
- the manifest contains exactly the five model artifacts and one SVR scaler;
- every artifact name is a plain `.pkl` filename, not a path;
- every required artifact exists;
- the stored feature list exactly matches the current feature engineering
  order and the version entry's feature list;
- the artifact schema version is supported;
- the target formulation is `absolute_price`;
- the compatibility model list matches the current model list;
- `has_svr_scaler` is true;
- each artifact path resolves inside its version directory.

This prevents loading an old model against a changed feature set, a missing
model, a path-traversal attempt, or an artifact set that was partially copied.

## 7. Registered-model prediction

`POST /api/v2/forecasting/predict/{symbol}`:

1. Requires a JWT.
2. Loads the active version.
3. Validates artifacts.
4. Fetches six months of history and builds the latest feature vector.
5. Runs all five models and the equal-weight ensemble.
6. Computes `predicted_return = ensemble / current_price − 1`.
7. Applies the ±1% signal threshold: `BUY`, `SELL`, or `HOLD`; `N/A` if no
   finite ensemble is available.
8. If `record` is true (the Express proxy sets it), appends a monitoring record.
9. Returns model version, feature timestamp, current price, predicted price,
   predicted return, per-model predictions, ensemble prediction, and artifact
   schema version.

The Express proxy also stores a sanitized `Prediction` document in MongoDB with
`algorithm = registry:{version}`, so existing history/report views can show the
registered-model prediction. The legacy `/api/predictions` inference path is not
used.

If no registered model is active, the AI service returns a registry error and
Express translates it to HTTP 409. There is no silent fallback to
`saved_models/`.

## 8. Audit log

`audit.jsonl` is append-only. Events include:

- `candidate_created`
- `evaluation_evidence_attached`
- `candidate_approved` / `candidate_unapproved`
- `version_activated`
- `version_deactivated`

Each record contains a UTC timestamp, event name, symbol, version, actor, and
relevant previous/active version information. The audit log is operational
evidence, not a tamper-proof ledger; protect the directory and ship it to
immutable storage if audit retention is required.

## 9. Monitoring link

Registered prediction records are written to
`monitoring/predictions/{SYMBOL}.jsonl` by the monitoring service. They include
the model ID, version, feature timestamp, current price, predicted price,
predicted return, signal, per-model predictions, and status `pending`.

Once the next session is available, an admin calls
`POST /api/v2/monitoring/{symbol}/update-actuals` to attach the actual price and
compute error, directional correctness, and completed-prediction metrics. See
[API_DOCUMENTATION.md](API_DOCUMENTATION.md) and
[ML_METHODOLOGY.md](ML_METHODOLOGY.md).

## 10. Operational checklist

Before activating a candidate:

- [ ] Run a completed walk-forward evaluation for the symbol.
- [ ] Confirm the report symbol, period, feature schema, selected model,
  metrics, baseline comparison, seed, and generation time.
- [ ] Review its development and holdout metrics and `candidate_vs_active`
  comparison.
- [ ] Confirm the validation split is chronological and the baseline is present.
- [ ] Confirm the feature schema matches the running service.
- [ ] Attach the report as evaluation evidence.
- [ ] Approve with the correct admin account.
- [ ] Confirm the artifact directory is present and readable.
- [ ] Activate only after a successful approval.
- [ ] Make one v2 prediction and confirm the returned version and timestamp.
- [ ] Monitor completed predictions and drift; roll back on a documented
  deterioration, not on a single bad day.

For rollback:

- [ ] Confirm the target version is the intended previous version and was
  previously approved with evidence.
- [ ] Confirm its artifacts still validate against the current feature schema.
- [ ] Record the incident/reason operationally.
- [ ] Run a post-rollback prediction and monitoring check.

## 11. Security and limitations

- Every FastAPI API route requires the `X-Internal-Service-Token` service
  secret. Express enforces JWT authentication and `adminOnly` for lifecycle
  operations, then forwards the service token server-side.
- The registry cannot be placed inside `saved_models/`.
- Approval requires a completed, schema-matched walk-forward report; activation
  requires prior approval and attached evidence.
- Version numbers and symbols are validated; artifact paths are constrained with
  `realpath` checks and plain `.pkl` filename validation.
- The registry is file-backed and uses a process-local lock. It is suitable for
  a single research service process, not for concurrent writers across multiple
  hosts.
- The registry does not provide a database transaction across `registry.json`
  and artifact writes. A crash during training is handled by removing the
  partial entry and artifact directory on the next exception path; a crash that
  kills the process mid-write can leave orphaned files that an operator must
  inspect.
- Evidence hashes detect report changes made after attachment, but a writer
  with filesystem access can still alter the registry. Protect the registry and
  report directories with host-level access control.
- Activation does not prove that a model is profitable or statistically better.
  It only proves that the version is approved, evidence-attached, and
  artifact-compatible.
- No live registry artifacts are created by the test suite; tests use temporary
  directories. The Model registry directory in this working tree is empty until
  a candidate is explicitly trained.
