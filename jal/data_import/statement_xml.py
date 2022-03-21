import logging
from datetime import datetime, timezone
from lxml import etree
from PySide6.QtWidgets import QApplication
from jal.data_import.statement import Statement, FOF, Statement_ImportError


# -----------------------------------------------------------------------------------------------------------------------
# Base class to load XML-based statements
class StatementXML(Statement):
    statements_path = ''    # Where in XML structure search for statements
    statement_tag = ''      # Tag of the statement in XML (there might be several statements in one XML)
    STATEMENT_ROOT = '<statement_root>'

    def __init__(self):
        super().__init__()
        self.statement_name = ''
        self._sections = {}
        self._data = {
            FOF.PERIOD: [None, None],
            FOF.ACCOUNTS: [],
            FOF.ASSETS: [],
            FOF.SYMBOLS: [],
            FOF.ASSETS_DATA: [],
            FOF.TRADES: [],
            FOF.TRANSFERS: [],
            FOF.CORP_ACTIONS: [],
            FOF.ASSET_PAYMENTS: [],
            FOF.INCOME_SPENDING: []
        }
        self.attr_loader = {
            str: self.attr_string,
            float: self.attr_number,
            datetime: self.attr_timestamp
        }

    # -----------------------------------------------------------------------------------------------------------------------
    # Helpers to get values from XML tag properties
    # Convert attribute 'attr_name' value to string or return default value if attribute not found
    @staticmethod
    def attr_string(xml_element, attr_name, default_value):
        if attr_name not in xml_element.attrib:
            return default_value
        return xml_element.attrib[attr_name].strip()

    # Convert attribute 'attr_name' value to float or return default value if attribute not found / not a number
    @staticmethod
    def attr_number(xml_element, attr_name, default_value):
        if attr_name not in xml_element.attrib:
            return default_value
        try:
            value = float(xml_element.attrib[attr_name])
        except ValueError:
            return None
        return value

    # Convert attribute 'attr_name' value from strings "YYYYMMDD:hhmmss' or "YYYYMMDD" to datetime object
    # or return default value if attribute not found / has wrong format
    @staticmethod
    def attr_timestamp(xml_element, attr_name, default_value):
        if attr_name not in xml_element.attrib:
            return default_value
        time_str = xml_element.attrib[attr_name]
        try:
            if len(time_str) == 19:  # YYYY-MM-DDTHH:MM:SS
                return int(datetime.strptime(time_str, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc).timestamp())
            if len(time_str) == 15:  # YYYYMMDD;HHMMSS
                return int(datetime.strptime(time_str, "%Y%m%d;%H%M%S").replace(tzinfo=timezone.utc).timestamp())
            elif len(time_str) == 8:  # YYYYMMDD
                return int(datetime.strptime(time_str, "%Y%m%d").replace(tzinfo=timezone.utc).timestamp())
            else:
                return default_value
        except ValueError:
            raise Statement_ImportError(QApplication.translate("StatementXML", "Unsupported date/time format: ")
                                        + f"{xml_element.attrib[attr_name]}")

    def load(self, filename: str) -> None:
        try:
            xml_root = etree.parse(filename)
        except etree.XMLSyntaxError as e:
            raise Statement_ImportError(self.tr("Can't parse XML file: ") + e.msg)
        self.validate_file_header_attributes(xml_root.findall('.')[0].attrib)
        statements = xml_root.findall(self.statements_path)
        for statement in statements:
            if statement.tag != self.statement_tag:
                continue
            header_data = self.get_section_data(statement)
            self._sections[StatementXML.STATEMENT_ROOT]['loader'](header_data)

            for section in self._sections:
                if section == StatementXML.STATEMENT_ROOT:
                    continue  # skip header description
                section_elements = statement.xpath(section)  # Actually should be list of 0 or 1 element
                if section_elements:
                    section_data = self.get_section_data(section_elements[0])
                    if section_data is None:
                        return
                    self._sections[section]['loader'](section_data)
        logging.info(self.statement_name + self.tr(" loaded successfully"))

    def validate_file_header_attributes(self, xml_data):
        return

    def get_section_data(self, section):
        if section.tag == self.statement_tag:  # This is header section
            return self.parse_attributes(StatementXML.STATEMENT_ROOT, section)
        try:
            tag = self._sections[section.tag]['tag']
        except KeyError:
            return []  # This section isn't used for import
        data = []
        for element in section.xpath(tag):
            attributes = self.parse_attributes(section.tag, element)
            if attributes is not None:
                data.append(attributes)
        return data

    def parse_attributes(self, section_tag, element):
        tag_dictionary = {}
        if self._sections[section_tag]['level']:  # Skip extra lines (SUMMARY, etc)
            if self.attr_string(element, 'levelOfDetail', '') != self._sections[section_tag]['level']:
                return None
        for attr_name, key_name, attr_type, attr_default in self._sections[section_tag]['values']:
            attr_value = self.attr_loader[attr_type](element, attr_name, attr_default)
            if attr_value is None:
                raise Statement_ImportError(self.tr("Failed to load attribute: ") + f"{attr_name} / {element.attrib}")
            tag_dictionary[key_name] = attr_value
        return tag_dictionary

    # Removes all keys listed in extra_keys_list from operation_dict
    def drop_extra_fields(self, operation_dict, extra_keys_list):
        for key in extra_keys_list:
            if key in operation_dict:
                del operation_dict[key]
