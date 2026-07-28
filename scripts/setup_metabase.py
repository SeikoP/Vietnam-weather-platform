"""Provision the local warehouse reader and initialize Metabase."""

import os
import sys
from collections.abc import Mapping

from src.metabase.bootstrap import MetabaseSettings, bootstrap_metabase


def main(environ: Mapping[str, str] | None = None) -> int:
    environment = os.environ if environ is None else environ
    try:
        settings = MetabaseSettings.from_environ(environment)
        bootstrap_metabase(settings)
        print("Metabase setup completed.")
        return 0
    except Exception as exc:
        print(f"Metabase setup failed ({type(exc).__name__}).", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
