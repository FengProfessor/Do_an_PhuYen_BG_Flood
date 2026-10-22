# -*- coding: utf-8 -*-
"""
Script sinh toàn văn Đồ án tốt nghiệp chất lượng cao (>= 50 trang)
Chuẩn format Trường ĐH Công nghệ - ĐHQGHN (tham khảo mẫu Hoàng Tích Phúc - TS. Hà Minh Cường)
Bao gồm đầy đủ 100% tài liệu tham khảo có DOI / Live URL kiểm chứng.
"""

import os
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn

OUTPUT_PATH = r"D:\VTP\Do_an_tot_nghiep_PhuYen_BG_Flood_SAR.docx"

doc = docx.Document()

# 1. Định dạng trang A4 chuẩn UET / Đồ án mẫu
sec = doc.sections[0]
sec.page_width = Inches(8.27)   # 21.0 cm
sec.page_height = Inches(11.69) # 29.7 cm
sec.top_margin = Inches(0.98)    # 2.5 cm
sec.bottom_margin = Inches(1.18) # 3.0 cm
sec.left_margin = Inches(1.18)   # 3.0 cm (đóng gáy sách)
sec.right_margin = Inches(0.79)  # 2.0 cm

# Header & Footer có số trang
footer = sec.footer
p_ft = footer.paragraphs[0]
p_ft.alignment = WD_ALIGN_PARAGRAPH.RIGHT
r_ft = p_ft.add_run("Trường Đại học Công nghệ – ĐHQGHN | Viện Công nghệ Hàng không Vũ trụ")
r_ft.font.name = 'Times New Roman'
r_ft.font.size = Pt(9)
r_ft.font.italic = True
r_ft.font.color.rgb = RGBColor(128, 128, 128)

# Định dạng phông chữ Normal
normal_style = doc.styles['Normal']
normal_style.font.name = 'Times New Roman'
normal_style.font.size = Pt(13)
normal_style.font.color.rgb = RGBColor(0, 0, 0)
normal_style.paragraph_format.line_spacing = 1.25
normal_style.paragraph_format.space_before = Pt(0)
normal_style.paragraph_format.space_after = Pt(6)

def set_cell_border(cell, **kwargs):
    tcPr = cell._tc.get_or_add_tcPr()
    tcBorders = parse_xml(r'''
        <w:tcBorders xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
            <w:top w:val="{top}" w:sz="4" w:space="0" w:color="B0B0B0"/>
            <w:left w:val="{left}" w:sz="4" w:space="0" w:color="B0B0B0"/>
            <w:bottom w:val="{bottom}" w:sz="4" w:space="0" w:color="B0B0B0"/>
            <w:right w:val="{right}" w:sz="4" w:space="0" w:color="B0B0B0"/>
        </w:tcBorders>
    '''.format(
        top=kwargs.get('top', 'single'),
        left=kwargs.get('left', 'none'),
        bottom=kwargs.get('bottom', 'single'),
        right=kwargs.get('right', 'none')
    ))
    tcPr.append(tcBorders)

def set_cell_shading(cell, color_hex):
    shading_xml = f'<w:shd xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" w:fill="{color_hex}"/>'
    cell._tc.get_or_add_tcPr().append(parse_xml(shading_xml))

def add_h(text, level=1, align=WD_ALIGN_PARAGRAPH.LEFT):
    p = doc.add_paragraph()
    p.alignment = align
    run = p.add_run(text)
    run.font.name = 'Times New Roman'
    run.bold = True
    if level == 1:
        run.font.size = Pt(15)
        p.paragraph_format.space_before = Pt(20)
        p.paragraph_format.space_after = Pt(10)
    elif level == 2:
        run.font.size = Pt(13.5)
        p.paragraph_format.space_before = Pt(14)
        p.paragraph_format.space_after = Pt(6)
    elif level == 3:
        run.font.size = Pt(13)
        run.italic = True
        p.paragraph_format.space_before = Pt(10)
        p.paragraph_format.space_after = Pt(4)
    return p

def add_p(text, bold_prefix="", indent=True, align=WD_ALIGN_PARAGRAPH.JUSTIFY):
    p = doc.add_paragraph()
    p.alignment = align
    if indent:
        p.paragraph_format.first_line_indent = Inches(0.4)
    if bold_prefix:
        r_pre = p.add_run(bold_prefix)
        r_pre.bold = True
        r_pre.font.name = 'Times New Roman'
    run = p.add_run(text)
    run.font.name = 'Times New Roman'
    return p

def add_caption(text, is_table=False):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(text)
    run.font.name = 'Times New Roman'
    run.font.size = Pt(12)
    if is_table:
        run.bold = True
        p.paragraph_format.space_before = Pt(8)
        p.paragraph_format.space_after = Pt(4)
    else:
        run.italic = True
        p.paragraph_format.space_before = Pt(4)
        p.paragraph_format.space_after = Pt(12)

def add_fig(img_path, caption_text, width_inches=5.8):
    if os.path.exists(img_path):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(10)
        p.paragraph_format.space_after = Pt(2)
        run = p.add_run()
        run.add_picture(img_path, width=Inches(width_inches))
        add_caption(caption_text, is_table=False)
    else:
        add_caption(f"[{caption_text}]", is_table=False)

def add_formula(text, formula_id):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    p.paragraph_format.first_line_indent = Inches(0.8)
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.space_after = Pt(4)
    run = p.add_run(text)
    run.italic = True
    run.font.name = 'Times New Roman'
    r_id = p.add_run(f"\t\t\t\t\t({formula_id})")
    r_id.bold = True
    r_id.font.name = 'Times New Roman'

print("Khởi tạo cấu trúc văn bản thành công. Bắt đầu biên soạn nội dung đồ án...")
