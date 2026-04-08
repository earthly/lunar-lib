# Web Collector

Detects HTML and CSS/preprocessor files for frontend project categorization.

## Overview

Scans repositories for HTML, CSS, SCSS, and LESS files to determine whether a project is a frontend repo or has incidental web files. Writes file counts per type so policies can distinguish between a full frontend project and a repo with a few HTML docs. No external tools required.

## Collected Data

This collector writes to the following Component JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.lang.html` | object | Present only if `.html` files found |
| `.lang.html.file_count` | number | Number of `.html` files in the repository |
| `.lang.css` | object | Present only if `.css` files found |
| `.lang.css.file_count` | number | Number of `.css` files |
| `.lang.scss` | object | Present only if `.scss` files found |
| `.lang.scss.file_count` | number | Number of `.scss` files |
| `.lang.less` | object | Present only if `.less` files found |
| `.lang.less.file_count` | number | Number of `.less` files |

## Collectors

This integration provides the following collectors (use `include` to select a subset):

| Collector | Hook Type | Description |
|-----------|-----------|-------------|
| `project` | code | Detects HTML/CSS/SCSS/LESS files, writes counts to `.lang.html`, `.lang.css`, `.lang.scss`, `.lang.less` |

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/web@v1.0.0
    on: ["domain:your-domain"]
```
