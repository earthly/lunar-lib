# Web Collector

Detects HTML and CSS/preprocessor files for frontend project categorization.

## Overview

Scans repositories for HTML, CSS, SCSS, and LESS files to determine whether a project is a frontend repo or has incidental web files. Writes file counts per type so policies can distinguish between a full frontend project and a repo with a few HTML docs. No external tools required.

## Collected Data

This collector writes to the following Component JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.lang.html` | object | HTML file detection data (present only if `.html` files found) |
| `.lang.html.file_count` | number | Number of `.html` files in the repository |
| `.lang.css` | object | CSS/preprocessor detection data (present only if `.css`/`.scss`/`.less` files found) |
| `.lang.css.file_count` | number | Number of `.css` files |
| `.lang.css.scss_file_count` | number | Number of `.scss` files |
| `.lang.css.less_file_count` | number | Number of `.less` files |
| `.lang.css.preprocessors` | array | Detected preprocessors (e.g., `["scss", "less"]`) |

## Collectors

This integration provides the following collectors (use `include` to select a subset):

| Collector | Hook Type | Description |
|-----------|-----------|-------------|
| `project` | code | Detects HTML and CSS-family files, writes counts to `.lang.html` and `.lang.css` |

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/web@v1.0.0
    on: ["domain:your-domain"]
```
