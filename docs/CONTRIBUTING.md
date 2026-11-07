# Contributing

Thank you for improving AI_SMP. The project combines a React frontend, an
Express gateway, MongoDB storage, and an internal FastAPI machine-learning
service.

## 1. Before you start

- Open an issue or discussion for non-trivial changes so the approach can be
  reviewed first.
- Do not include real brokerage credentials, API keys, JWTs, `.env` files, or
  private market data in a contribution.
- If your change affects features, model selection, or prediction behavior, read
  [ML_METHODOLOGY.md](ML_METHODOLOGY.md) before coding.

## 2. Branching and scope

- Branch from the current integration branch.
- Use descriptive names: `feature/...`, `fix/...`, `docs/...`, `test/...`.
- Keep each pull request focused. Do not mix refactors and unrelated UI changes.
- Do not rewrite history or force-push a shared branch.
- Do not delete or overwrite another contributor's artifacts or uncommitted work.

## 3. Development setup

Follow [DEVELOPMENT_SETUP.md](DEVELOPMENT_SETUP.md). In short:

```powershell
cd ai-service
.\venv\Scripts\python.exe -m pytest -q
ruff check .

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
- Add type hints for new public functions where practical.
- Use `ruff check` with the repository's `ruff.toml` baseline.
- Do not add broad `except Exception` blocks without a reason; API boundaries may
  translate service errors, but internal code should fail clearly.
- Do not use random shuffling or future-looking features in training code.

### JavaScript / React

- Follow the existing React function-component and hooks style.
- Keep API calls in `src/services/`; keep pages focused on presentation and state.
- Run `npm run lint`.
- Avoid introducing new runtime dependencies without justification.
- Do not commit `dist/`, `node_modules/`, or `.env` files.

### Documentation

- Update the relevant API, architecture, or methodology document when behavior
  changes.
- Describe model outputs as estimates, not guarantees.
- Do not market historical performance as expected future performance.

## 5. Tests

Add or update tests for:

- new feature engineering or model behavior;
- metric definitions and edge cases (empty arrays, non-finite values);
- API validation and authentication boundaries;
- frontend state and API integration changes where practical.

Use synthetic data in unit tests. Do not make tests depend on live Yahoo Finance
or a production MongoDB. If an integration test needs external data, mark it
clearly and skip it by default.

Current suite: `48` Python tests and `5` Node tests. Keep them green.

## 6. Commit messages

Use a short imperative subject and a body that explains the reasoning:

```text
fix: validate symbols before fetching market data

Invalid symbols now fail with a clear validation error instead of a network
request.
```

Prefixes: `feat:`, `fix:`, `test:`, `docs:`, `refactor:`, `chore:`, `security:`.

Do not commit generated secrets, personal `.env` values, or large model files
unless the repository policy explicitly calls for them.

## 7. Pull-request checklist

- [ ] The change is scoped and described.
- [ ] Existing behavior is preserved or the change is documented.
- [ ] New behavior has tests.
- [ ] `pytest`, `ruff`, backend tests/lint, frontend lint/build pass.
- [ ] No secrets or private data are included.
- [ ] No production model or `saved_models/` artifact is overwritten without a
  backup and a documented reason.
- [ ] Documentation and API examples are updated.
- [ ] Dependency changes are reviewed; do not run `npm audit fix --force`
  blindly.
- [ ] The diff contains no unrelated formatting churn.

## 8. Reporting bugs and security issues

For ordinary bugs, include:

- the service affected (frontend, backend, AI service);
- exact command or request;
- expected vs actual behavior;
- relevant logs with secrets removed;
- Python/Node versions and OS.

For a security issue (auth bypass, path traversal, secret exposure), do not open
a public issue with exploit details. Contact the maintainer privately or use the
repository's security-reporting channel.

## 9. License

By contributing, you agree that your contribution is licensed under the
repository's MIT license.
