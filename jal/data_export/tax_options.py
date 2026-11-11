from dataclasses import dataclass
from PySide6.QtCore import QCoreApplication

# Context of every string of an option: the tax dialog's own. A declaration spells it out as the literal
# "TaxWidget" in QT_TRANSLATE_NOOP, as 'lupdate' skips a context given by a variable.
TR_CONTEXT = "TaxWidget"


# Types an option may have; the type decides which editor the tax dialog builds for it
class OptionType:
    Boolean = 1
    Choice = 2     # one of 'choices'


# One option of a tax report or of a tax form file, declared by the class that reads it. The tax dialog builds an
# editor for it and hands the value over under 'key', as a keyword argument.
@dataclass
class TaxOption:
    key: str
    label: str                 # untranslated, as 'comment' and the labels of 'choices'
    type: int = OptionType.Boolean
    default: object = False
    comment: str = ''          # a line shown under the option
    choices: tuple = ()        # Choice only: (value, label) pairs

    def translated_label(self) -> str:
        return QCoreApplication.translate(TR_CONTEXT, self.label)

    def translated_comment(self) -> str:
        return QCoreApplication.translate(TR_CONTEXT, self.comment) if self.comment else ''

    def translated_choices(self) -> list:
        return [(value, QCoreApplication.translate(TR_CONTEXT, label)) for value, label in self.choices]


# The values of 'options' out of 'given', the default of each one not given
def option_values(options: list, given: dict) -> dict:
    return {x.key: given.get(x.key, x.default) for x in options}
