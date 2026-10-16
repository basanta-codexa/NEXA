import io
import zipfile
import xml.etree.ElementTree as ET
from fastapi import UploadFile, HTTPException


def extract_text_from_file(filename: str, file_bytes: bytes) -> str:
    """
    Extracts plain text from various file formats (.txt, .md, .csv, .pdf, .docx, .json).
    Zero external dependencies for docx/txt/md/csv; uses pypdf for pdf.
    """
    lower_name = filename.lower()

    # 1. Plain text, markdown, CSV, JSON
    if lower_name.endswith((".txt", ".md", ".csv", ".json", ".log")):
        try:
            return file_bytes.decode("utf-8")
        except UnicodeDecodeError:
            try:
                return file_bytes.decode("latin-1")
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Failed to decode text file: {e}")

    # 2. PDF files
    elif lower_name.endswith(".pdf"):
        try:
            import pypdf
            reader = pypdf.PdfReader(io.BytesIO(file_bytes))
            pages_text = []
            for page_num, page in enumerate(reader.pages):
                text = page.extract_text()
                if text:
                    pages_text.append(text.strip())
            extracted = "\n\n".join(pages_text).strip()
            if not extracted:
                raise HTTPException(status_code=400, detail="PDF file contains no readable text (it may be scanned images).")
            return extracted
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to read PDF file: {e}")

    # 3. DOCX files (Word documents)
    elif lower_name.endswith(".docx"):
        try:
            with zipfile.ZipFile(io.BytesIO(file_bytes)) as docx_zip:
                xml_content = docx_zip.read("word/document.xml")
                tree = ET.fromstring(xml_content)
                # Word XML uses namespace http://schemas.openxmlformats.org/wordprocessingml/2006/main
                namespaces = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
                paragraphs = []
                for p in tree.iterfind(".//w:p", namespaces):
                    texts = [node.text for node in p.iterfind(".//w:t", namespaces) if node.text]
                    if texts:
                        paragraphs.append("".join(texts))
                extracted = "\n\n".join(paragraphs).strip()
                if not extracted:
                    raise HTTPException(status_code=400, detail="Word document is empty.")
                return extracted
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to read Word document (.docx): {e}")

    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format '{filename}'. Allowed formats: .txt, .md, .pdf, .docx, .csv, .json"
        )
