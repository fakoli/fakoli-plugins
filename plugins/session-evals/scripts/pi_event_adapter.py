#!/usr/bin/env python3
"""Trusted Pi JSON-event adapter for the smoke runner; never retains messages."""
import argparse, json, os, subprocess, sys

SAFE_ENV = {"HOME", "PATH", "TMPDIR", "TEMP", "TMP"}
DROP = ("KEY", "TOKEN", "SECRET", "PASSWORD", "ANTHROPIC", "OPENAI", "GEMINI")

def measured_events(lines, limits):
    counts = {"turns": 0, "tools": 0, "subprocesses": 1, "input_tokens": 0, "output_tokens": 0}
    for line in lines:
        try: event = json.loads(line)
        except (TypeError, json.JSONDecodeError): raise ValueError("truncated or invalid Pi event")
        if not isinstance(event, dict): raise ValueError("invalid Pi event")
        typ = event.get("type")
        if typ == "tool_execution_start":
            if event.get("toolName") not in {"read", "edit", "write"}: raise ValueError("disallowed Pi tool")
            counts["tools"] += 1
        if typ == "turn_end": counts["turns"] += 1
        if typ == "message_end":
            usage = event.get("message", {}).get("usage", {})
            counts["input_tokens"] += int(usage.get("input", 0) or 0)
            counts["output_tokens"] += int(usage.get("output", 0) or 0)
        if any(counts[k] > limits[k] for k in counts): raise ValueError("Pi event limit exceeded")
    if not counts["turns"]: raise ValueError("missing turn_end")
    return counts

def main(argv=None):
    ap=argparse.ArgumentParser(); ap.add_argument("--launcher", required=True); ap.add_argument("--prompt-file", required=True); ap.add_argument("--session-dir", required=True); ap.add_argument("--max-turns",type=int,required=True); ap.add_argument("--max-tools",type=int,required=True); ap.add_argument("--max-input-tokens",type=int,default=100000); ap.add_argument("--max-output-tokens",type=int,default=100000); args=ap.parse_args(argv)
    prompt=json.load(open(args.prompt_file,encoding="utf-8"));
    if not isinstance(prompt,dict) or not isinstance(prompt.get("prompt"),str): ap.error("prompt file needs prompt text")
    env={k:v for k,v in os.environ.items() if k in SAFE_ENV and not any(x in k.upper() for x in DROP)}
    cmd=[args.launcher,"--mode","json","--tools","read,edit,write","--no-approve","--no-context-files","--no-skills","--no-prompt-templates","--session-dir",args.session_dir,"-p",prompt["prompt"]]
    proc=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True,env=env)
    try: counts=measured_events(proc.stdout,{"turns":args.max_turns,"tools":args.max_tools,"subprocesses":1,"input_tokens":args.max_input_tokens,"output_tokens":args.max_output_tokens})
    except ValueError as exc: proc.kill(); print(json.dumps({"error":str(exc)})); return 1
    if proc.wait()!=0: return 1
    print(json.dumps(counts)); return 0
if __name__=="__main__": sys.exit(main())
