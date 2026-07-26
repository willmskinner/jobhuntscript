import requests

from .base import SourceResult, register

GREENHOUSE_API = "https://boards-api.greenhouse.io/v1/boards/{board}/jobs"


@register("greenhouse_board")
def check(config, state):
    board = config["board"]
    keywords = [k.lower() for k in config.get("title_keywords", [])]

    resp = requests.get(GREENHOUSE_API.format(board=board), timeout=15)
    resp.raise_for_status()
    jobs = resp.json().get("jobs", [])

    matched = [j for j in jobs if not keywords or any(k in j["title"].lower() for k in keywords)]
    matched_ids = {str(j["id"]) for j in matched}
    seen_ids = set(state.get("seen_job_ids", []))

    new_jobs = [j for j in matched if str(j["id"]) not in seen_ids]
    new_items = [
        {
            "title": j["title"],
            "url": j["absolute_url"],
            "extra": (j.get("location") or {}).get("name", ""),
        }
        for j in new_jobs
    ]

    state_patch = {"seen_job_ids": sorted(seen_ids | matched_ids)}
    summary = f"{len(new_jobs)} new / {len(matched)} matched / {len(jobs)} total jobs"
    return SourceResult(new_items=new_items, state_patch=state_patch, summary=summary)
