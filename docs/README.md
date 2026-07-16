# docs

`img/` holds the TUI screenshots embedded in the top-level README — real tool output, rendered to
SVG via `rich.Console(record=True).save_svg()` rather than a terminal screen-grab. Regenerate them
with:

```bash
.venv/bin/python scripts/render_tui_screenshot.py sample.log docs/img/tui-demo.svg \
    "geotail --demo --file sample.log --tui"
```

See `scripts/render_tui_screenshot.py --help` (or just read the docstring) for the full usage,
including `--real` to render against the BIN files in `./data/` instead of `--demo` data.

An animated GIF would be a nice upgrade over the static screenshots: record with `vhs` or
`asciinema` + `agg`, running `geotail --demo` in an 80x24 terminal, save as `img/demo.gif`, and
reference it from the top of the README.
