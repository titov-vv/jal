from enum import Enum, auto
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication


# ----------------------------------------------------------------------------------------------------------------------
class Meaning(Enum):      # Semantic - what the value IS
    POSITIVE = auto()     # money in, a gain, a confident guess
    NEGATIVE = auto()     # money out, a loss, an invalid field, an error
    WARNING = auto()      # worth a second look, but nothing is wrong yet
    INFO = auto()         # marked, reconciled, plotted - noticeable without being a verdict
    MUTED = auto()        # present but secondary: a zero, a debug line, a marker's border
    # Categorical - the six kinds of row in the pending-transfers report. These are told apart from each other
    # rather than judged, so they are hues rather than verdicts, except the last two which are also warnings.
    SENT = auto()
    ARRIVED = auto()
    BRIDGE = auto()
    BASIS = auto()
    POISONING = auto()
    AIRDROP = auto()


# Hue in degrees and saturation in percent for each meaning. MUTED has no hue: it is a blend of the palette's own
# text color into the ground, which is what "grey" has to mean when the ground may be any color.
# These are the one place a color decision lives. Retuning a meaning is an edit here and nowhere else.
_ANCHOR = {
    Meaning.POSITIVE:  (120, 100),
    Meaning.NEGATIVE:  (0, 100),
    Meaning.WARNING:   (45, 100),
    Meaning.INFO:      (225, 100),
    Meaning.SENT:      (50, 100),
    Meaning.ARRIVED:   (210, 100),
    Meaning.BRIDGE:    (120, 100),
    Meaning.BASIS:     (265, 100),
    Meaning.POISONING: (0, 100),
    Meaning.AIRDROP:   (30, 100)
}

_FILL_STRENGTH = 0.50      # how much of the hue is mixed into the ground for a deliberately colored cell
_TINT_STRENGTH = 0.12      # ... and for a row tint, which has to stay behind its own text
_SEPARATOR_STRENGTH = 0.22 # grid lines: the palette's text color, mostly dissolved into the ground
_PLATE_STRENGTH = 0.88     # the plate under an unreadable picture: nearly all the way to the text color
_MUTED_STRENGTH = 0.55     # MUTED text: more than half way from the ground to the text color

# WCAG AA for body text. MUTED is deliberately quieter - it is secondary information and forcing it to 4.5 would
# make it indistinguishable from ordinary text, which defeats the point - so it gets the large-text/non-text floor.
_MIN_CONTRAST = 4.5
_MIN_CONTRAST_MUTED = 3.0

_LIGHTNESS_STEP = 2        # percent per iteration while solving for a readable lightness


def _luminance(color: QColor) -> float:
    def channel(value: int) -> float:
        value = value / 255
        return value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4
    return 0.2126 * channel(color.red()) + 0.7152 * channel(color.green()) + 0.0722 * channel(color.blue())


# WCAG contrast ratio, 1.0 (identical) to 21.0 (black on white)
def contrast(first: QColor, second: QColor) -> float:
    light, dark = sorted((_luminance(first), _luminance(second)), reverse=True)
    return (light + 0.05) / (dark + 0.05)


def _mix(color: QColor, ground: QColor, strength: float) -> QColor:
    return QColor(round(color.red() * strength + ground.red() * (1 - strength)),
                  round(color.green() * strength + ground.green() * (1 - strength)),
                  round(color.blue() * strength + ground.blue() * (1 - strength)))


# True if the ground is dark enough that a color drawn on it should be lightened rather than darkened.
# Asked as a question about contrast rather than about lightness, so a mid-tone ground goes whichever way
# actually gains more separation.
def _needs_light_ink(ground: QColor) -> bool:
    return contrast(QColor(255, 255, 255), ground) > contrast(QColor(0, 0, 0), ground)


# Keeps the hue and saturation, and walks the lightness away from the ground until the color is readable on it.
# Starts close to the ground and stops at the first lightness that clears the minimum, so the color stays as
# saturated as the requirement allows instead of going all the way to a washed-out pastel or a near-black.
def _readable(hue: int, saturation: int, ground: QColor, minimum: float) -> QColor:
    lighten = _needs_light_ink(ground)
    lightness = 70 if lighten else 30
    step = _LIGHTNESS_STEP if lighten else -_LIGHTNESS_STEP
    best, best_ratio = None, -1.0
    while 0 <= lightness <= 100:
        candidate = QColor.fromHsl(hue, round(saturation * 255 / 100), round(lightness * 255 / 100))
        ratio = contrast(candidate, ground)
        if ratio > best_ratio:
            best, best_ratio = candidate, ratio
        if ratio >= minimum:
            return candidate
        lightness += step
    return best   # the ground leaves no readable lightness at this hue - hand back the most legible one there was


