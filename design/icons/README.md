# Application icon sources

Vector sources for the JAL application icon. These are not packaged with the application -
only the rendered PNG in `jal/img/` is.

| File | Used as |
|---|---|
| `jal_icon.svg` | The application icon. A "J" standing on the accountant's double rule - the line that closes a column and marks the total. |
| `jal_icon_coin.svg` | Alternative mark kept for other uses (documentation, project pages) - a coin with the "J" struck out of it. |

Re-render after editing (any size, the source is 512x512 vector):

```bash
rsvg-convert -w 256 -h 256 design/icons/jal_icon.svg -o jal/img/ui_jal.png
```
