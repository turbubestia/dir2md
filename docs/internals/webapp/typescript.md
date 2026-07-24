# TypeScript

## What It Is

TypeScript is JavaScript with a type system. You still write JavaScript-like
code, but you also describe the shape of your data so tooling can catch mistakes
before the app runs.

## What Problem It Solves

In a UI project, many bugs come from using the wrong property name, passing the
wrong data shape, or forgetting that a value may be `null`. TypeScript helps
find those mistakes early and makes code easier to understand.

## Quick Start

1. Define interfaces for the data you pass around.
2. Add type annotations to function parameters and return values.
3. Let the compiler point out mismatches.
4. Keep shared API shapes in a single place instead of re-typing them in every
	 component.

Example:

```ts
interface User {
	name: string
	age: number
}

function formatUser(user: User): string {
	return `${user.name} (${user.age})`
}
```

## How This Project Uses It

This project uses TypeScript across the frontend:

- `src/webapp/frontend/src/types.ts` defines the shared frontend data shapes.
- `src/webapp/frontend/src/api.ts` uses those types for API responses.
- `src/webapp/frontend/src/components/*.tsx` use typed props and state.
- `src/webapp/frontend/tsconfig.json` and `tsconfig.node.json` configure the
	compiler.

TypeScript is especially useful here because the frontend mirrors the backend
Pydantic models. That keeps the browser UI and Python API aligned.

## When You Would Edit It

Edit TypeScript types when you add or change a backend response, a form model,
or a component prop shape.
