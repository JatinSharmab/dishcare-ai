import re
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5


def load_documents(
    directory: Path,
) -> list[dict]:

    documents = []

    for path in sorted(
        directory.glob("*.md")
    ):

        content = path.read_text(
            encoding="utf-8"
        )

        sections = re.split(
            r"(?m)(?=^##\s+)",
            content,
        )

        for index, section in enumerate(sections):

            section = section.strip()

            if not section:
                continue

            title = section.splitlines()[0]
            words = section.split()

            chunk_size = 160
            step = 130

            for chunk_index, start in enumerate(
                range(0, len(words), step)
            ):

                chunk = " ".join(
                    words[start:start + chunk_size]
                )

                if not chunk:
                    continue

                text = f"{title}\n{chunk}"

                point_id = str(
                    uuid5(
                        NAMESPACE_URL,
                        (
                            f"{path.name}:"
                            f"{index}:{chunk_index}"
                        ),
                    )
                )

                documents.append({
                    "id": point_id,
                    "source": path.name,
                    "title": title,
                    "text": text,
                })

                if start + chunk_size >= len(words):
                    break

    return documents