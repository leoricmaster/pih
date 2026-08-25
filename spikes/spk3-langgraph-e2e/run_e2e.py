"""SPK-3 端到端执行：对 samples.json 全量跑图，落 e2e_results.json。

每条 sleep 0.3s（控速，避免 429）。冒烟建议先跑 1 条验证 API 连通。
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[0]))  # spikes/ for _lib

SAMPLES = HERE.parents[0] / "spk2-extraction-probe" / "golden" / "samples.json"

# 仅冒烟时跑前 1 条；全量跑请传 --all 或不带参数默认全量
SMOKE = "--smoke" in sys.argv


def main() -> int:
    from graph import build_graph

    app = build_graph()
    samples = json.loads(SAMPLES.read_text(encoding="utf-8"))
    if SMOKE:
        samples = samples[:1]
        print("[smoke] 仅跑 1 条")
    rows = []
    for s in samples:
        t0 = time.monotonic()
        try:
            final = app.invoke({"id": s["id"], "text": s["text"]})
            rows.append({
                "id": s["id"],
                "kept": final.get("kept"),
                "pred": final.get("pred"),
                "retries": final.get("retries"),
                "error": final.get("error"),
                "node_timings_ms": final.get("node_timings_ms", {}),
                "elapsed_ms": int((time.monotonic() - t0) * 1000),
            })
            print(
                f"[ok] {s['id']} kept={final.get('kept')} "
                f"pred={'有' if final.get('pred') else '无'} "
                f"retries={final.get('retries')} {rows[-1]['elapsed_ms']}ms"
            )
        except Exception as exc:  # noqa: BLE001
            rows.append({
                "id": s["id"],
                "error": f"{type(exc).__name__}: {exc}",
                "elapsed_ms": int((time.monotonic() - t0) * 1000),
            })
            print(f"[fail] {s['id']}: {exc}")
        time.sleep(0.3)
    out = HERE / "e2e_results.json"
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    ok = sum(1 for r in rows if r.get("pred"))
    print(f"成功(有pred) {ok}/{len(rows)} -> {out}")
    return 0 if ok == len(rows) and not SMOKE else 0  # 冒烟也返回0便于观察


if __name__ == "__main__":
    sys.exit(main())