# ----------------------------------------------------------------------------------------------------------------------
# Derived colours are cached, because they are asked for once per painted cell. The cache is keyed by the palette's
# own cacheKey(), which Qt changes whenever the palette does - so a system theme switch invalidates everything here
# with no event plumbing at all. Widgets that ASK for a colour while painting therefore need no notification; only
# the few that apply a palette once and keep it have to listen for QEvent.ApplicationPaletteChange themselves.
_cache = {}
_cache_palette = None


def _palette() -> QPalette:
    return QApplication.palette() if QApplication.instance() is not None else QPalette()


# True when the application is running on a dark ground. Exposed for the few surfaces that have to choose between
# two ready-made appearances instead of deriving a colour - QChart, which paints its own background and picks its
# label colours from a chart theme of its own, knowing nothing about QPalette.
def is_dark_theme() -> bool:
    return _needs_light_ink(_palette().base().color())


class Theme:
    # Ink: a colour to draw text, a line or a marker WITH, readable on the given ground (the palette's Base by default)
    @classmethod
    def text(cls, meaning: Meaning, ground: QColor = None) -> QColor:
        return cls._derive('text', meaning, ground)

    # A cell background that is coloured on purpose - the value in it stays readable
    @classmethod
    def fill(cls, meaning: Meaning, ground: QColor = None) -> QColor:
        return cls._derive('fill', meaning, ground)

    # A row tint that groups a list at a glance without competing with the text on top of it
    @classmethod
    def tint(cls, meaning: Meaning, ground: QColor = None) -> QColor:
        return cls._derive('tint', meaning, ground)

    # Grid lines and hairline dividers: visible, achromatic, and never mistaken for content
    @classmethod
    def separator(cls, ground: QColor = None) -> QColor:
        return cls._derive('separator', None, ground)

    # The plate that goes under a picture which would otherwise dissolve into the ground it is painted on - a dark
    # logo on a dark row (see JalIcons.icon), for example.
    @classmethod
    def plate(cls, ground: QColor = None) -> QColor:
        return cls._derive('plate', None, ground)

    @classmethod
    def _derive(cls, role: str, meaning, ground: QColor) -> QColor:
        global _cache_palette
        palette = _palette()
        if _cache_palette != palette.cacheKey():   # the palette changed - everything derived from it is stale
            _cache.clear()
            _cache_palette = palette.cacheKey()
        if ground is None:
            ground = palette.base().color()
        key = (role, meaning, ground.rgba())
        if key not in _cache:
            _cache[key] = cls._compute(role, meaning, ground, palette)
        return _cache[key]

    @classmethod
    def _compute(cls, role: str, meaning, ground: QColor, palette: QPalette) -> QColor:
        ink = palette.text().color()
        if role == 'separator':
            return _mix(ink, ground, _SEPARATOR_STRENGTH)
        if role == 'plate':
            return _mix(ink, ground, _PLATE_STRENGTH)
        if meaning == Meaning.MUTED:   # achromatic: derived from the palette's own text colour, not from a hue
            if role == 'text':
                muted = _mix(ink, ground, _MUTED_STRENGTH)
                return muted if contrast(muted, ground) >= _MIN_CONTRAST_MUTED else ink
            anchor = ink
        else:
            hue, saturation = _ANCHOR[meaning]
            if role == 'text':
                return _readable(hue, saturation, ground, _MIN_CONTRAST)
            anchor = QColor.fromHsl(hue, round(saturation * 255 / 100), 128)
        # A fill or a tint: mix the anchor into the ground, and back off if that would leave the text on it unreadable
        strength = _FILL_STRENGTH if role == 'fill' else _TINT_STRENGTH
        while strength > 0.05:
            mixed = _mix(anchor, ground, strength)
            if contrast(ink, mixed) >= _MIN_CONTRAST:
                return mixed
            strength -= 0.05
        return _mix(anchor, ground, 0.05)
