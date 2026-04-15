---
name: "next-best-practices"
description: "Next.js best practices for file conventions, RSC, async patterns, runtime, data fetching, and more. Invoke when working with Next.js projects."
---

# Next.js Best Practices

Apply these rules when writing or reviewing Next.js code.

## File Conventions

- Project structure and special files
- Route segments (dynamic, catch-all, groups)
- Parallel and intercepting routes
- Middleware rename in v16 (middleware → proxy)

## RSC Boundaries

Detect invalid React Server Component patterns.

- Async client component detection (invalid)
- Non-serializable props detection
- Server Action exceptions

## Async Patterns

Next.js 15+ async API changes.

- Async `params` and `searchParams`
- Async `cookies()` and `headers()`
- Migration codemod

## Runtime Selection

- Default to Node.js runtime
- When Edge runtime is appropriate

## Directives

- `'use client'`, `'use server'` (React)
- `'use cache)

## Functions

- Navigation hooks: `useRouter`,'` (Next.js `usePathname`, `useSearchParams`, `useParams`
- Server functions: `cookies`, `headers`, `draftMode`, `after`
- Generate functions: `generateStaticParams`, `generateMetadata`

## Error Handling

- `error.tsx`, `global-error.tsx`, `not-found.tsx`
- `redirect`, `permanentRedirect`, `notFound`
- `forbidden`, `unauthorized` (auth errors)
- `unstable_rethrow` for catch blocks

## Data Patterns

- Server Components vs Server Actions vs Route Handlers
- Avoiding data waterfalls (`Promise.all`, Suspense, preload)
- Client component data fetching

## Route Handlers

- `route.ts` basics
- GET handler conflicts with `page.tsx`
- Environment behavior (no React DOM)
- When to use vs Server Actions

## Metadata & OG Images

- Static and dynamic metadata
- `generateMetadata` function
- OG image generation with `next/og`
- File-based metadata conventions

## Image Optimization

- Always use `next/image` over `<img>`
- Remote images configuration
- Responsive `sizes` attribute
- Blur placeholders
- Priority loading for LCP

## Font Optimization

- `next/font` setup
- Google Fonts, local fonts
- Tailwind CSS integration
- Preloading subsets

## Bundling

- Server-incompatible packages
- CSS imports (not link tags)
- Polyfills (already included)
- ESM/CommonJS issues
- Bundle analysis

## Scripts

- `next/script` vs native script tags
- Inline scripts need `id`
- Loading strategies
- Google Analytics with `@next/third-parties`

## Hydration Errors

- Common causes (browser APIs, dates, invalid HTML)
- Debugging with error overlay
- Fixes for each cause

## Suspense Boundaries

- CSR bailout with `useSearchParams` and `usePathname`
- Which hooks require Suspense boundaries

## Parallel & Intercepting Routes

- Modal patterns with `@slot` and `(.)` interceptors
- `default.tsx` for fallbacks
- Closing modals correctly with `router.back()`

## Self-Hosting

- `output: 'standalone'` for Docker
- Cache handlers for multi-instance ISR
- What works vs needs extra setup

## Debug Tricks

- Rebuild specific routes with `--debug-build-paths`
