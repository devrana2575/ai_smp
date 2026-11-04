# Contributing

Thank you for improving AI_SMP. This project combines a legacy prediction app
with research and model-lifecycle features, so contributions must preserve the
existing application while keeping evaluation honest.

## 1. Before you start

- Open an issue or discussion for non-trivial changes so the approach can be
  reviewed first.
- Do not include real brokerage credentials, API keys, JWTs, `.env` files, or
  private market data in a contribution.
- If your change affects evaluation, backtesting, model selection, or activation,
  read [EVALUATION_METHODOLOGY.md](EVALUATION_METHODOLOGY.md),
  [BACKTESTING_METHODOLOGY.md](BACKTESTING_METHODOLOGY.md), and
  [MODEL_REGISTRY.md](MODEL_REGISTRY.md) before coding.

## 2. Branching and scope

- Branch from the current integration branch.
- Use descriptive names: `feature/...`, `fix/...`, `docs/...`, `test/...`.
- Keep each pull request focused. Do not mix refactors, new experiments, and
  unrelated UI changes.
- Do not rewrite history or force-push a shared branch.
- Do not delete or overwrite another contributor's artifacts or uncommitted work.

## 3. Development setup

Follow [DEVELOPMENT_SETUP.md](DEVELOPMENT_SETUP.md). In short:

```powershell
cd ai-service
.\venv\Scripts\python.exe -m pytest -q
ruff check app tests scripts

cd ..\backend
npm test
npm run lint

cd ..\frontend
npm run lint
npm run build
```

Run the relevant checks before opening a pull request. If a check cannot run in
your environment, say so explicitly in the pull request.

## 4. Coding standards

### Python

- Follow the existing module layout and naming.
- Keep research services separate from production training/prediction.
- Add type hints for new public functions where practical.
- Use `ruff check` with the repository's `ruff.toml` baseline.
- Do not add broad `except Exception` blocks without a reason; API boundaries may
  translate service errors, but internal code should fail clearly.
- Do not use random shuffling or future-looking features in training/evaluation
  code.

### JavaScript / React

- Follow the existing React function-component and hooks style.
- Keep API calls in `src/services/`; keep pages focused on presentation and state.
- Run `npm run lint`.
- Avoid introducing new runtime dependencies without justification.
- Do not commit `dist/`, `node_modules/`, or `.env` files.

### Documentation

- Update the relevant methodology or API document when behavior changes.
- Label simulated results and evaluation periods.
- Do not market backtest returns as expected future performance.

## 5. Non-negotiable research rules

1. **No leakage.** No shuffling, no future-derived features, no target
   contamination across folds.
2. **Locked holdout.** Never tune, select, or assign ensemble weights using the
   final holdout.
3. **Identical boundaries.** When comparing target formulations, reuse the same
   dataset construction, folds, and holdout split.
4. **Abstention is not error.** A zero predicted movement is an abstention.
   Report directional accuracy only on non-zero signals and include coverage and
   abstention rate.
5. **Next-open execution.** Backtest signals form at the feature-day close and
   execute at the next session's open.
6. **No fabricated metrics.** If a metric is undefined, return `null` and explain
   why. Do not substitute zero or a made-up score.
7. **No overwriting production artifacts.** Research candidates go under
   `model_registry/`; activation is explicit and audited.
8. **Do not claim profitability.** Report actual results, including negative
   ones, and state the limitations.

Any pull request that changes these rules needs an explicit methodology review.

## 6. Tests

Add or update tests for:

- new metric definitions and edge cases (empty arrays, zero movement, zero
  actuals, non-finite values);
- fold construction and holdout isolation;
- backtest execution timing, costs, and trade accounting;
- registry lifecycle, artifact path validation, and rollback;
- monitoring pagination, actuals matching, and drift thresholds;
- API validation, authentication boundaries, and structured errors.

Use synthetic data in unit tests. Do not make tests depend on live Yahoo Finance
or a production MongoDB. If an integration test needs external data, mark it
clearly and skip it by default.

Current suite: `89` Python tests and `3` Node tests. Keep them green.

## 7. Commit messages

Use a short imperative subject and a body that explains the reasoning:

```text
feat: add abstention-aware directional metrics

Zero predicted movement now counts as abstention. Coverage and abstention
rate are reported, and undefined directional accuracy is null instead of zero.
```

Prefixes: `feat:`, `fix:`, `test:`, `docs:`, `refactor:`, `chore:`, `security:`.

Do not commit generated secrets, personal `.env` values, or huge report files
unless the repository policy explicitly calls for them.

## 8. Pull-request checklist

- [ ] The change is scoped and described.
- [ ] Existing legacy behavior is preserved or the change is documented.
- [ ] New behavior has tests.
- [ ] `pytest`, `ruff`, backend tests/lint, frontend lint/build pass.
- [ ] No secrets or private data are included.
- [ ] No production model or `saved_models/` artifact is overwritten.
- [ ] Evaluation/backtest changes preserve chronological integrity and the
  locked holdout.
- [ ] Results are labelled as simulations and include limitations.
- [ ] Documentation and API examples are updated.
- [ ] Dependency changes are reviewed; do not run `npm audit fix --force`
  blindly.
- [ ] The diff contains no unrelated formatting churn.

## 9. Reporting bugs and security issues

For ordinary bugs, include:

- the service affected (frontend, backend, AI service);
- exact command or request;
- expected vs actual behavior;
- relevant logs with secrets removed;
- Python/Node versions and OS.

For a security issue (auth bypass, path traversal, secret exposure, unsafe
artifact loading), do not open a public issue with exploit details. Contact the
maintainer privately or use the repository's security-reporting channel.

## 10. License

By contributing, you agree that your contribution is licensed under the
repository's MIT license.
