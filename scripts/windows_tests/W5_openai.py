"""W5 - OpenAI Responses API: latency, timeout path and auth-failure path.

    set OPENAI_API_KEY=...        (PowerShell: $env:OPENAI_API_KEY = "...")
    set OPENAI_MODEL=<model id>   (or pass --model)
    uv run python scripts/windows_tests/W5_openai.py

The API key is read from the environment only. It is never printed, never written to the report
and never accepted on the command line. The model id is configuration: M0-08 (model selection)
needs current official API documentation and owner approval, so there is deliberately no default.
No price or quality claim is made; token usage is recorded as reported by the API.

Three scenarios: (1) normal calls, (2) a client with an absurdly small timeout must raise a
timeout/connection error that the caller can catch, (3) a deliberately invalid key must raise an
authentication error. (2) and (3) prove error handling does not crash the application.
"""

import argparse
import os
import sys
import time

from _common import Recorder, redact, stats

SENTENCES = (
    "You should not have come here.",
    "The gate is sealed. We cannot go back.",
    "Press E to open the chest.",
    "Quest updated: Find the missing merchant.",
)
INSTRUCTIONS = (
    "Translate the user's English game dialogue into natural Vietnamese. "
    "Reply with the translation only."
)


def is_timeout_or_connection_error(exc: BaseException, openai_module) -> bool:
    """True only for the SDK's timeout/connection errors (APITimeoutError subclasses the latter)."""
    return isinstance(exc, openai_module.APIConnectionError)


def is_auth_error(exc: BaseException, openai_module) -> bool:
    """True only for an HTTP 401 from the API; a network failure must not count as 'auth works'."""
    return isinstance(exc, openai_module.AuthenticationError)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--model", default=os.environ.get("OPENAI_MODEL"))
    parser.add_argument("--timeout", type=float, default=20.0, help="seconds for normal calls")
    parser.add_argument("--max-output-tokens", type=int, default=200)
    args = parser.parse_args()

    rec = Recorder("W5", "OpenAI Responses API integration")
    print("W5 - OpenAI Responses API")
    has_key = bool(os.environ.get("OPENAI_API_KEY"))
    rec.measure("api_key_present_in_env", has_key)
    if not has_key:
        return rec.skip("OPENAI_API_KEY is not set in the environment")
    if not args.model:
        return rec.skip("no model id: pass --model or set OPENAI_MODEL (no default by design)")
    rec.measure("model", args.model)

    try:
        import openai
        from openai import OpenAI
    except Exception as exc:  # noqa: BLE001
        rec.check("import openai", False, f"{type(exc).__name__}: {exc}")
        return rec.finish()
    rec.measure("openai_sdk_version", getattr(openai, "__version__", None))

    client = OpenAI(timeout=args.timeout, max_retries=0)

    # Model availability in THIS account (master prompt: check, do not assume).
    try:
        client.models.retrieve(args.model)
        rec.check("model is available to this API key (models.retrieve)", True, args.model)
    except openai.NotFoundError:
        rec.check("model is available to this API key (models.retrieve)", False, "404 not found")
    except Exception as exc:  # noqa: BLE001
        rec.check(
            "model is available to this API key (models.retrieve)",
            None,
            f"could not tell: {type(exc).__name__}: {redact(str(exc))[:150]}",
        )

    latencies: list[float] = []
    translations: dict[str, str] = {}
    usage: list[dict[str, int | None]] = []
    failures = 0
    for sentence in SENTENCES:
        start = time.perf_counter()
        try:
            response = client.responses.create(
                model=args.model,
                instructions=INSTRUCTIONS,
                input=sentence,
                max_output_tokens=args.max_output_tokens,
            )
        except Exception as exc:  # noqa: BLE001
            failures += 1
            rec.note(f"call failed: {type(exc).__name__}: {redact(str(exc))[:200]}")
            continue
        latencies.append((time.perf_counter() - start) * 1000)
        translations[sentence] = (response.output_text or "").strip()
        used = getattr(response, "usage", None)
        usage.append(
            {
                "input_tokens": getattr(used, "input_tokens", None),
                "output_tokens": getattr(used, "output_tokens", None),
            }
        )
    rec.extra["translations"] = translations
    rec.extra["usage"] = usage
    for source, target in translations.items():
        print(f"    {source}  ->  {target}")
    rec.check("all normal calls succeeded", failures == 0, f"{failures} failed")
    rec.check(
        "all translations non-empty",
        bool(translations) and all(t for t in translations.values()),
    )
    if latencies:
        rec.measure("latency_ms", stats(latencies))

    # (2) timeout path
    tiny = OpenAI(timeout=0.001, max_retries=0)
    caught: BaseException | None = None
    start = time.perf_counter()
    try:
        tiny.responses.create(model=args.model, input="ping", max_output_tokens=16)
    except Exception as exc:  # noqa: BLE001
        caught = exc
    rec.measure("timeout_path_ms", round((time.perf_counter() - start) * 1000))
    rec.check(
        "tiny timeout raises the SDK timeout/connection error (does not hang or crash)",
        caught is not None and is_timeout_or_connection_error(caught, openai),
        type(caught).__name__ if caught is not None else "no exception was raised",
    )

    # (3) auth failure path: a fake key made up for this test, not a credential
    bad = OpenAI(
        api_key="invalid-key-for-w5-auth-failure-test", timeout=args.timeout, max_retries=0
    )
    auth_error: BaseException | None = None
    try:
        bad.responses.create(model=args.model, input="ping", max_output_tokens=16)
    except Exception as exc:  # noqa: BLE001
        auth_error = exc
    rec.check(
        "invalid key raises AuthenticationError (HTTP 401), not some other failure",
        auth_error is not None and is_auth_error(auth_error, openai),
        type(auth_error).__name__ if auth_error is not None else "no exception was raised",
    )
    rec.note(
        "Owner: read the printed translations yourself; no quality score is computed. Record the "
        "model chosen and the date. Never paste the key into any file, issue or log."
    )
    return rec.finish()


if __name__ == "__main__":
    sys.exit(main())
