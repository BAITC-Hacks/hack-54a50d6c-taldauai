"""Export protocol v1 to an offline DOCX document without office dependencies.

Backend adapters may call docx_bytes(). CLI: python -m ml.export result.json
--output protocol.docx. No document text is sent to an external service.
"""

import argparse
from io import BytesIO
import json
from pathlib import Path
import re
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile


def _text(value) -> str:
    return escape(re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", str(value)))


def _paragraph(text, *, bold=False) -> str:
    return '<w:p><w:r>' + ('<w:rPr><w:b/></w:rPr>' if bold else '') + '<w:t xml:space="preserve">' + _text(text) + '</w:t></w:r></w:p>'


def _timestamp(ms) -> str:
    seconds = max(0, int(ms or 0)) // 1000
    return f"{seconds // 3600:02d}:{seconds // 60 % 60:02d}:{seconds % 60:02d}"


def docx_bytes(protocol: dict, title: str = "Протокол совещания") -> bytes:
    if (not isinstance(protocol, dict) or protocol.get("schema_version") != "1.0"
            or protocol.get("status") != "completed"
            or any(not isinstance(protocol.get(k), list) for k in ("speakers", "segments", "tasks"))):
        raise ValueError("Export requires a completed protocol v1")
    paragraphs = [_paragraph(title, bold=True), _paragraph(protocol.get("meeting_started_at", ""))]
    if any(t.get("needs_review", True) for t in protocol["tasks"]) or protocol.get("warnings"):
        paragraphs.append(_paragraph("Черновик: требуется проверка секретарём.", bold=True))
    paragraphs.extend([_paragraph("Краткое саммари", bold=True), _paragraph(protocol.get("summary") or "Саммари отсутствует")])
    names = {s["id"]: s.get("display_name") or s["id"] for s in protocol["speakers"]}
    paragraphs.append(_paragraph("Участники", bold=True))
    paragraphs.extend(_paragraph(f"{speaker}: {name}") for speaker, name in names.items())
    paragraphs.append(_paragraph("Поручения", bold=True))
    if not protocol["tasks"]:
        paragraphs.append(_paragraph("Поручения не обнаружены."))
    for index, task in enumerate(protocol["tasks"], 1):
        paragraphs.extend([
            _paragraph(f"{index}. {task['description']}", bold=True),
            _paragraph(f"Ответственный: {task.get('assignee_name') or 'Не определён'}"),
            _paragraph(f"Срок: {task.get('due_date') or 'Требует уточнения'}; исходная формулировка: {task.get('due_text') or 'Не указана'}"),
            _paragraph("Источники: " + ", ".join(task.get("source_segment_ids", []))),
            _paragraph("Требует проверки" if task.get("needs_review", True) else "Проверка полей пройдена; подтвердите содержание по записи"),
        ])
    paragraphs.append(_paragraph("Транскрипт", bold=True))
    for segment in protocol["segments"]:
        speaker = names.get(segment.get("speaker_id"), "Говорящий не определён")
        paragraphs.append(_paragraph(f"{segment['id']} [{_timestamp(segment.get('start_ms'))}–{_timestamp(segment.get('end_ms'))}] {speaker}", bold=True))
        paragraphs.append(_paragraph(segment["text"]))
        if segment.get("suggested_text"):
            paragraphs.append(_paragraph("Неподтверждённая подсказка: " + segment["suggested_text"]))
    if protocol.get("warnings"):
        paragraphs.append(_paragraph("Предупреждения", bold=True))
        paragraphs.extend(_paragraph(w) for w in protocol["warnings"])
    document = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>'
                + ''.join(paragraphs) + '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>'
                '<w:pgMar w:top="1134" w:right="1134" w:bottom="1134" w:left="1134"/></w:sectPr></w:body></w:document>')
    stream = BytesIO()
    with ZipFile(stream, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>')
        archive.writestr("_rels/.rels", '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>')
        archive.writestr("word/document.xml", document)
    return stream.getvalue()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("protocol")
    parser.add_argument("--output", required=True)
    parser.add_argument("--title", default="Протокол совещания")
    args = parser.parse_args()
    if Path(args.output).suffix.lower() != ".docx":
        parser.error("--output must end in .docx")
    result = json.loads(Path(args.protocol).read_text(encoding="utf-8"))
    Path(args.output).write_bytes(docx_bytes(result, args.title))


if __name__ == "__main__":
    main()
