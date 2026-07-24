# Tailwind CSS

## What It Is

Tailwind CSS is a utility-first CSS framework. Instead of writing lots of custom
CSS selectors, you build styles from small classes like `flex`, `px-4`,
`border`, or `text-sm`.

## What Problem It Solves

It makes it easier to keep a design system consistent. You can reuse the same
spacing, colors, borders, and typography patterns across many components
without writing a large stylesheet from scratch.

## Quick Start

1. Add Tailwind to the project build.
2. Define your theme tokens in `tailwind.config.ts`.
3. Use utility classes directly in your markup.
4. Put repeated patterns into reusable component classes if needed.

Example:

```tsx
<button className="rounded bg-sky-500 px-3 py-2 text-white">
	Save
</button>
```

## How This Project Uses It

This project uses Tailwind as the main visual system for the frontend:

- `src/webapp/frontend/tailwind.config.ts` defines the color palette.
- `src/webapp/frontend/src/styles.css` builds reusable component classes on top
	of Tailwind utilities.
- `src/webapp/frontend/src/components/*.tsx` use those classes to style panels,
	buttons, rows, workflow stages, and preview areas.

The project uses a dark shell with light blue accents. If you want to change the
look of the app, Tailwind config and `styles.css` are the first places to check.

## When You Would Edit It

Edit Tailwind config when you want to change theme colors or spacing tokens.
Edit `styles.css` when you want to change shared component styles.
