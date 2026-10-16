import re


def split_text(text: str, chunk_size: int = 500, chunk_overlap: int = 50) -> list[str]:
    """
    Splits input text into overlapping chunks, prioritizing paragraph and
    sentence boundaries.
    """
    clean_text = text.strip()
    if not clean_text:
        return []

    if len(clean_text) <= chunk_size:
        return [clean_text]

    # Split into paragraphs/sentences first
    paragraphs = re.split(r'\n+', clean_text)
    chunks: list[str] = []
    current_chunk = ""

    for paragraph in paragraphs:
        paragraph = paragraph.strip()
        if not paragraph:
            continue

        # If adding this paragraph fits in chunk_size, append it
        if len(current_chunk) + len(paragraph) + 1 <= chunk_size:
            current_chunk = (current_chunk + "\n" + paragraph).strip()
        else:
            if current_chunk:
                chunks.append(current_chunk)
                # Keep overlap from previous chunk
                overlap_text = current_chunk[-chunk_overlap:] if len(current_chunk) > chunk_overlap else current_chunk
                current_chunk = overlap_text + "\n" + paragraph
            else:
                # If single paragraph is larger than chunk_size, split by sentences or fixed window
                words = paragraph.split(" ")
                sub_chunk = ""
                for word in words:
                    if len(sub_chunk) + len(word) + 1 <= chunk_size:
                        sub_chunk = (sub_chunk + " " + word).strip()
                    else:
                        if sub_chunk:
                            chunks.append(sub_chunk)
                            overlap = sub_chunk[-chunk_overlap:] if len(sub_chunk) > chunk_overlap else ""
                            sub_chunk = (overlap + " " + word).strip()
                        else:
                            chunks.append(word)
                if sub_chunk:
                    current_chunk = sub_chunk

    if current_chunk and (not chunks or chunks[-1] != current_chunk):
        chunks.append(current_chunk)

    return chunks
