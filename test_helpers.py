import os
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn

OUTPUT_DOCX = r"D:\VTP\Do_an_tot_nghiep_PhuYen_BG_Flood_SAR.docx"

def set_cell_border(cell, **kwargs):
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    tcBorders = parse_xml(r'''
        <w:tcBorders xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
            <w:top w:val="{top}" w:sz="4" w:space="0" w:color="CCCCCC"/>
            <w:left w:val="{left}" w:sz="4" w:space="0" w:color="CCCCCC"/>
            <w:bottom w:val="{bottom}" w:sz="4" w:space="0" w:color="CCCCCC"/>
            <w:right w:val="{right}" w:sz="4" w:space="0" w:color="CCCCCC"/>
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

print("Helper functions ready.")
