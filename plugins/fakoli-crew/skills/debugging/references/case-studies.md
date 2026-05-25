# Debugging Case Studies

Three worked examples of the 4-phase systematic debugging method. Each follows the same structure: symptom, wrong-fix temptation, root cause, and what each phase produced.

---

## Case Study 1 — Python: `ImportError` in a package that definitely exists

**Symptom:** A FastAPI application raises `ImportError: cannot import name 'AsyncSession' from 'sqlalchemy.orm'` in production. The same code runs fine on the developer's laptop. The package is present in `requirements.txt` and `pip show sqlalchemy` reports version `1.4.46`.

**Wrong-fix temptation:** Add `sqlalchemy` to `requirements.txt` again, or pin it to the exact version from the developer's machine — `sqlalchemy==1.4.46`. A junior would assume the package is missing or the wrong version and reinstall it.

---

### Phase 1: Root Cause Investigation

Read the full traceback. The final frames show:

```
File "/app/db/session.py", line 4, in <module>
    from sqlalchemy.orm import AsyncSession
ImportError: cannot import name 'AsyncSession' from 'sqlalchemy.orm'
  (/usr/local/lib/python3.9/site-packages/sqlalchemy/orm/__init__.py)
```

`AsyncSession` was added in SQLAlchemy 1.4. The production image reports `1.4.46`, so version looks fine. Check the actual installed path:

```bash
python -c "import sqlalchemy; print(sqlalchemy.__version__, sqlalchemy.__file__)"
# 1.3.23  /usr/local/lib/python3.9/site-packages/sqlalchemy/__init__.py
```

The running interpreter sees `1.3.23`, not `1.4.46`. `pip show` was queried in the wrong virtualenv — it reported the developer tooling environment, not the one the application process uses.

**Evidence gathered:** Two virtualenvs exist in the container. The app's process uses `python3.9` from the system path, which resolves to a separate virtualenv that was never upgraded.

---

### Phase 2: Pattern Analysis

Find the Dockerfile and compare the install step to a working service in the same repo:

Working service (`Dockerfile.auth`):
```dockerfile
RUN pip install --no-cache-dir -r requirements.txt
```

Broken service (`Dockerfile.api`):
```dockerfile
RUN pip install --no-cache-dir -r requirements.txt
RUN apt-get install -y python3.9
```

The `apt-get install python3.9` step installs a second Python binary *after* `pip install`. The new binary brings its own site-packages directory. When the container starts, `/usr/bin/python3.9` (from apt) is earlier on `PATH` than the virtualenv Python. The `apt` version has only the base packages; it never received the `pip install` run.

---

### Phase 3: Hypothesis and Test

**Hypothesis:** The application entrypoint resolves `python3.9` from `/usr/bin/` instead of the virtualenv, so it sees the unconfigured apt-installed interpreter.

Test:
```bash
# Inside the running container
which python3.9
# /usr/bin/python3.9        ← apt version

/usr/local/bin/python3.9 -c "from sqlalchemy.orm import AsyncSession; print('OK')"
# OK

/usr/bin/python3.9 -c "from sqlalchemy.orm import AsyncSession; print('OK')"
# ImportError: cannot import name 'AsyncSession'
```

Hypothesis confirmed.

---

### Phase 4: Implementation

Write a failing test (CI-level, not unit):

```bash
# tests/test_interpreter.sh
PYTHON=$(docker run --rm api-image which python3.9)
VERSION=$(docker run --rm api-image "$PYTHON" -c "import sqlalchemy; print(sqlalchemy.__version__)")
[ "$VERSION" = "1.4.46" ] || { echo "FAIL: wrong sqlalchemy $VERSION on $PYTHON"; exit 1; }
```

Fix: remove the redundant `apt-get install -y python3.9` line from the Dockerfile. The virtualenv Python is already on `PATH` via the base image's entrypoint script. Reinstall the image, run the test — it passes. Run the full integration suite — no regressions.

---

## Case Study 2 — TypeScript: Race Condition in Parallel `Promise.all` Writes

**Symptom:** An Express API endpoint that writes user preferences occasionally stores the wrong values. The bug reproduces roughly 1 in 20 requests and only under load. Unit tests always pass. The error shows up as a user seeing another user's theme setting.

