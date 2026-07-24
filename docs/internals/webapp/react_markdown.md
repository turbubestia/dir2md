# react-markdown

## What It Is

`react-markdown` is a React library that turns Markdown text into rendered React
elements.

## What Problem It Solves

Markdown is a plain-text format, but users usually want to see it rendered as
headings, lists, links, and code blocks. `react-markdown` does that translation
for you in the browser.

## Quick Start

1. Pass a Markdown string to the component.
2. Add plugins if you want GitHub-flavored Markdown, math, or HTML handling.
3. Add sanitization if the content can come from untrusted sources.
4. Style the rendered output with CSS.

Example:

```tsx
import ReactMarkdown from 'react-markdown'

<ReactMarkdown># Hello\n\nThis is **Markdown**.</ReactMarkdown>
```

## How This Project Uses It

This project uses `react-markdown` in `src/webapp/frontend/src/components/MarkdownViewer.tsx`.
That component also uses:

- `remark-gfm` for GitHub-flavored Markdown
- `remark-math` and `rehype-mathjax` for math
- `rehype-raw` and `rehype-sanitize` for safe HTML handling
- `better-react-mathjax` for math rendering support

The Markdown viewer is used in the workflow preview panes and in the LLM test
response panel. It gives the app a readable preview mode without requiring a
full editor.

## How It Fits The Project

In this project, `react-markdown` is the main tool for rendering generated or
saved Markdown content as a preview. It is the library behind the code/preview
view switch explained in the UI docs.

## When You Would Edit It

Edit this area when you want to change how Markdown is rendered, sanitized,
styled, or extended with plugins.
