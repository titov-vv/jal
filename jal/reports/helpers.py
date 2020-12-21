
class xslxFormat:
    def __init__(self, workbook):
        self.wbk = workbook
        self.even_color_bg = '#C0C0C0'
        self.odd_color_bg = '#FFFFFF'

    def Bold(self):
        return self.wbk.add_format({'bold': True})

    def ColumnHeader(self):
        return self.wbk.add_format({'bold': True,
                                    'text_wrap': True,
                                    'align': 'center',
                                    'valign': 'vcenter',
                                    'bg_color': '#808080',
                                    'font_color': '#FFFFFF',
                                    'border': 1})

    def ColumnFooter(self):
        return self.wbk.add_format({'bold': True,
                                    'num_format': '#,###,##0.00',
                                    'bg_color': '#808080',
                                    'font_color': '#FFFFFF',
                                    'border': 1})

    def Text(self, even_odd_value=1):
        if even_odd_value % 2:
            bg_color = self.odd_color_bg
        else:
            bg_color = self.even_color_bg
        return self.wbk.add_format({'border': 1,
                                    'valign': 'vcenter',
                                    'bg_color': bg_color})

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
        return self.wbk.add_format({'num_format': num_format,
                                    'border': 1,
                                    'align': align,
                                    'valign': 'vcenter',
                                    'bg_color': bg_color})

#-----------------------------------------------------------------------------------------------------------------------
ROW_DATA = 0
ROW_FORMAT = 1
ROW_WIDTH = 2
ROW_SPAN_H = 3
ROW_SPAN_V = 4


def xlsxWriteRow(wksheet, row, columns, height=None):
    if height:
        wksheet.set_row(row, height)
    for column in columns:
        cd = columns[column]
        if len(cd) != 2:
            if cd[ROW_WIDTH]:
                wksheet.set_column(column, column, cd[ROW_WIDTH])
            if cd[ROW_SPAN_H] or cd[ROW_SPAN_V]:
                wksheet.merge_range(row, column, row+cd[ROW_SPAN_V], column+cd[ROW_SPAN_H],
                                    cd[ROW_DATA], cd[ROW_FORMAT])
        wksheet.write(row, column, cd[ROW_DATA], cd[ROW_FORMAT])