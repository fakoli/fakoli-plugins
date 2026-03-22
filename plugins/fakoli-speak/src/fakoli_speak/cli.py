"""CLI entrypoint for fakoli-speak."""

import argparse
import json
import os
import sys

from dotenv import load_dotenv

from . import autospeak, cost, registry, tts
from .tts import TTSError


def cmd_speak(args: argparse.Namespace) -> None:
    if args.text:
        text = " ".join(args.text)
    elif not sys.stdin.isatty():
        text = sys.stdin.read()
    else:
        raise TTSError("No text provided. Pipe text in or pass as argument.")

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
    print(f"Status:    {state}")
    print(f"Provider:  {s['provider_display']} ({s['provider']})")
    print(f"Voice:     {s['voice_id']}")
    print(f"Model:     {s['model_id']}")


def cmd_voices(_args: argparse.Namespace) -> None:
    provider = registry.get_provider()
    voices = tts.list_voices()
    fmt = "{:<25} {:<20} {:<12} {:<10}"
    print(f"Voices for {provider.display_name} ({provider.name}):")
    print(fmt.format("VOICE_ID", "NAME", "LANGUAGE", "GENDER"))
    print("-" * 67)
    for v in voices:
        print(fmt.format(
            v["voice_id"][:24],
            v["name"][:19],
            v["language"][:11],
            v["gender"][:9],
        ))
    print(f"\n{len(voices)} voices available.")
    print(f"Set FAKOLI_SPEAK_PROVIDER or the provider-specific voice env var in ~/.env to switch.")


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
    print(f"=== TTS Usage ({s['provider']}) ===")
    print(f"Today:     {s['today_requests']} requests, "
          f"{s['today_characters']:,} chars, ${s['today_cost_usd']:.4f}")
    print(f"All time:  {s['total_requests']} requests, "
          f"{s['total_characters']:,} chars, ${s['total_cost_usd']:.4f}")
    print(f"Rate:      ${s['cost_per_1k_chars']:.2f} per 1K characters")


def cmd_provider(args: argparse.Namespace) -> None:
    if args.name:
        provider = registry.get_provider(args.name)
        provider.validate_config()
        print(f"Provider: {provider.display_name} ({provider.name})")
        print(f"Voice: {provider.get_voice_id()}")
        print(f"Model: {provider.get_model_id()}")
        rate = provider.get_default_cost_rate()
        print(f"Rate: ${rate.cost_per_1k_chars:.4f}/1K chars")
        print(f"\nTo persist: add FAKOLI_SPEAK_PROVIDER={provider.name} to ~/.env")
    else:
        current = registry.get_provider()
        all_names = registry.get_provider_names()
        print(f"Active:    {current.display_name} ({current.name})")
        print(f"Available: {', '.join(all_names)}")
        rate = current.get_default_cost_rate()
        print(f"Rate:      ${rate.cost_per_1k_chars:.4f}/1K chars")
        print(f"\nSet FAKOLI_SPEAK_PROVIDER in ~/.env to switch.")


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
    except TTSError:
        pass  # Hook must never crash or block


def main() -> None:
    load_dotenv(dotenv_path=os.path.expanduser("~/.env"))

    parser = argparse.ArgumentParser(
        prog="fakoli-speak",
        description="Multi-provider TTS for Claude Code",
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

    # provider
    p_provider = sub.add_parser("provider", help="Show or switch TTS provider")
    p_provider.add_argument("name", nargs="?", help="Provider name")
    p_provider.set_defaults(func=cmd_provider)

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

    try:
        args.func(args)
    except TTSError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
