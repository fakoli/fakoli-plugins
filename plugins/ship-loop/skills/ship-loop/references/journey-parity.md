# Test one journey across its supported surfaces

Use this when a feature exposes the same workflow through CLI, browser, API or
another client. Start from the user's intent and the product's authoritative
state transition, then exercise each claimed surface. Keep fixtures and selectors
in the owning product repository; this is a test-design pattern, not a browser
framework.

| Journey | Starting state | CLI/API action | Browser action | Native result | Refusal/recovery | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| Approve reviewed work | Evidence present, review complete | Native approve command | Inspect bound preview and confirm | One authorized acceptance event | Changed evidence invalidates preview without partial writes | Command exit, event readback, browser observation |
| Continue independent work | One member awaiting review | Read current execution plan | Refresh member board | Unrelated eligible work remains available | Failed proof remains refused; dependencies retain their own gates | Native fixture plus observed UI state |
| Select a later item | More items than one page | Fetch the exact identifier | Page/filter, select and confirm | Selected identifier and scope match | Refresh/reorder cannot confirm another item | Native identifier plus browser focus/selection |

Adapt these examples to the actual product. Do not invent missing UI actions or
turn a reconstructed walkthrough into observed browser evidence.

For each journey:

1. State the actor, intent, initial state and expected event or durable result.
2. Exercise the CLI/API path with a disposable fixture and verify the native
   state, including a meaningful refusal case. An HTTP mock is not a browser run.
3. Exercise the real UI path where visual or interactive behavior is claimed.
   Check drag/drop destination feedback, keyboard operation, focus, pagination
   and narrow layouts only where the feature uses them.
4. Cross the boundary: a CLI change should appear after a browser refresh, and
   a browser action should be visible through the native read path. Keep the
   same fixture identity; a second coincidentally similar fixture proves less.
5. Preserve unknown responses and stale previews. Read current state before
   retrying a mutation; a transport failure does not prove nothing committed.

Keep the journey table next to product tests and user-facing instructions, using
stable journey IDs to connect them. Test the authority boundary in the shared
state engine as well as the client affordance. Shared logic does not prove that
every client submits the right identity, scope or evidence.

Record what each check establishes: command/HTTP behavior, actual browser
interaction, visual fit, accessibility, or scale. A successful provider read is
not rendering evidence; a small browser fixture is not thousand-card UI
qualification. Final acceptance and real-environment mutation still require the
task's authorization.
