# Excalidraw Diagram

Create editable `.excalidraw` scenes with a zero-dependency Node.js 18+ converter. Install this plugin through either the Codex or Claude marketplace in the repository README, then describe the diagram or provide an existing scene.

```sh
node scripts/convert.js skeleton.json diagram.excalidraw
node scripts/convert.js --stdin diagram.excalidraw < skeleton.json
node scripts/convert.js --modify existing.excalidraw additions.json updated.excalidraw
node --test tests/convert.test.js
```

Run those commands from this plugin directory or use absolute script paths. The converter prints a JSON result and exits nonzero on invalid input. It writes atomically, including in-place edits.

Skeleton IDs remain stable in output, so subsequent additions can connect to existing shapes by name. The modify operation supports additions with new IDs and a `remove` list. It preserves embedded images, extra scene fields, and app state; removing a frame detaches its children. Read older files to obtain their generated IDs.

Shapes, labeled arrows, lines, text and frames are supported. Frame bounds are computed from children, and explicit coordinates are preserved. Elbowed arrows are not supported. Text dimensions are approximate: import into an Excalidraw editor to verify complex or long-label layouts.

See [the skill](skills/excalidraw/SKILL.md) and [format reference](skills/excalidraw/references/format-reference.md). Browser previews use normal file import or the documented Excalidraw API, never internal React structures.
