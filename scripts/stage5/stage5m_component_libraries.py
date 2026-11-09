#!/usr/bin/env python3
"""
Stage 5m -- Component Library Detection
=========================================
For every JS/TS repo in the corpus, fetch package.json (and check for
components.json) via GraphQL to identify which UI component library is used.

Libraries detected:
  shadcn     -- 'shadcn'/'shadcn-ui' package OR components.json present
                OR class-variance-authority + tailwindcss + @radix-ui combo
  mui        -- '@mui/material' or '@material-ui/core'
  chakra     -- '@chakra-ui/react'
  antd       -- 'antd'
  mantine    -- '@mantine/core'
  radix      -- '@radix-ui/react-*' standalone (without shadcn indicators)
  headlessui -- '@headlessui/react' or '@headlessui/vue'
  none       -- none of the above found

A repo may have multiple libraries. `primary_library` picks the first match
in priority order: shadcn > mui > chakra > antd > mantine > radix > headlessui.

Input
-----
  data/stage3/corpus_detected_full.csv

Output
------
  data/stage5/component_libraries.csv
    Columns: full_name, adoption_label, primary_language,
             has_shadcn, has_mui, has_chakra, has_antd, has_mantine,
             has_radix, has_headlessui, primary_library, api_status

Usage
-----
  export GITHUB_TOKEN=ghp_...
  python3 scripts/stage5/stage5m_component_libraries.py [--limit N] [--resume]
"""

import os, sys, time, json, argparse, requests
import pandas as pd
from pathlib import Path

ROOT    = Path(__file__).resolve().parents[2]
CORPUS  = ROOT / "data" / "stage3" / "corpus_detected_full.csv"
OUT_DIR = ROOT / "data" / "stage5"
OUT_CSV = OUT_DIR / "component_libraries.csv"
OUT_DIR.mkdir(parents=True, exist_ok=True)

GRAPHQL_URL = "https://api.github.com/graphql"
BATCH_SIZE  = 5      # smaller batch — package.json blobs can be large
SLEEP_BATCH = 0.80

PRIORITY_ORDER = ["shadcn", "mui", "chakra", "antd", "mantine", "radix", "headlessui"]


# ── GitHub helpers ─────────────────────────────────────────────────────────────

def get_headers() -> dict:
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        sys.exit("ERROR: GITHUB_TOKEN not set.")
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def gql_post(query: str, headers: dict) -> dict:
    wait = 15
    for attempt in range(6):
        try:
            resp = requests.post(GRAPHQL_URL,
                                 json={"query": query},
                                 headers=headers,
                                 timeout=60)
        except (requests.exceptions.ReadTimeout,
                requests.exceptions.ConnectionError) as exc:
            if attempt < 5:
                print(f"\n  Network error ({exc.__class__.__name__}), "
                      f"retry {attempt+1}/5 in {wait}s …", flush=True)
                time.sleep(wait)
                wait = min(wait * 2, 120)
                continue
            raise

        if resp.status_code == 200:
            return resp.json()

        if resp.status_code in (403, 429):
            reset  = int(resp.headers.get("X-RateLimit-Reset", time.time() + 60))
            wait_s = max(reset - int(time.time()), 10)
            print(f"\n  Rate limited ({resp.status_code}) — sleeping {wait_s}s …",
                  flush=True)
            time.sleep(wait_s + 2)
            continue

        if resp.status_code in (500, 502, 503, 504):
            print(f"\n  Server error {resp.status_code} — "
                  f"retry {attempt+1}/5 in {wait}s …", flush=True)
            time.sleep(wait)
            wait = min(wait * 2, 120)
            continue

        print(f"\n  Unexpected HTTP {resp.status_code}", flush=True)
        return {}

    print("\n  Giving up after 5 retries — returning empty result.", flush=True)
    return {}


# ── GraphQL query builder ──────────────────────────────────────────────────────

def build_query(batch: list[tuple[str, str]]) -> str:
    """Fetch package.json text and components.json existence for each repo."""
    parts = []
    for i, (owner, repo) in enumerate(batch):
        parts.append(f"""
  r{i}: repository(owner: "{owner}", name: "{repo}") {{
    pkg: object(expression: "HEAD:package.json") {{
      ... on Blob {{ text }}
    }}
    cfg: object(expression: "HEAD:components.json") {{
      ... on Blob {{ text }}
    }}
  }}""")
    return "query {" + "".join(parts) + "\n}"


# ── Library detection ──────────────────────────────────────────────────────────

def detect_libraries(pkg_text: str | None, has_components_json: bool) -> dict:
    """Parse package.json text and return a dict of boolean library flags."""
    flags = {k: False for k in PRIORITY_ORDER}

    if has_components_json:
        flags["shadcn"] = True

    if not pkg_text:
        return flags

    try:
        pkg = json.loads(pkg_text)
    except (json.JSONDecodeError, ValueError):
        return flags

    # Merge all dep fields
    all_deps: set[str] = set()
    for field in ("dependencies", "devDependencies", "peerDependencies"):
        all_deps.update(pkg.get(field, {}).keys())

    # Also check scripts for shadcn CLI usage
    scripts_str = json.dumps(pkg.get("scripts", {}))

    # shadcn/ui
    if (not flags["shadcn"] and
            ("shadcn-ui" in all_deps or "shadcn" in all_deps
             or "shadcn" in scripts_str)):
        flags["shadcn"] = True

    # Secondary shadcn signal: characteristic combo
    # (class-variance-authority + tailwindcss + any @radix-ui package)
    if not flags["shadcn"]:
        has_cva    = "class-variance-authority" in all_deps
        has_tw     = "tailwindcss" in all_deps
        has_radix  = any(d.startswith("@radix-ui/") for d in all_deps)
        if has_cva and has_tw and has_radix:
            flags["shadcn"] = True

    # MUI
    if "@mui/material" in all_deps or "@material-ui/core" in all_deps:
        flags["mui"] = True

    # Chakra UI
    if "@chakra-ui/react" in all_deps:
        flags["chakra"] = True

    # Ant Design
    if "antd" in all_deps:
        flags["antd"] = True

    # Mantine
    if "@mantine/core" in all_deps:
        flags["mantine"] = True

    # Radix standalone (not already claimed by shadcn)
    if not flags["shadcn"] and any(d.startswith("@radix-ui/") for d in all_deps):
        flags["radix"] = True

    # Headless UI
    if "@headlessui/react" in all_deps or "@headlessui/vue" in all_deps:
        flags["headlessui"] = True

    return flags


