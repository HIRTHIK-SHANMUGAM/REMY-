from remy.agents import orchestrator


def test_chat_history_persists_and_resets():
    orchestrator.reset_history()
    orchestrator._persist_turn("user", "remember the milk")
    orchestrator._persist_turn("assistant", "Noted.")
    loaded = orchestrator._load_history()
    assert loaded == [
        {"role": "user", "content": "remember the milk"},
        {"role": "assistant", "content": "Noted."},
    ]
    orchestrator.reset_history()
    assert orchestrator._load_history() == []


def test_history_load_skips_corrupt_lines():
    orchestrator.reset_history()
    path = orchestrator._history_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{"role":"user","content":"ok"}\nnot json\n'
                    '{"role":"tool","content":"skip me"}\n')
    assert orchestrator._load_history() == [{"role": "user", "content": "ok"}]
    orchestrator.reset_history()
