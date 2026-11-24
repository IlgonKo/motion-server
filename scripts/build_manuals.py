"""Build editable manuals from the reviewed Markdown sources (python-docx).

PDF export and visual rendering are a separate release check; this command does
not claim that a successfully written DOCX has passed layout validation.
"""
from pathlib import Path
import re
from docx import Document
from docx.shared import Mm, Pt, RGBColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

ROOT = Path(__file__).resolve().parents[1]
MANUALS = ('Motion_Server_User_Manual_KR', 'Motion_Server_Installation_Manual_Basic_Mode')


def font(style, size, name='Malgun Gothic'):
    style.font.name = name
    style.font.size = Pt(size)
    style.font.color.rgb = RGBColor(0, 0, 0)
    fonts = style.element.get_or_add_rPr().rFonts
    for attr in list(fonts.attrib):
        if 'theme' in attr.lower():
            del fonts.attrib[attr]
    for attr in ('ascii', 'hAnsi', 'cs'):
        fonts.set(qn('w:' + attr), name)
    fonts.set(qn('w:eastAsia'), 'Malgun Gothic')


def inline(paragraph, value):
    for i, part in enumerate(re.split(r'`([^`]+)`', value)):
        run = paragraph.add_run(part)
        if i % 2:
            run.font.name = 'Consolas'
            run.font.size = Pt(9)


def build(stem):
    source = ROOT / 'docs' / (stem + '.md')
    doc = Document()
    # python-docx's bundled template may contain decorative Title borders.
    for border in doc.styles.element.xpath('.//w:pBdr'):
        border.getparent().remove(border)
    section = doc.sections[0]
    section.page_width, section.page_height = Mm(210), Mm(297)
    section.top_margin = section.bottom_margin = Mm(20)
    section.left_margin = section.right_margin = Mm(21)
    section.footer_distance = Mm(10)
    font(doc.styles['Normal'], 10)
    normal = doc.styles['Normal'].paragraph_format
    normal.line_spacing = 1.25
    normal.space_after = Pt(7)
    normal.widow_control = True
    for name, size in [('Title', 23), ('Heading 1', 15), ('Heading 2', 12), ('Subtitle', 10)]:
        font(doc.styles[name], size)
        doc.styles[name].paragraph_format.keep_with_next = True
    doc.styles['Title'].paragraph_format.space_after = Pt(8)
    doc.styles['Subtitle'].font.italic = False
    doc.styles['Heading 1'].paragraph_format.space_before = Pt(14)
    doc.styles['Heading 1'].paragraph_format.space_after = Pt(7)
    code = doc.styles.add_style('Manual Code', 1)
    font(code, 8.5, 'Consolas')
    code.paragraph_format.line_spacing = 1.1
    code.paragraph_format.space_after = Pt(7)
    code.paragraph_format.keep_together = True
    code.paragraph_format.left_indent = Mm(3)
    footer = section.footer.paragraphs[0]
    footer.alignment = 2
    run = footer.add_run('Motion Server  |  ')
    run.font.size = Pt(8)
    field = OxmlElement('w:fldSimple')
    field.set(qn('w:instr'), 'PAGE')
    footer._p.append(field)
    doc.core_properties.author = 'Motion Server'
    doc.core_properties.subject = 'Basic mode 사용자 및 설치 안내'
    doc.core_properties.version = '2.0'
    lines = source.read_text(encoding='utf-8').splitlines()
    body, block = [], None

    def flush(keep_next=False):
        if body:
            p = doc.add_paragraph()
            p.paragraph_format.keep_with_next = keep_next
            inline(p, ' '.join(body))
            body.clear()

    for line in lines:
        if line.startswith('```'):
            flush(keep_next=block is None)
            if block is None:
                if doc.paragraphs:
                    doc.paragraphs[-1].paragraph_format.keep_with_next = True
                block = []
            else:
                p = doc.add_paragraph('\n'.join(block), 'Manual Code')
                shade = OxmlElement('w:shd')
                shade.set(qn('w:fill'), 'F2F4F6')
                p._p.get_or_add_pPr().append(shade)
                block = None
        elif block is not None:
            block.append(line)
        elif not line.strip():
            flush()
        elif line.startswith('# '):
            flush()
            title = line[2:]
            doc.add_paragraph(title, 'Title')
            doc.core_properties.title = title
        elif line.startswith('## '):
            flush()
            p = doc.add_paragraph(line[3:], 'Heading 1')
            if line[3:] == '외부 프로그램의 API 사용':
                p.paragraph_format.page_break_before = True
        elif line.startswith('개정 '):
            flush()
            doc.add_paragraph(line, 'Subtitle')
        elif re.match(r'^\d+\. ', line):
            flush()
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Mm(5)
            p.paragraph_format.first_line_indent = Mm(-5)
            inline(p, line)
        else:
            body.append(line)
    flush()
    if block is not None:
        raise ValueError(f'Unclosed code block: {source}')
    target = source.with_suffix('.docx')
    doc.save(target)
    print(target)


if __name__ == '__main__':
    for name in MANUALS:
        build(name)
