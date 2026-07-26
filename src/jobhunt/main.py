import argparse
import logging
import sys

from .config import load_config
from .notify import send_email
from .state import load_state, save_state
from .sources.base import SOURCE_HANDLERS
from . import sources  # noqa: F401  registers SOURCE_HANDLERS

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("jobhunt")

FAILURE_ALERT_THRESHOLD = 3


def render_email(new_items_by_source, failing_sources, recovered_sources):
    html_parts = []
    text_parts = []

    for src_id, items in new_items_by_source.items():
        html_parts.append(f"<h3>{src_id}</h3><ul>")
        text_parts.append(f"{src_id}:")
        for item in items:
            extra = f" ({item['extra']})" if item.get("extra") else ""
            html_parts.append(f"<li><a href='{item['url']}'>{item['title']}</a>{extra}</li>")
            text_parts.append(f"  - {item['title']}{extra} {item['url']}")
        html_parts.append("</ul>")

    if failing_sources:
        html_parts.append("<h3>Sources failing repeatedly</h3><ul>")
        for src_id, err in failing_sources.items():
            html_parts.append(f"<li>{src_id}: {err}</li>")
            text_parts.append(f"FAILING: {src_id}: {err}")
        html_parts.append("</ul>")

    if recovered_sources:
        html_parts.append("<h3>Sources recovered</h3><ul>")
        for src_id in recovered_sources:
            html_parts.append(f"<li>{src_id}</li>")
            text_parts.append(f"RECOVERED: {src_id}")
        html_parts.append("</ul>")

    return "\n".join(html_parts), "\n".join(text_parts)


def run(dry_run=False, seed_state=False):
    config_sources = load_config()
    state = load_state()
    state.setdefault("sources", {})

    pending_state_updates = {}
    new_items_by_source = {}
    failing_sources = {}
    recovered_sources = []
    any_new_failure_or_recovery = False

    for src in config_sources:
        if not src.get("enabled", True):
            continue

        src_id = src["id"]
        src_state = state["sources"].get(src_id, {})
        handler = SOURCE_HANDLERS.get(src["type"])
        if handler is None:
            raise ValueError(f"unknown source type {src['type']!r} for {src_id!r}")

        try:
            result = handler(src, src_state)
        except Exception as exc:
            failures = src_state.get("consecutive_failures", 0) + 1
            pending_state_updates[src_id] = {
                **src_state,
                "consecutive_failures": failures,
                "last_error": str(exc),
            }
            log.info("%s: ERROR (%d consecutive) - %s", src_id, failures, exc)
            if failures == FAILURE_ALERT_THRESHOLD:
                failing_sources[src_id] = str(exc)
                any_new_failure_or_recovery = True
            continue

        log.info("%s: %s", src_id, result.summary)

        if src_state.get("consecutive_failures", 0) >= FAILURE_ALERT_THRESHOLD:
            recovered_sources.append(src_id)
            any_new_failure_or_recovery = True

        pending_state_updates[src_id] = {
            **src_state,
            **result.state_patch,
            "consecutive_failures": 0,
            "last_error": None,
        }
        if result.new_items:
            new_items_by_source[src_id] = result.new_items

    if seed_state:
        state["sources"] = pending_state_updates
        save_state(state)
        log.info("Seeded state.json with current baseline; no email sent.")
        return

    has_anything_to_report = bool(new_items_by_source) or any_new_failure_or_recovery

    if not has_anything_to_report:
        state["sources"].update(pending_state_updates)
        if not dry_run:
            save_state(state)
        log.info("Nothing new to report.")
        return

    html_body, text_body = render_email(new_items_by_source, failing_sources, recovered_sources)

    subject_bits = []
    if new_items_by_source:
        subject_bits.append(f"{sum(len(v) for v in new_items_by_source.values())} new")
    if failing_sources:
        subject_bits.append(f"{len(failing_sources)} failing")
    if recovered_sources:
        subject_bits.append(f"{len(recovered_sources)} recovered")
    subject = "Job hunt alert: " + ", ".join(subject_bits)

    if dry_run:
        print(f"SUBJECT: {subject}\n")
        print(text_body)
        log.info("Dry run - not sending email, not persisting seen-state.")
        return

    send_email(subject, html_body, text_body)
    state["sources"].update(pending_state_updates)
    save_state(state)
    log.info("Email sent and state updated.")


def main():
    parser = argparse.ArgumentParser(description="Scan configured job/fellowship sources and email new matches.")
    parser.add_argument("--test-email", action="store_true", help="Send a canned test email and exit.")
    parser.add_argument("--dry-run", action="store_true", help="Run detection, print the email, send nothing.")
    parser.add_argument("--seed-state", action="store_true", help="Write current results as baseline, send nothing.")
    args = parser.parse_args()

    if args.test_email:
        send_email("Job hunt scanner - test email", "<p>This is a test email from your job hunt scanner.</p>")
        log.info("Test email sent.")
        return

    try:
        run(dry_run=args.dry_run, seed_state=args.seed_state)
    except Exception:
        log.exception("Fatal error")
        sys.exit(1)


if __name__ == "__main__":
    main()
