"""SP-02 统计脚本：把"我发了什么"和"我收到了什么"算清楚。

用法：
  python stats.py --sent evidence/sent_baseline.jsonl --received evidence/raw_baseline.jsonl
  python stats.py --sent ... --received ... --json-out evidence/stats_baseline.json

输出指标：
  sent_count / received_count / missing / unexpected
  duplicate_by_observation_id   （同一 observation_id 收到 >1 次）
  duplicate_by_d1_key           （D1 定义：device_id+boot_id+sensor_type+seq 重复）
  order_inversions              （同一 boot_id 内，到达顺序中 seq 出现下降的次数）
  latency_ms                    （收到时刻 − 发送时刻，仅对匹配到的消息）
  boot_segments                 （每个 boot_id 收到多少条，用来看"重启后 seq 归零"）

⚠️ 统计口径写在 REPORT.md 里；不要只凭终端"看起来正常"写 PASS。
"""
from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter, defaultdict
from datetime import datetime


def load_jsonl(path: str):
    rows = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def parse_dt(s: str) -> datetime:
    return datetime.fromisoformat(s)


def main() -> int:
    p = argparse.ArgumentParser(description="SP-02 统计")
    p.add_argument("--sent", required=True)
    p.add_argument("--received", required=True)
    p.add_argument("--json-out", default=None)
    args = p.parse_args()

    sent = load_jsonl(args.sent)
    recv = load_jsonl(args.received)

    sent_by_id = {}
    for r in sent:
        # 重复注入时会写两条相同 observation_id，保留第一条
        sent_by_id.setdefault(r["observation_id"], r)

    parsed = []
    non_observation = 0
    parse_errors = 0
    for r in recv:
        obs = r.get("_obs")
        if not isinstance(obs, dict):
            parse_errors += 1
            continue
        if "observation_id" not in obs or "sensor_type" not in obs:
            # status 心跳等非观测消息：不计入观测统计
            non_observation += 1
            continue
        parsed.append((r, obs))

    recv_ids = [o["observation_id"] for _, o in parsed]
    recv_id_counts = Counter(recv_ids)

    # ---- 缺失 / 多余 ----
    missing_ids = [i for i in sent_by_id if i not in recv_id_counts]
    unexpected_ids = [i for i in recv_id_counts if i not in sent_by_id]

    # ---- D1 重复 ----
    d1_counter = Counter(
        (o["device_id"], o["boot_id"], o["sensor_type"], o["seq"]) for _, o in parsed
    )
    d1_dups = {k: v for k, v in d1_counter.items() if v > 1}

    # ---- 乱序：按到达顺序，同 boot_id 内 seq 下降次数 ----
    by_boot_arrival = defaultdict(list)
    for r, o in parsed:
        by_boot_arrival[o["boot_id"]].append((r["_recv_at"], o["seq"]))
    inversions = 0
    inversion_examples = []
    for boot, items in by_boot_arrival.items():
        items.sort(key=lambda x: x[0])  # 按收到时间排序
        prev = None
        for recv_at, seq in items:
            if prev is not None and seq < prev:
                inversions += 1
                if len(inversion_examples) < 5:
                    inversion_examples.append({"boot_id": boot, "from_seq": prev, "to_seq": seq})
            prev = seq

    # ---- 延迟 ----
    lat = []
    for r, o in parsed:
        s = sent_by_id.get(o["observation_id"])
        if not s or not s.get("ts_published"):
            continue
        try:
            dt = (parse_dt(r["_recv_at"]) - parse_dt(s["ts_published"])).total_seconds() * 1000
        except Exception:  # noqa: BLE001
            continue
        lat.append(dt)

    # ---- boot 分段 ----
    boot_segments = []
    for boot, items in by_boot_arrival.items():
        seqs = [s for _, s in items]
        boot_segments.append(
            {
                "boot_id": boot,
                "received": len(items),
                "seq_min": min(seqs),
                "seq_max": max(seqs),
                "first_seq": seqs[0],
                "last_seq": seqs[-1],
            }
        )

    buffered = sum(1 for r in sent if r.get("buffered"))
    dup_injections = sum(1 for r in sent if r.get("duplicate_injection"))

    summary = {
        "files": {"sent": args.sent, "received": args.received},
        "sent_count": len(sent),
        "sent_unique_observations": len(sent_by_id),
        "sent_buffered": buffered,
        "duplicate_injections_declared": dup_injections,
        "received_count": len(recv),
        "received_parsed": len(parsed),
        "non_observation_messages": non_observation,
        "parse_errors": parse_errors,
        "missing": len(missing_ids),
        "missing_ids_sample": missing_ids[:5],
        "unexpected": len(unexpected_ids),
        "duplicate_by_observation_id": sum(1 for v in recv_id_counts.values() if v > 1),
        "duplicate_excess_messages": sum(v - 1 for v in recv_id_counts.values() if v > 1),
        "duplicate_by_d1_key": len(d1_dups),
        "order_inversions": inversions,
        "order_inversion_examples": inversion_examples,
        "latency_ms": {
            "n": len(lat),
            "min": round(min(lat), 1) if lat else None,
            "median": round(statistics.median(lat), 1) if lat else None,
            "max": round(max(lat), 1) if lat else None,
        },
        "boot_segments": boot_segments,
        "sensor_type_counts": dict(Counter(o["sensor_type"] for _, o in parsed)),
    }

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(summary, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
        print(f"\n[stats] 已写入 {args.json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
