import os
import json
import logging
import xlsxwriter

from PySide6.QtCore import Qt, QModelIndex
from PySide6.QtWidgets import QApplication
from jal.constants import Setup
from jal.db.helpers import get_app_path
from jal.widgets.helpers import ts2d


#-----------------------------------------------------------------------------------------------------------------------
# Class to encapsulate all xlsxwriter-related activities - like formatting, formulas, etc
class XLSX:
    ROW_DATA = 0
    ROW_FORMAT = 1
    ROW_WIDTH = 2
    ROW_SPAN_H = 3
    ROW_SPAN_V = 4
    totals = "ИТОГО"

    RPT_METHOD = 0
    RPT_TITLE = 1
    RPT_COLUMNS = 2
    RPT_DATA_ROWS = 3

    COL_TITLE = 0
    COL_WIDTH = 1
    COL_FIELD = 2
    COL_DESCR = -1
    START_ROW = 9

    def __init__(self, xlsx_filename):
        self.filename = xlsx_filename
        self.workbook = xlsxwriter.Workbook(filename=xlsx_filename)
        self.formats = xslxFormat(self.workbook)

    def tr(self, text):
        return QApplication.translate("XLSX", text)

    def save(self):
        try:
            self.workbook.close()
        except:
            logging.error(self.tr("Can't save report into file ") + f"'{self.filename}'")

    def load_template(self, file):
        template = None
        file_path = get_app_path() + Setup.EXPORT_PATH + os.sep + Setup.TEMPLATE_PATH + os.sep + file
        try:
            with open(file_path, 'r', encoding='utf-8') as json_file:
                template = json.load(json_file)
        except Exception as e:
            logging.error(self.tr("Can't load report template from file ") + f"'{file_path}' ({type(e).__name__} {e})")
        return template

    def output_data(self, data, template_file, parameters):
        template = self.load_template(template_file)
        if template is None or not data:
            return
        sheet = self.workbook.add_worksheet(template['page'])
        self.add_report_title(sheet, template['title'])
        row = self.add_report_headers(sheet, template['headers'], parameters)
        numbered = template['columns_numbered'] if 'columns_numbered' in template else False
        row = self.add_column_headers(sheet, template['columns'], parameters, start_row=row + 1, numbered=numbered)
        for i, values in enumerate(data):
            try:
                row_template_name = values['report_template']
            except KeyError:
                raise RuntimeError(self.tr("No report row template set"))
            try:
                row_template = template[row_template_name]
            except KeyError:
                raise RuntimeError(self.tr("Report row template not found: ") + row_template_name)
            even_odd = values['report_group'] if "report_group" in values else (i + 1)
            row += self.add_data_row(sheet, row, values, row_template, even_odd=even_odd)
        self.add_report_footers(sheet, template['footers'], start_row=row + 1)

    def output_model(self, report_name, model):
        sheet = self.workbook.add_worksheet(report_name)
        headers = []
        for col in range(model.columnCount()):   # 8.43 is adjustment coefficient for default font - see xlsxwriter.set_column() help
            headers.append({"name": model.headerData(col, Qt.Horizontal), "width": model.headerWidth(col)/8.43})
        row = self.add_column_headers(sheet, headers, {}, start_row=0)
        self.output_model_element(sheet, model, QModelIndex(), row)

    def output_model_element(self, sheet, model, element, start_row, level=0):
        row = start_row
        for i in range(model.rowCount(parent=element)):
            values = {}
            template = {"rows": [[]], "formats": [[]]}
            for j in range(model.columnCount()):
                field_name = f"{j}"
                if j == 0 and level:  # Make indent for tree levels
                    values[field_name] = ('   ' * level) + str(model.data(model.index(i, j, parent=element)))
                else:
                    values[field_name] = model.data(model.index(i, j, parent=element))
                template["rows"][0].append(field_name)
                template["formats"][0].append("T")
            row += self.add_data_row(sheet, row, values, template)
            if model.index(0, 0, model.index(0, 0, QModelIndex())) != model.index(0, 0, QModelIndex()):  # Traverse tree
                row = self.output_model_element(sheet, model, model.index(i, 0, parent=element), row, level + 1)
        return row

    # Put bold title in cell A1
    def add_report_title(self, sheet, title):
        sheet.write(0, 0, title, self.formats.Bold())
    
    # Put report headers below the title, skip one row after title
    # Returns last used row
    def add_report_headers(self, sheet, headers, parameters, start_row=2):
        for i, header in enumerate(headers):
            sheet.write(start_row + i, 0, header.format(parameters=parameters), self.formats.CommentText())
        return start_row + len(headers)

    # Put titles for columns of the report
    # Returns last used row
    def add_column_headers(self, sheet, columns, parameters, start_row=2, numbered=False):
        sheet.set_row(start_row, 60)
        for i, column in enumerate(columns):
            title = column['name'].format(parameters=parameters)
            sheet.write(start_row, i, title, self.formats.ColumnHeader())
            sheet.set_column(i, i, column['width'])
            if numbered:
                sheet.write(start_row + 1, i,  f"({i + 1})", self.formats.ColumnHeader())
        last_row = start_row+2 if numbered else start_row+1
        return last_row

    def add_data_row(self, sheet, start_row, values, template, even_odd=1):
        for row, row_template in enumerate(template['rows']):
            for col, column_key in enumerate(row_template):
                if column_key is None:
                    continue
                try:
                    value = values[column_key]
                except KeyError:
                    value = column_key   # Use original text if there are no such key
                try:
                    value, value_format = self.apply_format(value, template['formats'][row][col], even_odd)
                except KeyError:
                    logging.warning(self.tr("Format is missing for report field: ") + column_key)
                    value_format = self.formats.Text(even_odd)
                if 'span' in template and not template['span'][row][col] is None:
                    span = template['span'][row][col]
                    sheet.merge_range(start_row+row, col, start_row+row+span['v'], col+span['h'], value, value_format)
                else:
                    sheet.write(start_row+row, col, value, value_format)
        return len(template['rows'])

    def apply_format(self, value, format_string, even_odd=1):
        if format_string is None:
            return value, self.formats.Text(even_odd)
        if format_string[0] == 'T':
            if format_string[2:] == 'B':
                return value, self.formats.Bold()
            else:
                return value, self.formats.Text(even_odd)
        elif format_string[0] == 'D':
            value = ts2d(value)
            return value, self.formats.Text(even_odd)
        elif format_string[0] == 'N':
            return value, self.formats.Number(even_odd, tolerance=int(format_string[2:]))
        elif format_string[0] == 'F':
            return value, self.formats.ColumnFooter()
        elif format_string[0] == '-':
            return value, self.formats.NoFormat()
        else:
            logging.warning(self.tr("Unrecognized format string: ") + format_string)
            return value, self.formats.Text(even_odd)

    # Put report footers from start_row and below
    # Returns last used row
    def add_report_footers(self, sheet, footers, start_row=2):
        for i, footer in enumerate(footers):
            sheet.write(start_row + i, 0, footer, self.formats.CommentText())
        return start_row + len(footers)

