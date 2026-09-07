# parsing/nio_jsonl.py

import json
from pathlib import Path

from domain.model import NIO, Protocol, Source


def load_protocol_jsonl(path: str) -> Protocol:

    path_obj = Path(path)

    nios: list[NIO] = []

    with path_obj.open(
        "r",
        encoding="utf-8",
    ) as f:

        for line_number, line in enumerate(f, start=1):

            line = line.strip()

            if not line:
                continue

            data = json.loads(line)

            source_data = data.get("source")

            source = None

            if source_data is not None:
                source = Source(
                    file=source_data.get("file"),
                    table=source_data.get("table"),
                    word_row=source_data.get("word_row"),
                )

            req = data.get("Req")

            if req not in ("Yes", "No", None):
                raise ValueError(
                    f"Invalid Req value at line "
                    f"{line_number}: {req!r}"
                )

            nio = NIO(
                id=data["id"],
                specification=data["specification"],
                rationale=data.get("rationale"),
                req=req,
                source=source,
            )

            nios.append(nio)

    return Protocol(
        document_id=path_obj.stem,
        title=path_obj.stem,
        nios=nios,
    )