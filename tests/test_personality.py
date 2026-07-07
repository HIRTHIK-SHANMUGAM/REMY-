from remy.personality import TRAITS, Personality


def test_defaults_and_clamping():
    p = Personality()
    assert set(p.values) == {t.key for t in TRAITS}
    p.set("humour", 150)
    assert p.values["humour"] == 100
    p.set("humour", -5)
    assert p.values["humour"] == 0


def test_unknown_trait_rejected():
    p = Personality()
    try:
        p.set("bravado", 50)
        assert False, "should have raised"
    except KeyError:
        pass


def test_save_load_roundtrip():
    p = Personality()
    p.set("sarcasm", 77)
    p.set("verbosity", 12)
    p.save()
    q = Personality.load()
    assert q.values["sarcasm"] == 77
    assert q.values["verbosity"] == 12


def test_prompt_rendering_contains_percentages():
    p = Personality()
    p.set("humour", 85)
    section = p.render_prompt_section()
    assert "Humour: 85%" in section
    assert "PERSONALITY SETTINGS" in section
    for t in TRAITS:
        assert t.label in section


def test_identity_prompt_includes_personality_and_rules():
    from remy.identity import build_system_prompt
    prompt = build_system_prompt("# ROLE: TEST")
    assert "REMY" in prompt
    assert "RULES" in prompt
    assert "PERSONALITY SETTINGS" in prompt
    assert prompt.rstrip().endswith("# ROLE: TEST")
