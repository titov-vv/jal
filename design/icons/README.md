# Application icon sources

Vector sources for the JAL application icon. These are not packaged with the application -
only the rendered PNG in `jal/img/` is.

| File | Used as |
|---|---|
| `jal_icon.svg` | The application icon. A "J" standing on the accountant's double rule - the line that closes a column and marks the total. |
| `jal_icon_coin.svg` | The project mark - a coin with the "J" struck out of it. Used by the documentation site and the READMEs, never inside the application. |
| `social_preview.svg` | The 1280x640 card shown when a link to the project is shared. |

Re-render after editing (the sources are vector, so any size works):

```bash
# application icon
rsvg-convert -w 256 -h 256 design/icons/jal_icon.svg -o jal/img/ui_jal.png
# documentation site favicon, logo and link card
rsvg-convert -w 32 -h 32 design/icons/jal_icon_coin.svg -o docs/img/favicon-32.png
rsvg-convert -w 180 -h 180 design/icons/jal_icon_coin.svg -o docs/img/favicon-180.png
rsvg-convert -w 128 -h 128 design/icons/jal_icon_coin.svg -o docs/img/jal_logo.png
rsvg-convert -w 1280 -h 640 design/icons/social_preview.svg -o docs/img/social_preview.png
```

`docs/img/social_preview.png` also has to be uploaded manually in the repository settings
(*Settings -> General -> Social preview*) - GitHub does not read it from the repository.
