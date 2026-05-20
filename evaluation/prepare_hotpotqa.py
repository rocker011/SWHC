from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen


BASE_DIR = Path(__file__).resolve().parent
DATASET_SERVER = "https://datasets-server.huggingface.co/rows"
DEFAULT_HF_DATASET = "hotpotqa/hotpot_qa"
DEFAULT_CONFIG = "distractor"
DEFAULT_SPLIT = "validation"
DEFAULT_SAMPLE_SIZE = 512
DEFAULT_PAGE_SIZE = 100


def clean_text(value: object) -> str:
    text = str(value or "").strip()
    return html.unescape(text)


def fetch_page(
    *,
    hf_dataset: str,
    config: str,
    split: str,
    offset: int,
    length: int,
) -> dict:
    query = urlencode(
        {
            "dataset": hf_dataset,
            "config": config,
            "split": split,
            "offset": offset,
            "length": length,
        }
    )
    with urlopen(f"{DATASET_SERVER}?{query}", timeout=120) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_rows(
    *,
    hf_dataset: str,
    config: str,
    split: str,
    sample_size: int,
    start_offset: int,
    page_size: int,
) -> tuple[list[dict], int]:
    rows: list[dict] = []
    offset = start_offset
    total_rows = 0
    while len(rows) < sample_size:
        page = fetch_page(
            hf_dataset=hf_dataset,
            config=config,
            split=split,
            offset=offset,
            length=min(page_size, sample_size - len(rows)),
        )
        page_rows = page.get("rows", [])
        total_rows = int(page.get("num_rows_total") or total_rows or 0)
        if not page_rows:
            break
        rows.extend(item["row"] for item in page_rows)
        offset += len(page_rows)
    return rows, total_rows


def supporting_sentences(row: dict) -> list[str]:
    context = row.get("context") or {}
    titles = [clean_text(title) for title in context.get("title") or []]
    sentences_by_title = {
        title: [clean_text(sentence) for sentence in sentences]
        for title, sentences in zip(titles, context.get("sentences") or [])
    }

    supporting = row.get("supporting_facts") or {}
    support_titles = [clean_text(title) for title in supporting.get("title") or []]
    support_sent_ids = supporting.get("sent_id") or []

    gold_context: list[str] = []
    seen: set[str] = set()
    for title, sent_id in zip(support_titles, support_sent_ids):
        sentences = sentences_by_title.get(title) or []
        if isinstance(sent_id, int) and 0 <= sent_id < len(sentences):
            sentence = sentences[sent_id].strip()
            if sentence and sentence not in seen:
                gold_context.append(sentence)
                seen.add(sentence)
    return gold_context


def build_context_sections(row: dict) -> list[str]:
    raw_context = row.get("context") or {}
    titles = [clean_text(title) for title in raw_context.get("title") or []]
    all_sentences = raw_context.get("sentences") or []
    sections: list[str] = []
    for title, sentences in zip(titles, all_sentences):
        body = " ".join(clean_text(sentence) for sentence in sentences).strip()
        if not body:
            continue
        sections.append(f"{title}\n{body}" if title else body)
    return sections


def convert_rows(rows: list[dict], *, context_mode: str) -> tuple[list[str], list[dict]]:
    context_docs: list[str] = []
    seen_docs: set[str] = set()
    questions: list[dict] = []

    for row in rows:
        sections = build_context_sections(row)
        if context_mode == "bundle":
            document = "\n\n".join(sections).strip()
            if document:
                context_docs.append(document)
        elif context_mode == "title":
            for document in sections:
                if document not in seen_docs:
                    context_docs.append(document)
                    seen_docs.add(document)
        else:
            raise ValueError(f"Unsupported context mode: {context_mode}")

        gold_context = supporting_sentences(row)
        support_titles = [
            clean_text(title)
            for title in (row.get("supporting_facts") or {}).get("title", [])
        ]
        unique_support_titles = sorted({title for title in support_titles if title})

        questions.append(
            {
                "question": clean_text(row.get("question")),
                "golden_answers": [clean_text(row.get("answer"))],
                "context": gold_context,
                "nary": len(unique_support_titles),
                "nhop": len(unique_support_titles),
                "hotpotqa_id": clean_text(row.get("id")),
                "type": clean_text(row.get("type")),
                "level": clean_text(row.get("level")),
                "supporting_facts": row.get("supporting_facts") or {},
            }
        )

    return context_docs, questions


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data_source", default="hotpotqa")
    parser.add_argument("--hf_dataset", default=DEFAULT_HF_DATASET)
    parser.add_argument("--config", default=DEFAULT_CONFIG)
    parser.add_argument("--split", default=DEFAULT_SPLIT)
    parser.add_argument("--sample_size", type=int, default=DEFAULT_SAMPLE_SIZE)
    parser.add_argument("--start_offset", type=int, default=0)
    parser.add_argument("--page_size", type=int, default=DEFAULT_PAGE_SIZE)
    parser.add_argument(
        "--context_mode",
        choices=["bundle", "title"],
        default="bundle",
        help=(
            "bundle writes one distractor-context document per QA sample; "
            "title writes one de-duplicated document per Wikipedia title."
        ),
    )
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    if args.sample_size <= 0:
        raise ValueError("--sample_size must be positive")

    context_path = BASE_DIR / "contexts" / f"{args.data_source}_contexts.json"
    question_dir = BASE_DIR / "datasets" / args.data_source
    question_path = question_dir / "questions.json"
    meta_path = question_dir / "dataset_meta.json"

    existing_outputs = [path for path in (context_path, question_path, meta_path) if path.exists()]
    if existing_outputs and not args.force:
        joined = ", ".join(path.as_posix() for path in existing_outputs)
        raise FileExistsError(f"Refusing to overwrite existing files without --force: {joined}")

    rows, total_rows = fetch_rows(
        hf_dataset=args.hf_dataset,
        config=args.config,
        split=args.split,
        sample_size=args.sample_size,
        start_offset=args.start_offset,
        page_size=args.page_size,
    )
    if len(rows) != args.sample_size:
        raise RuntimeError(f"Expected {args.sample_size} rows, fetched {len(rows)}")

    context_docs, questions = convert_rows(rows, context_mode=args.context_mode)

    context_path.parent.mkdir(parents=True, exist_ok=True)
    question_dir.mkdir(parents=True, exist_ok=True)
    context_path.write_text(
        json.dumps(context_docs, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    question_path.write_text(
        json.dumps(questions, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    meta_path.write_text(
        json.dumps(
            {
                "source": "Hugging Face Dataset Viewer",
                "hf_dataset": args.hf_dataset,
                "config": args.config,
                "split": args.split,
                "start_offset": args.start_offset,
                "sample_size": args.sample_size,
                "context_mode": args.context_mode,
                "total_rows_reported": total_rows,
                "context_documents": len(context_docs),
                "question_file": question_path.as_posix(),
                "context_file": context_path.as_posix(),
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "event": "hotpotqa_prepared",
                "data_source": args.data_source,
                "questions": len(questions),
                "context_documents": len(context_docs),
                "context_mode": args.context_mode,
                "total_rows_reported": total_rows,
                "question_path": question_path.as_posix(),
                "context_path": context_path.as_posix(),
                "meta_path": meta_path.as_posix(),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
