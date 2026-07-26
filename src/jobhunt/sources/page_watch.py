import re

import requests
from bs4 import BeautifulSoup

from .base import SourceResult, register


@register("page_watch")
def check(config, state):
    url = config["url"]
    pattern = re.compile(config["extract_regex"])

    resp = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
    resp.raise_for_status()
    text = resp.text

    if config.get("css_selector"):
        soup = BeautifulSoup(text, "html.parser")
        node = soup.select_one(config["css_selector"])
        text = node.get_text(" ") if node else ""

    match = pattern.search(text)
    if not match:
        raise ValueError(f"extract_regex {config['extract_regex']!r} did not match content for {url!r}")

    snippet = match.group(0)
    last_snippet = state.get("last_snippet")

    new_items = []
    if snippet != last_snippet:
        open_keywords = config.get("open_keywords")
        notify_worthy = any(k in snippet for k in open_keywords) if open_keywords else True
        if notify_worthy:
            new_items.append({"title": f"Status changed: {snippet}", "url": url, "extra": ""})

    state_patch = {"last_snippet": snippet}
    summary = "unchanged" if snippet == last_snippet else f"changed: {last_snippet!r} -> {snippet!r}"
    return SourceResult(new_items=new_items, state_patch=state_patch, summary=summary)
