import re

_IRREGULAR_PLURALS = {
    "person": "people",
    "child": "children",
    "man": "men",
    "woman": "women",
}


def snake_case(name: str) -> str:
    name = re.sub(r"[\s-]+", "_", name.strip())
    name = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", name)
    name = re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", "_", name)
    return name.lower().strip("_")


def pascal_case(name: str) -> str:
    return "".join(part.capitalize() for part in snake_case(name).split("_") if part)


def title_case(snake: str) -> str:
    return " ".join(part.capitalize() for part in snake.split("_") if part)


def pluralize(word: str) -> str:
    lower = word.lower()
    if lower in _IRREGULAR_PLURALS:
        return _IRREGULAR_PLURALS[lower]
    if lower.endswith(("s", "x", "z", "ch", "sh")):
        return word + "es"
    if lower.endswith("y") and len(lower) > 1 and lower[-2] not in "aeiou":
        return word[:-1] + "ies"
    return word + "s"
