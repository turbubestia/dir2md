# React

## What It Is

React is a JavaScript library for building user interfaces. Instead of writing
one large page by hand, you build small reusable components and let React
compose them into a screen.

## What Problem It Solves

React helps when a page has many moving parts: buttons, forms, tabs, live
status, and previews. It keeps the UI organized by splitting it into components
that manage their own state and render themselves from data.

## Quick Start

1. Write a component as a function that returns JSX.
2. Pass data into the component with props.
3. Use hooks like `useState` and `useEffect` when the component needs local
	 state or to react to data loading.
4. Compose simple components into larger screens.

Example:

```tsx
function Greeting({ name }: { name: string }) {
	return <h1>Hello, {name}</h1>
}
```

## How This Project Uses It

This project uses React for the whole web UI:

- `src/webapp/frontend/src/main.tsx` mounts the app into the page.
- `src/webapp/frontend/src/App.tsx` chooses the top-level shell.
- `src/webapp/frontend/src/components/WorkspaceShell.tsx` builds the main
	layout.
- `src/webapp/frontend/src/components/WorkflowPanel.tsx` owns the workflow
	screen.
- `src/webapp/frontend/src/components/SettingsForm.tsx` owns the settings form.
- `src/webapp/frontend/src/components/LlmTestPanel.tsx` owns the prompt editor
	and test response panel.

React is what makes those sections update live when the user clicks a button,
types in a field, or receives a new backend response.

## When You Would Edit It

Edit React components when you want to change layout, interaction, or what data
is shown on screen.
