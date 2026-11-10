"""
Runs the whole pipeline in order: load -> monthly metrics -> narrative -> page.

    python run_pipeline.py            full refresh (needs network + EVDS_API_KEY)
    python run_pipeline.py --offline  skip the load step, rebuild from the database
"""
import subprocess
import sys

STEPS = [("Load sources", "etl/load.py"), ("Monthly metrics", "etl/metrics.py"),
         ("What changed narrative", "etl/narrative.py"), ("Build page", "etl/build_page.py")]


def main():
    offline = "--offline" in sys.argv
    for label, script in STEPS:
        if offline and script == "etl/load.py":
            continue
        print(f"\n=== {label} ({script}) ===")
        if subprocess.run([sys.executable, script]).returncode != 0:
            sys.exit(f"FAILED: {label}")
    print("\nPipeline completed.")


if __name__ == "__main__":
    main()
