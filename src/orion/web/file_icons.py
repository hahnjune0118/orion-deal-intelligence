"""Locally served, unmodified Fluent UI file-type artwork (not app branding)."""
from dash import html


def file_icon(filename):
    extension = str(filename).rsplit('.', 1)[-1].lower()
    family = {'doc': 'word', 'docx': 'word', 'xls': 'excel', 'xlsx': 'excel',
              'ppt': 'powerpoint', 'pptx': 'powerpoint', 'pdf': 'pdf', 'csv': 'csv'}.get(extension, 'other')
    label = {'word': 'Microsoft Word', 'excel': 'Microsoft Excel', 'powerpoint': 'Microsoft PowerPoint',
             'pdf': 'PDF', 'csv': 'CSV', 'other': '문서'}[family]
    return html.Img(src='/assets/file-' + family + '.svg', alt=label + ' 파일',
                    width=24, height=24, className='file-type-icon', title=label)
