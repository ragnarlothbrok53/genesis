from genesis_cli.inflect import pascal_case, pluralize, snake_case, title_case


def test_snake_case_from_pascal():
    assert snake_case("BlogPost") == "blog_post"


def test_snake_case_from_camel():
    assert snake_case("blogPost") == "blog_post"


def test_snake_case_from_kebab_and_spaces():
    assert snake_case("blog-post") == "blog_post"
    assert snake_case("blog post") == "blog_post"


def test_snake_case_handles_acronym_boundaries():
    assert snake_case("HTTPRequest") == "http_request"


def test_snake_case_is_idempotent():
    assert snake_case("blog_post") == "blog_post"


def test_pascal_case_round_trips_snake():
    assert pascal_case("blog_post") == "BlogPost"
    assert pascal_case("item") == "Item"


def test_title_case_adds_spaces():
    assert title_case("blog_post") == "Blog Post"


def test_pluralize_default_adds_s():
    assert pluralize("item") == "items"


def test_pluralize_sibilant_adds_es():
    assert pluralize("box") == "boxes"
    assert pluralize("bus") == "buses"


def test_pluralize_consonant_y_becomes_ies():
    assert pluralize("category") == "categories"


def test_pluralize_vowel_y_just_adds_s():
    assert pluralize("day") == "days"


def test_pluralize_irregular():
    assert pluralize("person") == "people"
    assert pluralize("child") == "children"
