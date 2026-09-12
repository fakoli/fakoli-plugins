// Explicit Pi smoke-evaluation tools.  Run only with --no-builtin-tools and
// --no-extensions; these names intentionally replace Pi's unrestricted core
// read/edit/write tools for a disposable fixture session.
import { Type } from "@earendil-works/pi-ai";
import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";
import { constants } from "node:fs";
import { lstat, open, readFile, realpath } from "node:fs/promises";
import { isAbsolute, relative, resolve, sep } from "node:path";

const MAX_FILE_BYTES = 256 * 1024;

function result(text: string, isError = false) {
  return { content: [{ type: "text" as const, text }], details: { isError } };
}

function inside(root: string, target: string): boolean {
  const rel = relative(root, target);
  return rel === "" || (!rel.startsWith(`..${sep}`) && rel !== ".." && !isAbsolute(rel));
}

async function fixtureRoot(ctx: ExtensionContext): Promise<string> {
  const info = await lstat(ctx.cwd);
  if (info.isSymbolicLink() || !info.isDirectory()) throw new Error("fixture root must be a regular directory");
  return realpath(ctx.cwd);
}

async function checkedPath(ctx: ExtensionContext, raw: string, writing = false): Promise<string> {
  if (!raw || raw.includes("\0") || isAbsolute(raw)) throw new Error("path must be a non-empty relative path");
  const root = await fixtureRoot(ctx);
  const target = resolve(root, raw);
  if (!inside(root, target)) throw new Error("path escapes fixture");
  const pieces = relative(root, target).split(sep).filter(Boolean);
  let current = root;
  for (let index = 0; index < pieces.length; index += 1) {
    current = resolve(current, pieces[index]);
    try {
      const info = await lstat(current);
      if (info.isSymbolicLink()) throw new Error("symlinks are not allowed in fixture paths");
      if (index < pieces.length - 1 && !info.isDirectory()) throw new Error("path ancestor is not a directory");
    } catch (error: unknown) {
      if ((error as NodeJS.ErrnoException).code === "ENOENT" && writing) break;
      throw error;
    }
  }
  const parent = resolve(target, "..");
  if (!inside(root, await realpath(parent))) throw new Error("path escapes fixture");
  try {
    const info = await lstat(target);
    if (info.isSymbolicLink() || !info.isFile()) throw new Error("target must be a regular non-symlink file");
    if (!inside(root, await realpath(target))) throw new Error("path escapes fixture");
  } catch (error: unknown) {
    if ((error as NodeJS.ErrnoException).code !== "ENOENT") throw error;
    if (!writing) throw new Error("path does not exist");
  }
  return target;
}

async function writeChecked(ctx: ExtensionContext, path: string, content: string): Promise<void> {
  if (Buffer.byteLength(content) > MAX_FILE_BYTES) throw new Error("content exceeds smoke write limit");
  const target = await checkedPath(ctx, path, true);
  const handle = await open(target, constants.O_WRONLY | constants.O_CREAT | constants.O_TRUNC | constants.O_NOFOLLOW, 0o600);
  try { await handle.writeFile(content, "utf8"); } finally { await handle.close(); }
}

export default function (pi: ExtensionAPI): void {
  pi.registerTool({
    name: "read", label: "Fixture Read", description: "Read one regular UTF-8 file inside the smoke fixture.",
    parameters: Type.Object({ path: Type.String({ minLength: 1, maxLength: 1024 }) }),
    async execute(_id, params, _signal, _update, ctx) {
      try {
        const target = await checkedPath(ctx, params.path);
        const content = await readFile(target, "utf8");
        if (Buffer.byteLength(content) > MAX_FILE_BYTES) return result("file exceeds smoke read limit", true);
        return result(content);
      } catch (error) { return result((error as Error).message, true); }
    },
  });
  pi.registerTool({
    name: "write", label: "Fixture Write", description: "Write one regular UTF-8 file inside the smoke fixture.",
    parameters: Type.Object({ path: Type.String({ minLength: 1, maxLength: 1024 }), content: Type.String({ maxLength: MAX_FILE_BYTES }) }),
    async execute(_id, params, _signal, _update, ctx) {
      try { await writeChecked(ctx, params.path, params.content); return result("written"); }
      catch (error) { return result((error as Error).message, true); }
    },
  });
  pi.registerTool({
    name: "edit", label: "Fixture Edit", description: "Replace exactly one string in a regular UTF-8 fixture file.",
    parameters: Type.Object({ path: Type.String({ minLength: 1, maxLength: 1024 }), old_string: Type.String({ minLength: 1, maxLength: MAX_FILE_BYTES }), new_string: Type.String({ maxLength: MAX_FILE_BYTES }) }),
    async execute(_id, params, _signal, _update, ctx) {
      try {
        const target = await checkedPath(ctx, params.path);
        const content = await readFile(target, "utf8");
        if (content.split(params.old_string).length !== 2) return result("old_string must occur exactly once", true);
        await writeChecked(ctx, params.path, content.replace(params.old_string, params.new_string));
        return result("edited");
      } catch (error) { return result((error as Error).message, true); }
    },
  });
}
