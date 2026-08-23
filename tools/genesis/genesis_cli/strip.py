import re

_COMMENT = r"(?:[#;]|//)"
_KIND = r"(?:module|service|topology)"
_HTML_END = r"(?:\s*-->)?"

BLOCK_START = re.compile(rf"^\s*(?:<!--\s*|{_COMMENT}\s*)>>>\s*({_KIND}:[\w-]+){_HTML_END}\s*$")
BLOCK_END = re.compile(rf"^\s*(?:<!--\s*|{_COMMENT}\s*)<<<\s*({_KIND}:[\w-]+){_HTML_END}\s*$")
LINE_TAG = re.compile(rf"{_COMMENT}\s*({_KIND}:[\w-]+)\s*$")


class MarkerError(Exception):
    pass


def strip_excluded(text: str, excluded: set[str], source: str = "<text>") -> str:
    kept = []
    open_blocks: list[str] = []

    for number, line in enumerate(text.splitlines(keepends=True), start=1):
        start = BLOCK_START.match(line)
        if start:
            open_blocks.append(start.group(1))
            if not any(name in excluded for name in open_blocks):
                kept.append(line)
            continue

        end = BLOCK_END.match(line)
        if end:
            if not open_blocks:
                raise MarkerError(f"{source}:{number}: '<<< {end.group(1)}' has no opener")
            opened = open_blocks.pop()
            if opened != end.group(1):
                raise MarkerError(
                    f"{source}:{number}: closes '{end.group(1)}' but '{opened}' is open"
                )
            if not any(name in excluded for name in [*open_blocks, opened]):
                kept.append(line)
            continue

        if any(name in excluded for name in open_blocks):
            continue

        tag = LINE_TAG.search(line)
        if tag and tag.group(1) in excluded:
            continue

        kept.append(line)

    if open_blocks:
        raise MarkerError(f"{source}: unclosed block(s): {', '.join(open_blocks)}")

    return "".join(kept)


def declared_markers(text: str) -> set[str]:
    found = set()
    for line in text.splitlines():
        for pattern in (BLOCK_START, BLOCK_END):
            match = pattern.match(line)
            if match:
                found.add(match.group(1))
        tag = LINE_TAG.search(line)
        if tag:
            found.add(tag.group(1))
    return found