def primary_library(flags: dict) -> str:
    for lib in PRIORITY_ORDER:
        if flags.get(lib):
            return lib
    return "none"


# ── Response parser ────────────────────────────────────────────────────────────

def parse_batch(response: dict, batch: list[tuple[str, str]]) -> list[dict]:
    data = response.get("data") or {}

    results = []
    for i, (owner, repo) in enumerate(batch):
        full_name = f"{owner}/{repo}"
        alias     = f"r{i}"
        repo_data = data.get(alias)

        if repo_data is None:
            results.append({"full_name": full_name, "api_status": "error",
                            **{f"has_{k}": False for k in PRIORITY_ORDER},
                            "primary_library": "none"})
            continue

        pkg_obj = repo_data.get("pkg") or {}
        cfg_obj = repo_data.get("cfg") or {}

        pkg_text          = pkg_obj.get("text") if pkg_obj else None
        has_components_json = bool(cfg_obj)

        if pkg_text is None and not has_components_json:
            results.append({"full_name": full_name, "api_status": "no_package_json",
                            **{f"has_{k}": False for k in PRIORITY_ORDER},
                            "primary_library": "none"})
            continue

        flags = detect_libraries(pkg_text, has_components_json)
        results.append({
            "full_name":      full_name,
            "api_status":     "ok",
            **{f"has_{k}": flags[k] for k in PRIORITY_ORDER},
            "primary_library": primary_library(flags),
        })

    return results


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit",  type=int, default=0, help="Process only first N repos (0 = all)")
    ap.add_argument("--resume", action="store_true",  help="Skip repos already in output file")
    args = ap.parse_args()

    headers = get_headers()

    # Load corpus — JS/TS repos only
    corpus = pd.read_csv(CORPUS)
    js_ts  = corpus[corpus["primary_language"].isin(["JavaScript", "TypeScript"])][
        ["full_name", "adoption_label", "primary_language"]].copy()

    if args.limit:
        js_ts = js_ts.head(args.limit)

    # Resume
    done: set[str] = set()
    if args.resume and OUT_CSV.exists():
        done = set(pd.read_csv(OUT_CSV)["full_name"])
        print(f"Resume: {len(done):,} repos already done.")

    todo = js_ts[~js_ts["full_name"].isin(done)].copy()
    print(f"JS/TS repos to process: {len(todo):,}  "
          f"(agentic={(todo['adoption_label']=='agentic').sum():,}, "
          f"none={(todo['adoption_label']=='none').sum():,})")

    if todo.empty:
        print("Nothing to do.")
        return

    lbl_lookup  = js_ts.set_index("full_name")["adoption_label"].to_dict()
    lang_lookup = js_ts.set_index("full_name")["primary_language"].to_dict()

    pairs   = [(r.split("/")[0], r.split("/")[1]) for r in todo["full_name"]]
    batches = [pairs[i:i+BATCH_SIZE] for i in range(0, len(pairs), BATCH_SIZE)]
    total   = len(batches)
    written = 0

    write_header = not (args.resume and OUT_CSV.exists())

    print(f"Running {total:,} batches (batch size={BATCH_SIZE}) …\n")

    for b_idx, batch in enumerate(batches):
        query    = build_query(batch)
        response = gql_post(query, headers)
        rows     = parse_batch(response, batch)

        records = []
        for row in rows:
            fn = row["full_name"]
            records.append({
                "full_name":      fn,
                "adoption_label": lbl_lookup.get(fn, "unknown"),
                "primary_language": lang_lookup.get(fn, "unknown"),
                **{k: v for k, v in row.items()
                   if k not in ("full_name",)},
            })

        df_out = pd.DataFrame(records)
        df_out.to_csv(OUT_CSV, mode="a", index=False, header=write_header)
        write_header = False
        written += len(records)

        if (b_idx + 1) % 100 == 0 or (b_idx + 1) == total:
            pct = (b_idx + 1) / total * 100
            print(f"  [{b_idx+1:,}/{total:,}  {pct:.1f}%]  written={written:,}",
                  flush=True)

        time.sleep(SLEEP_BATCH)

    print(f"\nDone. {written:,} rows written to {OUT_CSV}")

    # Quick summary
    result = pd.read_csv(OUT_CSV)
    ok     = result[result["api_status"] == "ok"]
    print(f"\n--- Primary library distribution (n={len(ok):,} repos with package.json) ---")
    print(ok["primary_library"].value_counts().to_string())

    print("\n--- By adoption label ---")
    for label in ["agentic", "none"]:
        sub = ok[ok["adoption_label"] == label]
        if sub.empty:
            continue
        print(f"\n{label} (n={len(sub):,}):")
        counts = sub["primary_library"].value_counts()
        for lib, n in counts.items():
            print(f"  {lib:<15} {n:>6,}  ({n/len(sub)*100:.1f}%)")


if __name__ == "__main__":
    main()