#-----------------------------------------------------------------------------------------------------------------------
class xslxFormat:
    def __init__(self, workbook):
        self.wbk = workbook
        self.even_color_bg = '#C0C0C0'
        self.odd_color_bg = '#FFFFFF'
        self.text_font_size = 9

    def Bold(self):
        return self.wbk.add_format({'font_size': self.text_font_size,
                                    'bold': True})

    def ColumnHeader(self):
        return self.wbk.add_format({'font_size': self.text_font_size,
                                    'bold': True,
                                    'text_wrap': True,
                                    'align': 'center',
                                    'valign': 'vcenter',
                                    'bg_color': '#808080',
                                    'font_color': '#FFFFFF',
                                    'border': 1})

    def ColumnFooter(self):
        return self.wbk.add_format({'font_size': self.text_font_size,
                                    'bold': True,
                                    'num_format': '#,###,##0.00',
                                    'bg_color': '#808080',
                                    'font_color': '#FFFFFF',
                                    'border': 1})

    def NoFormat(self):
        return self.wbk.add_format({'font_size': self.text_font_size})

    def Text(self, even_odd_value=1):
        if even_odd_value % 2:
            bg_color = self.odd_color_bg
        else:
            bg_color = self.even_color_bg
        return self.wbk.add_format({'font_size': self.text_font_size,
                                    'border': 1,
                                    'valign': 'vcenter',
                                    'bg_color': bg_color,
                                    'text_wrap': True})

    def CommentText(self):
        return self.wbk.add_format({'font_size': self.text_font_size, 'valign': 'vcenter'})

    def Number(self, even_odd_value=1, tolerance=2, center=False):
        if even_odd_value % 2:
            bg_color = self.odd_color_bg
        else:
            bg_color = self.even_color_bg
        num_format = ''
        if tolerance > 0:
            num_format = '#,###,##0.'
            for i in range(tolerance):
                num_format = num_format + '0'
        if center:
            align = 'center'
        else:
            align = 'right'
        return self.wbk.add_format({'font_size': self.text_font_size,
                                    'num_format': num_format,
                                    'border': 1,
                                    'align': align,
                                    'valign': 'vcenter',
                                    'bg_color': bg_color})
