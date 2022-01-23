import xlsxwriter
import logging
from datetime import datetime
from PySide6.QtWidgets import QApplication


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

    def save(self):
        try:
            self.workbook.close()
        except:
            logging.error(QApplication.translate('XLSX', "Can't save report into file ") + f"'{self.filename}'")

    def add_report_sheet(self, name):
        return self.workbook.add_worksheet(name)

    # all parameters are zero-based integer indices
    # Function does following:
    # 1) puts self.totals caption into cell at (footer_row, columns_list[0]) if columns_list[0] is not None
    # 2) puts formula =SUM(start_row+1, footer_row) into all other cells at (footer_row, columns_list[1:])
    # 3) puts 0 instead of SUM if there are no data to make totals
    def add_totals_footer(self, sheet, start_row, footer_row, columns_list):
        if columns_list[0] is not None:
            sheet.write(footer_row, columns_list[0], self.totals, self.formats.ColumnFooter())
        if footer_row > start_row:  # Don't put formulas with pre-definded errors
            for i in columns_list[1:]:
                if i > 25:
                    raise ValueError
                formula = f"=SUM({chr(ord('A')+i)}{start_row + 1}:{chr(ord('A')+i)}{footer_row})"
                sheet.write_formula(footer_row, i, formula, self.formats.ColumnFooter())
        else:
            self.write_zeros(sheet, [footer_row], columns_list[1:], self.formats.ColumnFooter())

    # Fills rectangular area defined by rows and columns with 0 values
    def write_zeros(self, sheet, rows, columns, format):
        for i in rows:
            for j in columns:
                sheet.write(i, j, 0, format)

    def write_row(self, sheet, row, columns, height=None):
        if height:
            sheet.set_row(row, height)
        for column in columns:
            cd = columns[column]
            if len(cd) != 2:
                if cd[self.ROW_WIDTH]:
                    sheet.set_column(column, column, cd[self.ROW_WIDTH])
                if cd[self.ROW_SPAN_H] or cd[self.ROW_SPAN_V]:
                    sheet.merge_range(row, column, row + cd[self.ROW_SPAN_V], column + cd[self.ROW_SPAN_H],
                                        cd[self.ROW_DATA], cd[self.ROW_FORMAT])
            sheet.write(row, column, cd[self.ROW_DATA], cd[self.ROW_FORMAT])

    def output_data(self, sheet, data, template, header_data):
        self.add_report_header(sheet, template, header_data)
        for i, record in enumerate(data):
            self.add_report_row(sheet, template, i+self.START_ROW, record, even_odd=i)
    
    # This method puts header on each report sheet
    def add_report_header(self, sheet, template, header_data):
        sheet.write(0, 0, template[self.RPT_TITLE], self.formats.Bold())
        sheet.write(2, 0, "Документ-основание:", self.formats.CommentText())
        sheet.write(3, 0, f"Период: {datetime.utcfromtimestamp(header_data['year_begin']).strftime('%d.%m.%Y')}"
                                       f" - {datetime.utcfromtimestamp(header_data['year_end'] - 1).strftime('%d.%m.%Y')}",
                                 self.formats.CommentText())
        sheet.write(4, 0, "ФИО:", self.formats.CommentText())
        sheet.write(5, 0, f"Номер счета: {header_data['account_number']} ({header_data['account_currency']})",
                                 self.formats.CommentText())

        header_row = {}
        numbers_row = {}  # Put column numbers for reference
        for column in template[self.RPT_COLUMNS]:
            # make tuple for each column i: ("Column_Title", xlsx.formats.ColumnHeader(), Column_Width, 0, 0)
            title = template[self.RPT_COLUMNS][column][self.COL_TITLE].format(currency=header_data['account_currency'])
            width = template[self.RPT_COLUMNS][column][self.COL_WIDTH]
            header_row[column] = (title, self.formats.ColumnHeader(), width, 0, 0)
            numbers_row[column] = (f"({column + 1})", self.formats.ColumnHeader())
        self.write_row(sheet, 7, header_row, 60)
        self.write_row(sheet, 8, numbers_row)

    def add_report_row(self, sheet, template, row, data, even_odd=1, alternative=0):
        KEY_NAME = 0
        VALUE_FMT = 1
        FMT_DETAILS = 2
        H_SPAN = 3
        V_SPAN = 4

        data_row = {}
        idx = self.COL_FIELD + alternative
        for column in template[self.RPT_COLUMNS]:
            field_dscr = template[self.RPT_COLUMNS][column][idx]
            if field_dscr is not None:
                value = data[field_dscr[KEY_NAME]]
                format_as = field_dscr[VALUE_FMT]
                if format_as == "text":
                    fmt = self.formats.Text(even_odd)
                elif format_as == "number":
                    precision = field_dscr[FMT_DETAILS]
                    fmt = self.formats.Number(even_odd, tolerance=precision)
                elif format_as == "date":
                    value = datetime.utcfromtimestamp(value).strftime('%d.%m.%Y')
                    fmt = self.formats.Text(even_odd)
                elif format_as == "bool":
                    value = field_dscr[FMT_DETAILS][value]
                    fmt = self.formats.Text(even_odd)
                else:
                    raise ValueError
                if len(field_dscr) == 5:  # There are horizontal or vertical span defined
                    data_row[column] = (value, fmt, 0, field_dscr[H_SPAN], field_dscr[V_SPAN])
                else:
                    data_row[column] = (value, fmt)
        self.write_row(sheet, row, data_row)

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

    def Text(self, even_odd_value=1):
        if even_odd_value % 2:
            bg_color = self.odd_color_bg
        else:
            bg_color = self.even_color_bg
        return self.wbk.add_format({'font_size': self.text_font_size,
                                    'border': 1,
                                    'valign': 'vcenter',
                                    'bg_color': bg_color})

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
