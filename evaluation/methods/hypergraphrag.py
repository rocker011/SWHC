from __future__ import annotations

import argparse
import asyncio

from hypergraphrag import QueryParam

from methods.common import run_query_method


async def run(data_source: str):
    return await run_query_method(
        data_source=data_source,
        method_name="HyperGraphRAG",
        query_param_factory=lambda: QueryParam(only_need_context=True),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data_source", default="hypertension")
    args = parser.parse_args()
    asyncio.run(run(args.data_source))


if __name__ == "__main__":
    main()
