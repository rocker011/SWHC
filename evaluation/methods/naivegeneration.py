from __future__ import annotations

import argparse

from methods.common import load_question_data, save_knowledge_results


def run(data_source: str):
    data, _ = load_question_data(data_source)
    for item in data:
        item["knowledge"] = ""
    return save_knowledge_results("NaiveGeneration", data_source, data)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data_source", default="hypertension")
    args = parser.parse_args()
    save_path = run(args.data_source)
    print(f"Results saved to {save_path.as_posix()}")


if __name__ == "__main__":
    main()
