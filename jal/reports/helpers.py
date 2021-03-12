import xlsxwriter
import logging

from jal.widgets.helpers import g_tr


#-----------------------------------------------------------------------------------------------------------------------
# Class to encapsulate all xlsxwriter-related activities - like formatting, formulas, etc
class XLSX:
    ROW_DATA = 0
    ROW_FORMAT = 1
    ROW_WIDTH = 2
    ROW_SPAN_H = 3
    ROW_SPAN_V = 4
    totals = "ИТОГО"

    def __init__(self, xlsx_filename):
        self.filename = xlsx_filename
        self.workbook = xlsxwriter.Workbook(filename=xlsx_filename)
        self.formats = xslxFormat(self.workbook)

    def save(self):
        try:
            self.workbook.close()
        except:
            logging.error(g_tr('XLSX', "Can't save report into file ") + f"'{self.filename}'")

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
