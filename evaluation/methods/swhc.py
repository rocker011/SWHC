from __future__ import annotations

import argparse
import asyncio
import os

from hypergraphrag import QueryParam

from methods.common import run_query_method


def _parse_bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    raise ValueError(f"Unsupported boolean value for {name}: {value}")


def _build_query_param() -> QueryParam:
    return QueryParam(
        only_need_context=True,
        subgraph_selector="swhc",
        swhc_source_rerank=_parse_bool_env("HGRAG_SWHC_SOURCE_RERANK", False),
    )


async def run(data_source: str):
    return await run_query_method(
        data_source=data_source,
        method_name="SWHC",
        query_param_factory=_build_query_param,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data_source", default="hypertension")
    args = parser.parse_args()
    asyncio.run(run(args.data_source))


if __name__ == "__main__":
    main()
