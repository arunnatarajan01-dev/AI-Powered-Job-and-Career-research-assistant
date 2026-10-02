"""Build a simple .xlsx workbook from tables. Uses only the Python standard library."""

import io
import zipfile
from xml.sax.saxutils import escape


def _column(index):
    name = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        name = chr(65 + remainder) + name
    return name


def _text(value):
    if value is None:
        raw = ""
    elif isinstance(value, (list, tuple)):
        raw = ", ".join(str(item) for item in value)
    else:
        raw = str(value)
    cleaned = "".join(char for char in raw if char >= " " or char == "\t")
    return escape(cleaned[:32000])


def _sheet_xml(headers, rows):
    table = [list(headers)]
    table.extend(list(row) for row in rows)
    lines = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">',
        "<sheetData>",
    ]
    for row_index, row in enumerate(table, start=1):
        cells = []
        for col_index, value in enumerate(row, start=1):
            ref = f"{_column(col_index)}{row_index}"
            cells.append(f'<c r="{ref}" t="inlineStr"><is><t>{_text(value)}</t></is></c>')
        lines.append(f'<row r="{row_index}">{"".join(cells)}</row>')
    lines.append("</sheetData></worksheet>")
    return "".join(lines)


def build_xlsx(sheets):
    """Return xlsx bytes. Each sheet is (name, headers, rows)."""
    used = []
    for name, _headers, _rows in sheets:
        clean = "".join(char for char in name if char not in '[]:*?/\\')[:31] or "Sheet"
        if clean in used:
            clean = (clean[:28] + str(len(used)))[:31]
        used.append(clean)

    content_types = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">',
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>',
        '<Default Extension="xml" ContentType="application/xml"/>',
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>',
    ]
    workbook = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">',
        "<sheets>",
    ]
    rels = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">',
    ]
    for index, name in enumerate(used, start=1):
        content_types.append(
            f'<Override PartName="/xl/worksheets/sheet{index}.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        )
        workbook.append(f'<sheet name="{escape(name)}" sheetId="{index}" r:id="rId{index}"/>')
        rels.append(
            f'<Relationship Id="rId{index}" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
            f'Target="worksheets/sheet{index}.xml"/>'
        )
    content_types.append("</Types>")
    workbook.append("</sheets></workbook>")
    rels.append("</Relationships>")

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", "".join(content_types))
        archive.writestr(
            "_rels/.rels",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            "</Relationships>",
        )
        archive.writestr("xl/workbook.xml", "".join(workbook))
        archive.writestr("xl/_rels/workbook.xml.rels", "".join(rels))
        for index, (_name, headers, rows) in enumerate(sheets, start=1):
            archive.writestr(f"xl/worksheets/sheet{index}.xml", _sheet_xml(headers, rows))
    buffer.seek(0)
    return buffer
