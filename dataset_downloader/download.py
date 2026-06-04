"""
Download external datasets into data/raw/.

  python datasets/download.py
  python datasets/download.py --dataset pag
"""
import argparse
import json
import os
import subprocess
from pathlib import Path

import requests

RAW_DIR = Path("./data/raw")


def download_pag(out_dir: Path) -> None:
    print("Downloading PAG incidents...")
    try:
        from datasets import load_dataset

        ds = load_dataset("bigcode/the-stack-smol", data_dir="data/markdown", split="train[:500]")
        records = [
            {
                "incident_id": f"PAG-{i:04d}",
                "title": f"Incident {i}",
                "description": str(row.get("content", ""))[:500],
                "severity": "P3",
                "affected_system": "unknown",
                "source_dataset": "pag",
            }
            for i, row in enumerate(ds)
        ]
        out_path = out_dir / "pag_incidents.json"
        out_path.write_text(json.dumps(records, indent=2), encoding="utf-8")
        print(f"  Saved {len(records)} records to {out_path}")
    except Exception as e:
        print(f"  WARNING: PAG failed ({e}). Using placeholder.")
        _write_placeholder(out_dir / "pag_incidents.json", "pag", 10)


def download_hdfs_sample(out_dir: Path) -> None:
    print("Downloading HDFS log sample...")
    hdfs_dir = out_dir / "hdfs_logs"
    hdfs_dir.mkdir(exist_ok=True)
    url = "https://raw.githubusercontent.com/logpai/loghub/master/HDFS/HDFS_2k.log"
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        out_path = hdfs_dir / "HDFS_sample.log"
        out_path.write_text(resp.text, encoding="utf-8")
        print(f"  Saved {resp.text.count(chr(10))} lines to {out_path}")
    except Exception as e:
        print(f"  WARNING: HDFS failed ({e}). Using placeholder.")
        (hdfs_dir / "HDFS_sample.log").write_text(
            "\n".join(f"ERROR 2024-01-01 00:0{i}:00 hdfs: simulated {i}" for i in range(20))
        )


def download_kaggle_it(out_dir: Path) -> None:
    username = os.environ.get("KAGGLE_USERNAME")
    key = os.environ.get("KAGGLE_KEY")
    if not username or not key:
        print("  SKIP Kaggle (set KAGGLE_USERNAME / KAGGLE_KEY in .env)")
        _write_placeholder(out_dir / "it_incidents.json", "kaggle_it", 20)
        return
    print("Downloading IT-incidents from Kaggle...")
    try:
        subprocess.run(
            [
                "kaggle",
                "datasets",
                "download",
                "-d",
                "vipul4789/it-incident-dataset",
                "--unzip",
                "-p",
                str(out_dir),
            ],
            check=True,
        )
    except Exception as e:
        print(f"  WARNING: Kaggle failed ({e}).")
        _write_placeholder(out_dir / "it_incidents.json", "kaggle_it", 20)


def _write_placeholder(path: Path, source: str, n: int) -> None:
    records = [
        {
            "incident_id": f"{source.upper()}-{i:04d}",
            "title": f"Placeholder incident {i}",
            "description": f"Test record from {source}.",
            "severity": ["P1", "P2", "P3", "P4"][i % 4],
            "affected_system": ["database", "api", "network", "storage"][i % 4],
            "signals": [f"ERROR service-{i}: simulated error"],
            "source_dataset": source,
        }
        for i in range(n)
    ]
    path.write_text(json.dumps(records, indent=2), encoding="utf-8")
    print(f"  Placeholder ({n}) → {path}")


DATASETS = {
    "pag": download_pag,
    "hdfs": download_hdfs_sample,
    "kaggle": download_kaggle_it,
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Download datasets into data/raw/")
    parser.add_argument("--dataset", choices=[*DATASETS.keys(), "all"], default="all")
    args = parser.parse_args()

    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    targets = list(DATASETS) if args.dataset == "all" else [args.dataset]
    for name in targets:
        DATASETS[name](RAW_DIR)
    print("\nDone. Next: python main.py --mode seed")


if __name__ == "__main__":
    main()
