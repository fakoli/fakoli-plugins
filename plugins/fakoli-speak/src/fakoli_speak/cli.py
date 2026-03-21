"""CLI entrypoint for fakoli-speak."""

import argparse
import json
import sys

from dotenv import load_dotenv

from . import autospeak, cost, tts


def cmd_speak(args: argparse.Namespace) -> None:
    if args.text:
        text = " ".join(args.text)
    elif not sys.stdin.isatty():
        text = sys.stdin.read()
    else:
        print("Error: No text provided. Pipe text in or pass as argument.", file=sys.stderr)
        sys.exit(1)

    result = tts.speak(text)
    print(
        f"Speaking ({result['characters']} chars, "
        f"${result['cost_usd']:.4f})"
    )


def cmd_stop(_args: argparse.Namespace) -> None:
    tts.stop()
    print("TTS stopped.")


def cmd_status(_args: argparse.Namespace) -> None:
    s = tts.status()
    state = f"Playing (PID: {s['pid']})" if s["playing"] else "Idle"
    print(f"Status:  {state}")
    print(f"Voice:   {s['voice_id']}")
    print(f"Model:   {s['model_id']}")


def cmd_voices(_args: argparse.Namespace) -> None:
    voices = tts.list_voices()
    fmt = "{:<25} {:<20} {:<10} {:<10}"
    print(fmt.format("VOICE_ID", "NAME", "ACCENT", "GENDER"))
    print("-" * 65)
    for v in voices:
        print(fmt.format(v["voice_id"][:24], v["name"][:19], v["accent"][:9], v["gender"][:9]))
    print(f"\n{len(voices)} voices available.")
    print("Set ELEVENLABS_VOICE_ID in ~/.env to switch.")


def cmd_cost(args: argparse.Namespace) -> None:
    if args.reset:
        cost.reset_usage()
        print("Usage data reset.")
        return

    if args.rate is not None:
        cost.set_cost_rate(args.rate)
        print(f"Cost rate set to ${args.rate:.2f} per 1K characters.")
        return

    if args.json:
        print(json.dumps(cost.get_summary(), indent=2))
        return

    s = cost.get_summary()
    print("=== ElevenLabs TTS Usage ===")
    print(f"Today:     {s['today_requests']} requests, "
          f"{s['today_characters']:,} chars, ${s['today_cost_usd']:.4f}")
    print(f"All time:  {s['total_requests']} requests, "
          f"{s['total_characters']:,} chars, ${s['total_cost_usd']:.4f}")
    print(f"Rate:      ${s['cost_per_1k_chars']:.2f} per 1K characters")


def cmd_autospeak(args: argparse.Namespace) -> None:
    if args.action == "on":
        autospeak.enable()
        print("Autospeak enabled. Responses will be read aloud automatically.")
    elif args.action == "off":
        autospeak.disable()
        print("Autospeak disabled.")
    else:
        state = "enabled" if autospeak.is_enabled() else "disabled"
        print(f"Autospeak is {state}.")


def cmd_autospeak_hook(_args: argparse.Namespace) -> None:
    """Called by the Stop hook — reads stdin, extracts text, speaks."""
    if not autospeak.is_enabled():
        return

    text = autospeak.process_hook_stdin()
    if text is None:
        return

    try:
        tts.speak(text)
    except (SystemExit, Exception):
        pass  # Hook must never crash or block


def main() -> None:
    load_dotenv(dotenv_path="~/.env")

    parser = argparse.ArgumentParser(
        prog="fakoli-speak",
        description="ElevenLabs TTS for Claude Code",
    )
    sub = parser.add_subparsers(dest="command")

    # speak
    p_speak = sub.add_parser("speak", help="Convert text to speech")
    p_speak.add_argument("text", nargs="*", help="Text to speak (or pipe via stdin)")
    p_speak.set_defaults(func=cmd_speak)

    # stop
    p_stop = sub.add_parser("stop", help="Stop playback")
    p_stop.set_defaults(func=cmd_stop)

    # status
    p_status = sub.add_parser("status", help="Show TTS status")
    p_status.set_defaults(func=cmd_status)

    # voices
    p_voices = sub.add_parser("voices", help="List available voices")
    p_voices.set_defaults(func=cmd_voices)

    # cost
    p_cost = sub.add_parser("cost", help="Show usage and cost")
    p_cost.add_argument("--reset", action="store_true", help="Reset usage data")
    p_cost.add_argument("--rate", type=float, help="Set cost per 1K chars (USD)")
    p_cost.add_argument("--json", action="store_true", help="Output as JSON")
    p_cost.set_defaults(func=cmd_cost)

    # autospeak
    p_auto = sub.add_parser("autospeak", help="Toggle automatic TTS on responses")
    p_auto.add_argument("action", nargs="?", choices=["on", "off"], help="Enable or disable")
    p_auto.set_defaults(func=cmd_autospeak)

    # autospeak-hook (internal, called by Stop hook)
    p_hook = sub.add_parser("autospeak-hook", help=argparse.SUPPRESS)
    p_hook.set_defaults(func=cmd_autospeak_hook)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
