// Exercises the TypeScript guard through Pi's actual extension loader.  This
// is deliberately local: no model provider is started or contacted.
import * as assert from "node:assert/strict";
import { createRequire } from "node:module";
import { mkdtemp, readFile, rm, symlink, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";

const packageDir = process.env.PI_PACKAGE_DIR;
if (!packageDir) throw new Error("PI_PACKAGE_DIR must identify the reviewed Pi package");

const root = resolve(new URL("..", import.meta.url).pathname);
const guard = join(root, "scripts", "pi_scoped_fs_tools.ts");
const require = createRequire(import.meta.url);
const { createJiti } = require(join(packageDir, "node_modules", "jiti", "lib", "jiti.cjs"));
const jiti = createJiti(guard, {
  interopDefault: true,
  fsCache: false,
  alias: {
    "@earendil-works/pi-ai": join(packageDir, "node_modules", "@earendil-works", "pi-ai", "dist", "index.js"),
    "@earendil-works/pi-coding-agent": join(packageDir, "dist", "index.js"),
  },
});
const module = await jiti.import(guard);
const tools = new Map();
module.default({ registerTool: (tool) => tools.set(tool.name, tool) });
assert.deepEqual([...tools.keys()].sort(), ["edit", "read", "write"]);

const scratch = await mkdtemp(join(tmpdir(), "pi-scoped-tools-"));
const workspace = join(scratch, "fixture");
const outside = join(scratch, "oracle.py");
try {
  await (await import("node:fs/promises")).mkdir(workspace);
  await writeFile(join(workspace, "answer.txt"), "broken\n");
  await writeFile(outside, "trusted\n");
  await symlink(outside, join(workspace, "oracle-link"));
  const ctx = { cwd: workspace };
  await tools.get("edit").execute("call-ok", { path: "answer.txt", old_string: "broken", new_string: "fixed" }, undefined, undefined, ctx);
  assert.equal(await readFile(join(workspace, "answer.txt"), "utf8"), "fixed\n");
  await assert.rejects(
    tools.get("write").execute("call-escape", { path: "../oracle.py", content: "corrupted\n" }, undefined, undefined, ctx),
    /path escapes fixture/,
  );
  await assert.rejects(
    tools.get("write").execute("call-link", { path: "oracle-link", content: "corrupted\n" }, undefined, undefined, ctx),
    /symlinks are not allowed/,
  );
  assert.equal(await readFile(outside, "utf8"), "trusted\n");
} finally {
  await rm(scratch, { recursive: true, force: true });
}