**Wrong-fix temptation:** Wrap the write in a try/catch, add retry logic, or increase the database connection pool size. A junior would assume the issue is a transient network error or connection exhaustion and reach for infrastructure knobs.

---

### Phase 1: Root Cause Investigation

Read the endpoint code:

```typescript
app.post('/preferences', async (req, res) => {
  const userId = req.user.id;
  const { theme, language } = req.body;

  await Promise.all([
    db.set(`user:${userId}:theme`, theme),
    db.set(`user:${userId}:language`, language),
  ]);

  res.json({ ok: true });
});
```

No obvious bug on first read. Add structured logging to capture `userId` at entry and at each write:

```typescript
const userId = req.user.id;
logger.info({ userId, phase: 'start' });
await Promise.all([
  db.set(`user:${userId}:theme`, theme).then(() => logger.info({ userId, phase: 'theme-done' })),
  db.set(`user:${userId}:language`, language).then(() => logger.info({ userId, phase: 'lang-done' })),
]);
```

Under load, the log shows `userId` at `start` is correct, but occasionally `theme-done` and `lang-done` log *different* `userId` values than `start`. Something is mutating `req.user.id` mid-flight.

---

### Phase 2: Pattern Analysis

Find where `req.user` is set. The auth middleware:

```typescript
app.use(async (req, _res, next) => {
  req.user = await tokenCache.get(req.headers.authorization);
  next();
});
```

`tokenCache.get` is async. Compare to the working `/profile` endpoint, which reads `req.user.id` synchronously after middleware completes. The difference: `/preferences` is the only route that runs multiple parallel async writes. During the `await Promise.all(...)`, the event loop yields. Other incoming requests run their middleware, mutating `req.user` on the same request object through a shared reference.

Wait — `req` objects are per-request. Shared reference to *what*? Dig further: `tokenCache` is backed by a `Map` and returns the same object reference for cached tokens. Two concurrent requests with the same JWT (load-test traffic) get the *same* user object. Middleware assigns `req.user = <shared object>`, then a concurrent request mutates that shared object's `id` field before the writes complete.

---

### Phase 3: Hypothesis and Test

**Hypothesis:** `tokenCache.get` returns a mutable object reference shared across requests. A concurrent request mutates `user.id` on the shared object before the parallel writes resolve.

Test:

```typescript
it('does not mutate userId mid-flight when two requests share a cached token', async () => {
  const shared = { id: 'user-1', theme: 'dark' };
  tokenCache.set('token-abc', shared);

  const req1 = mockRequest({ authorization: 'token-abc', body: { theme: 'light', language: 'en' } });
  const req2 = mockRequest({ authorization: 'token-abc', body: { theme: 'dark', language: 'fr' } });

  // Simulate concurrent mutation mid-write
  const write1 = handler(req1);
  shared.id = 'user-2'; // another request mutated the cached object
  await write1;

  expect(await db.get('user:user-1:theme')).toBe('light'); // fails: key is 'user:user-2:theme'
});
```

Test fails. Hypothesis confirmed.

---

### Phase 4: Implementation

Fix: return a shallow copy from the cache so each request owns its user object.

```typescript
// Before
app.use(async (req, _res, next) => {
  req.user = await tokenCache.get(req.headers.authorization);
  next();
});

// After
app.use(async (req, _res, next) => {
  const cached = await tokenCache.get(req.headers.authorization);
  req.user = { ...cached }; // each request gets its own copy
  next();
});
```

Re-run the failing test — it passes. Run the full suite under `jest --runInBand` and under the load harness (`autocannon -c 50 -d 10`). No further cross-user writes observed. No regressions.

---

## Case Study 3 — Bash: Quoting Bug Silently Drops Files with Spaces

