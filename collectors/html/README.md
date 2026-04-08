# HTML Collector

Detects and lints HTML, CSS, SCSS, and LESS files.

## Overview

Scans repositories for HTML and CSS-family files, runs HTMLHint and Stylelint for code quality analysis. Writes file counts per type and lint results so policies can enforce markup quality standards. Runs in a custom `html-main` image with Node.js, HTMLHint, and Stylelint pre-installed.

## Collected Data

This collector writes to the following Component JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.lang.html` | object | Present only if `.html` files found |
| `.lang.html.file_count` | number | Number of `.html` files in the repository |
| `.lang.html.lint` | object | Normalized HTMLHint lint warnings |
| `.lang.html.native.htmlhint` | object | Raw HTMLHint output and status |
| `.lang.css` | object | Present only if `.css` files found |
| `.lang.css.file_count` | number | Number of `.css` files |
| `.lang.css.lint` | object | Normalized Stylelint lint warnings (covers CSS/SCSS/LESS) |
| `.lang.css.native.stylelint` | object | Raw Stylelint output and status |
| `.lang.scss` | object | Present only if `.scss` files found |
| `.lang.scss.file_count` | number | Number of `.scss` files |
| `.lang.less` | object | Present only if `.less` files found |
| `.lang.less.file_count` | number | Number of `.less` files |

## Collectors

This integration provides the following collectors (use `include` to select a subset):

| Collector | Hook Type | Description |
|-----------|-----------|-------------|
| `project` | code | Detects HTML/CSS/SCSS/LESS files, writes counts to `.lang.html`, `.lang.css`, `.lang.scss`, `.lang.less` |
| `htmlhint` | code | Runs HTMLHint on `.html` files, writes lint results to `.lang.html.lint` |
| `stylelint` | code | Runs Stylelint on CSS/SCSS/LESS files, writes lint results to `.lang.css.lint` |

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/html@v1.0.0
    on: ["domain:your-domain"]
    # include: [project, htmlhint]  # Only include specific subcollectors
```
