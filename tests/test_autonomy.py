from datetime import datetime, timedelta, timezone

from remy import standing_orders, tasks
from remy.agents import watcher
from remy.memory.store import MemoryStore


def test_task_lifecycle_one_off():
    t = tasks.add_task("write report")
    assert t["status"] == "pending"
    assert any(x["id"] == t["id"] for x in tasks.due_tasks())
    tasks.mark_ran(t["id"])
    assert all(x["id"] != t["id"] for x in tasks.list_tasks())


def test_task_recurring_reschedules():
    t = tasks.add_task("poll feed", recur_minutes=30)
    tasks.mark_ran(t["id"])
    pending = [x for x in tasks.list_tasks() if x["id"] == t["id"]]
    assert pending and pending[0]["status"] == "pending"
    assert pending[0]["due_at"] is not None
    tasks.set_status(t["id"], "cancelled")


def test_overdue_detection():
    past = (datetime.now(timezone.utc) - timedelta(hours=30)).isoformat()
    t = tasks.add_task("stale thing", due_at=past)
    assert any(x["id"] == t["id"] for x in tasks.overdue_tasks(hours=24))
    tasks.set_status(t["id"], "cancelled")


def test_standing_orders_disk_alert(monkeypatch):
    monkeypatch.setattr(standing_orders, "get_health_snapshot",
                        lambda: {"disk_free_percent": 4.0, "cpu_percent": 10.0})
    findings, _ = standing_orders.evaluate()
    disk = [f for f in findings if "Disk" in f.condition]
    assert disk and disk[0].escalate


def test_standing_orders_cpu_escalates_on_second_cycle(monkeypatch):
    monkeypatch.setattr(standing_orders, "get_health_snapshot",
                        lambda: {"disk_free_percent": 50.0, "cpu_percent": 99.0})
    findings1, state1 = standing_orders.evaluate()
    cpu1 = [f for f in findings1 if "CPU" in f.condition][0]
    assert not cpu1.escalate
    findings2, _ = standing_orders.evaluate(state1)
    cpu2 = [f for f in findings2 if "CPU" in f.condition][0]
    assert cpu2.escalate


def test_watcher_coded_fallback_no_llm():
    decision, _ = watcher.gather_and_decide()
    assert decision["decided_by"] == "coded-fallback"
    assert decision["actions"], "must always log at least 'nothing to do'"


def test_memory_keyword_fallback_roundtrip():
    store = MemoryStore()
    store.remember("Hirthik prefers dark mode dashboards")
    hits = store.recall("dark mode preference")
    assert any("dark mode" in h for h in hits)