**Symptom:** A deployment script that archives log files leaves some files behind on servers whose hostnames contain a space in the directory path (a legacy convention on this team's staging fleet). The script runs without error, exits 0, but the backup archive is missing files. No error is logged.

**Wrong-fix temptation:** Add `set -e` to the script so it fails loudly, or rewrite it in Python. A junior would treat the silent success as a script reliability problem and reach for a stricter error mode or a different language, missing the underlying quoting issue.

---

### Phase 1: Root Cause Investigation

Read the full script:

```bash
#!/bin/bash
BACKUP_DIR=/opt/backups
LOG_DIR=/var/log/app

for f in $LOG_DIR/*.log; do
    gzip -c "$f" >> "$BACKUP_DIR/logs.tar.gz"
done
```

Run it manually with `bash -x` to trace execution:

```
+ for f in /var/log/app staging host/*.log
+ gzip -c /var/log/app
gzip: /var/log/app: Is a directory
+ gzip -c staging
gzip: staging: No such file or directory
+ gzip -c host/*.log
gzip: host/*.log: No such file or directory
```

The unquoted `$LOG_DIR` is word-split by the shell. When `LOG_DIR` contains `/var/log/app staging host` (a path with spaces, because the variable was set from a remote hostname that included spaces), the `for` loop iterates over three tokens instead of one path. `gzip` silently exits non-zero on each but the loop continues. The archive is written but empty of actual content.

**Evidence:** `$?` after the loop is 0 because the loop body itself never fails with a non-zero exit that the loop propagates; the loop construct exits 0 if all iterations complete regardless of individual command exit codes.

---

### Phase 2: Pattern Analysis

Find other scripts in the repo that iterate over files. The working `rotate-logs.sh`:

```bash
LOG_DIR="/var/log/app"
for f in "${LOG_DIR}"/*.log; do
    mv "$f" "${f}.rotated"
done
```

Every variable reference is double-quoted: `"${LOG_DIR}"`. The broken script has `$LOG_DIR` without quotes in the glob expansion. The shell performs word-splitting on unquoted variable substitution before glob expansion, so the path is split at the space before the glob `*.log` is applied.

---

### Phase 3: Hypothesis and Test

**Hypothesis:** The unquoted `$LOG_DIR` in the glob causes word-splitting when the path contains spaces, producing incorrect loop tokens that match no real files.

Test:

```bash
# Reproduce in isolation
LOG_DIR="/tmp/test dir"
mkdir -p "$LOG_DIR"
touch "$LOG_DIR/app.log"

# Unquoted (broken)
for f in $LOG_DIR/*.log; do echo "found: $f"; done
# found: /tmp/test
# found: dir/*.log   ← literal, no match

# Quoted (fixed)
for f in "${LOG_DIR}"/*.log; do echo "found: $f"; done
# found: /tmp/test dir/app.log
```

Hypothesis confirmed.

---

### Phase 4: Implementation

Write a test using `bats` (Bash Automated Testing System):

```bash
# tests/test_backup.bats
@test "backup script handles paths with spaces" {
  export LOG_DIR="/tmp/test log dir"
  mkdir -p "$LOG_DIR"
  echo "hello" > "$LOG_DIR/app.log"

  run bash backup.sh
  [ "$status" -eq 0 ]
  [ -s /opt/backups/logs.tar.gz ]  # archive is non-empty
  gunzip -c /opt/backups/logs.tar.gz | grep -q "hello"
}
```

Fix: quote every variable in the glob and in the loop body.

```bash
# Before
for f in $LOG_DIR/*.log; do
    gzip -c "$f" >> "$BACKUP_DIR/logs.tar.gz"
done

# After
for f in "${LOG_DIR}"/*.log; do
    gzip -c "$f" >> "${BACKUP_DIR}/logs.tar.gz"
done
```

Run the bats test — it passes. Run the full hook validation suite (`./tests/test-hooks-validation.sh`) — no regressions. Audit all other scripts for unquoted variables with `shellcheck backup.sh`; address the three additional warnings found.

---

## Summary

| # | Domain | Symptom | Wrong Fix | Root Cause |
|---|--------|---------|-----------|------------|
| 1 | Python / Docker | `ImportError` on a present package | Reinstall or re-pin the package | Two Python interpreters on PATH; app uses the unconfigured one |
| 2 | TypeScript / Async | Occasional cross-user data writes under load | Retry logic, bigger connection pool | Shared mutable object reference returned from token cache |
| 3 | Bash | Silent archive missing files on paths with spaces | Add `set -e`, rewrite in Python | Unquoted variable in glob causes word-splitting before expansion |

Each case reached the root cause only by completing Phase 1 (reading full traces and instrumenting for evidence) and Phase 2 (comparing against a working example line by line). Jumping straight to Phase 4 after Phase 1 — the most common shortcut — would have produced a plausible-looking but wrong fix in all three cases.
