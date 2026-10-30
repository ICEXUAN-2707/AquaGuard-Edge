"""SP-02 统计脚本的端到端测试（用子进程跑真实 CLI）。

跑：python -m pytest spikes/SP-02/tests -q
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(os.path.dirname(HERE), "src")
STATS = os.path.join(SRC, "stats.py")


def write_jsonl(path, rows):
    with open(path, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")


def obs(oid, seq, boot="b1", stype="flow", device="A001"):
    return {
        "device_id": device,
        "boot_id": boot,
        "sensor_type": stype,
        "seq": seq,
        "observation_id": oid,
    }


def run_stats(tmp_path, sent, recv):
    sp = tmp_path / "sent.jsonl"
    rp = tmp_path / "recv.jsonl"
    out = tmp_path / "stats.json"
    write_jsonl(sp, sent)
    write_jsonl(rp, recv)
    cp = subprocess.run(
        [sys.executable, STATS, "--sent", str(sp), "--received", str(rp), "--json-out", str(out)],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert cp.returncode == 0, cp.stderr
    return json.loads(out.read_text(encoding="utf-8"))


def recv_row(o, at="2026-10-30T12:00:00.100+08:00"):
    return {"_recv_at": at, "_topic": "t", "_payload_raw": "{}", "_obs": o, "_parse_error": None}


def sent_row(o, at="2026-10-30T12:00:00.000+08:00", buffered=False):
    return {
        "observation_id": o["observation_id"],
        "device_id": o["device_id"],
        "boot_id": o["boot_id"],
        "seq": o["seq"],
        "sensor_type": o["sensor_type"],
        "ts_attempt": at,
        "ts_published": at,
        "buffered": buffered,
        "payload": o,
    }


def test_detects_missing_and_duplicates(tmp_path):
    o1, o2, o3 = obs("id1", 1), obs("id2", 2), obs("id3", 3)
    sent = [sent_row(o1), sent_row(o2), sent_row(o3)]
    recv = [recv_row(o1), recv_row(o2), recv_row(o2)]  # 缺 id3，重复 id2
    s = run_stats(tmp_path, sent, recv)

    assert s["sent_count"] == 3
    assert s["received_count"] == 3
    assert s["missing"] == 1
    assert s["duplicate_by_observation_id"] == 1
    assert s["duplicate_excess_messages"] == 1
    assert s["duplicate_by_d1_key"] == 1


def test_detects_order_inversion(tmp_path):
    o1, o2, o3 = obs("id1", 1), obs("id2", 2), obs("id3", 3)
    sent = [sent_row(o1), sent_row(o2), sent_row(o3)]
    # 到达顺序 1 -> 3 -> 2 ：seq 从 3 降到 2，记一次乱序
    recv = [
        recv_row(o1, "2026-10-30T12:00:00.100+08:00"),
        recv_row(o3, "2026-10-30T12:00:00.200+08:00"),
        recv_row(o2, "2026-10-30T12:00:00.300+08:00"),
    ]
    s = run_stats(tmp_path, sent, recv)
    assert s["order_inversions"] == 1
    assert s["missing"] == 0


def test_boot_segments_distinguish_restart(tmp_path):
    a1, a2 = obs("a1", 1, boot="b1"), obs("a2", 2, boot="b1")
    b1_ = obs("b1x", 1, boot="b2")  # 重启后 seq 归零
    sent = [sent_row(a1), sent_row(a2), sent_row(b1_)]
    recv = [recv_row(a1), recv_row(a2), recv_row(b1_)]
    s = run_stats(tmp_path, sent, recv)
    boots = {seg["boot_id"]: seg for seg in s["boot_segments"]}
    assert set(boots) == {"b1", "b2"}
    assert boots["b2"]["first_seq"] == 1
    # 重启不应被误判成"同一轮的重复"
    assert s["duplicate_by_d1_key"] == 0


def test_latency_computed(tmp_path):
    o1 = obs("id1", 1)
    sent = [sent_row(o1, "2026-10-30T12:00:00.000+08:00")]
    recv = [recv_row(o1, "2026-10-30T12:00:00.150+08:00")]
    s = run_stats(tmp_path, sent, recv)
    assert s["latency_ms"]["n"] == 1
    assert s["latency_ms"]["min"] == 150.0
