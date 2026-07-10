---
description: Run the full ship loop (sync, isolate, scope, implement, adversarial review gate, merge, follow-ups) on the current task
---

Use the `ship-loop` skill from the ship-loop plugin to run the procedure
end-to-end for: $ARGUMENTS

If no argument names the work, ask what feature/fix to ship, then follow the
skill's seven steps in order. The adversarial review (step 5) is the merge
gate — run it without being asked.
