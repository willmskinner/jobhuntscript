from dataclasses import dataclass, field

SOURCE_HANDLERS = {}


def register(type_name):
    def deco(fn):
        SOURCE_HANDLERS[type_name] = fn
        return fn
    return deco


@dataclass
class SourceResult:
    new_items: list = field(default_factory=list)   # [{"title", "url", "extra"}]
    state_patch: dict = field(default_factory=dict)  # merged into source state once notified
    summary: str = ""                                  # one-line log summary
