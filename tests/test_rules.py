from rulelab.rules import approx_tokens, parse_rules


def test_section_split_skips_single_title(sample_text):
    rf = parse_rules(sample_text, "section")
    titles = [r.title for r in rf.rules]
    assert titles == ["Preamble", "Repository overview", "Testing", "Style", "Commits"]
    assert rf.rules[1].start_line == 5


def test_render_full_roundtrip(sample_text):
    rf = parse_rules(sample_text, "section")
    assert rf.render() == sample_text


def test_render_without_removes_only_that_rule(sample_text):
    rf = parse_rules(sample_text, "section")
    style = next(r for r in rf.rules if r.title == "Style")
    out = rf.render({style.id})
    assert "## Style" not in out
    assert "## Commits" in out and "## Testing" in out
    assert "# not a heading" not in out  # the code block belonged to Style
    assert "\n\n\n" not in out


def test_code_fence_is_not_split(sample_text):
    rf = parse_rules(sample_text, "section")
    assert all("not a heading" not in r.title for r in rf.rules)


def test_bullet_split(sample_text):
    rf = parse_rules(sample_text, "bullet")
    titles = [r.title for r in rf.rules]
    assert "Run pytest -q before finishing." in titles
    item = next(r for r in rf.rules if r.title.startswith("Add a test"))
    assert "Keep tests small" in item.text  # continuation line stays with its bullet
    out = rf.render({item.id})
    assert "Add a test" not in out and "Keep tests small" not in out
    assert "## Testing" in out  # headings are always kept
    # bullets inside code blocks are not rules
    assert not any(r.title == "not a bullet" for r in rf.rules)


def test_no_headings_is_one_rule():
    rf = parse_rules("Be careful.\nAlways run tests.\n", "section")
    assert len(rf.rules) == 1
    assert rf.render({"R1"}) == ""


def test_unknown_rule_id(sample_text):
    rf = parse_rules(sample_text)
    try:
        rf.render({"R99"})
    except ValueError as e:
        assert "R99" in str(e)
    else:
        raise AssertionError("expected ValueError")


def test_title_only_preamble_is_fixed():
    rf = parse_rules("# CLAUDE.md\n\n## A\n\nx\n\n## B\n\ny\n")
    assert [r.title for r in rf.rules] == ["A", "B"]
    assert rf.render({"R1", "R2"}) == "# CLAUDE.md\n"


def test_multiple_h1_sections():
    rf = parse_rules("# One\n\na\n\n# Two\n\nb\n")
    assert [r.title for r in rf.rules] == ["One", "Two"]


def test_crlf_and_tokens():
    rf = parse_rules("## A\r\n\r\nabcd efgh\r\n")
    assert rf.rules[0].text == "## A\n\nabcd efgh"
    assert approx_tokens("abcd") == 1 and approx_tokens("") == 0
