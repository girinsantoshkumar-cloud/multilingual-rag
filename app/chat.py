from __future__ import annotations

import argparse

from .models import Generator
from .router import build_context, route_query

def run(query: str) -> dict:
    routed = route_query(query)
    answer = Generator().answer(query, build_context(routed["results"]), routed["matrix_language"], routed["cmi"])
    return {**routed, "answer": answer}

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", required=True)
    args = parser.parse_args()
    result = run(args.query)
    print(result["answer"])
    print(f"\nCMI={result['cmi']} matrix={result['matrix_language']} views={[v['name'] for v in result['views']]}")
