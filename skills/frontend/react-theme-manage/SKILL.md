---
name: react-theme-manage
description: "Use when updating React component styles for dark/ligh theme support."
version: 0.1.0
author: andrej, Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [frontend, react, theming]
    related_skills: []
---

# React Theme Management Skill

## When to Use
- You need to toggle component styles between dark and light modes using Tailwind.
- The component uses a className string that must change dynamically.
- You have access to a `theme` state variable (`'dark' | 'light'`).
- You want to avoid undefined variable references (e.g., `disabled`).

## How to Run
Run the following sequence via the `terminal` tool or the Hermes workflow:
1. Open the target file (e.g., `frontend/src/App.tsx`).
2. Patch the `className` string per the reference table.
3. Run `npm run build` to verify no lint errors.
4. Test the UI in both themes.

## Reference
See `references/button-theme.md` for the class mapping and condition logic.

## Procedure
1. `patch` the file to replace the old className (search for the button definition).  
2. Use a template literal:
   ```tsx
   className={`p-3 rounded-xl transition-colors flex items-center justify-center min-w-[48px] ${theme === 'dark' ? 'bg-indigo-600 text-white hover:bg-indigo-700' : 'bg-slate-200 text-gray-800 hover:bg-slate-300'} ${!input.trim() ? 'opacity-50' : ''}`}
   ```
3. Remove any reference to an undefined `disabled` variable.
4. Run `npm run build`.
5. Verify via `npx tsc --noEmit`.
6. Switch themes to confirm visual correctness.

## Pitfalls
- **Undefined variables**: referencing `disabled` causes warnings. Use actual form state (`!input.trim()`).
- **Hard‑coded color tokens**: Tailwind utilities come from your config. If you add new colors, update the reference.
- **Missing `theme` state**: Ensure the component passes down the `theme` value.

## Verification
- `npm run build` exits 0 with no warning.
- UI shows the correct background/foreground colors in both modes.
- No console warnings about `Uncaught ReferenceError: disabled is not defined`.
