---
name: "ui-ux-pro-max"
description: "Comprehensive UI/UX design guide with 50+ styles, 97 color palettes, 57 font pairings, and 99 UX guidelines. Invoke when user requests UI/UX work: design, build, create, implement, review, fix, or improve."
---

# UI/UX Pro Max - Design Intelligence

Comprehensive design guide for web and mobile applications. Contains 50+ styles, 97 color palettes, 57 font pairings, 99 UX guidelines, and 25 chart types across 9 technology stacks. Searchable database with priority-based recommendations.

## When to Apply

Reference these guidelines when:

- Designing new UI components or pages
- Choosing color palettes and typography
- Reviewing code for UX issues
- Building landing pages or dashboards
- Implementing accessibility requirements

## Rule Categories by Priority

| Priority | Category | Impact | Domain |
|----------|----------|--------|--------|
| 1 | Accessibility | CRITICAL | ux |
| 2 | Touch & Interaction | CRITICAL | ux |
| 3 | Performance | HIGH | ux |
| 4 | Layout & Responsive | HIGH | ux |
| 5 | Typography & Color | MEDIUM | typography, color |
| 6 | Animation | MEDIUM | ux |
| 7 | Style Selection | MEDIUM | style, product |
| 8 | Charts & Data | LOW | chart |

## Quick Reference

### 1. Accessibility (CRITICAL)

- `color-contrast` - Minimum 4.5:1 ratio for normal text
- `focus-states` - Visible focus rings on interactive elements
- `alt-text` - Descriptive alt text for meaningful images
- `aria-labels` - aria-label for icon-only buttons
- `keyboard-nav` - Tab order matches visual order
- `form-labels` - Use label with for attribute

### 2. Touch & Interaction (CRITICAL)

- `touch-target-size` - Minimum 44x44px touch targets
- `hover-vs-tap` - Use click/tap for primary interactions
- `loading-buttons` - Disable button during async operations
- `error-feedback` - Clear error messages near problem
- `cursor-pointer` - Add cursor-pointer to clickable elements

### 3. Performance (HIGH)

- `image-optimization` - Use WebP, srcset, lazy loading
- `reduced-motion` - Check prefers-reduced-motion
- `content-jumping` - Reserve space for async content

### 4. Layout & Responsive (HIGH)

- `viewport-meta` - width=device-width initial-scale=1
- `readable-font-size` - Minimum 16px body text on mobile
- `horizontal-scroll` - Ensure content fits viewport width
- `z-index-management` - Define z-index scale (10, 20, 30, 50)

### 5. Typography & Color (MEDIUM)

- `line-height` - Use 1.5-1.75 for body text
- `line-length` - Limit to 65-75 characters per line
- `font-pairing` - Match heading/body font personalities

### 6. Animation (MEDIUM)

- `duration-timing` - Use 150-300ms for micro-interactions
- `transform-performance` - Use transform/opacity, not width/height
- `loading-states` - Skeleton screens or spinners

### 7. Style Selection (MEDIUM)

- `style-match` - Match style to product type
- `consistency` - Use same style across all pages
- `no-emoji-icons` - Use SVG icons, not emojis

### 8. Charts & Data (LOW)

- `chart-type` - Match chart type to data type
- `color-guidance` - Use accessible color palettes
- `data-table` - Provide table alternative for accessibility

## Workflow

### Step 1: Analyze User Requirements

Extract key information from user request:

- **Product type**: SaaS, e-commerce, portfolio, dashboard, landing page, etc.
- **Style keywords**: minimal, playful, professional, elegant, dark mode, etc.
- **Industry**: healthcare, fintech, gaming, education, etc.
- **Stack**: React, Vue, Next.js, or default to `html-tailwind`

### Step 2: Generate Design System (REQUIRED)

Always start with design system to get comprehensive recommendations:

- **Pattern**: Choose appropriate UI pattern for product type
- **Style**: Match visual style (glassmorphism, minimalism, brutalism, etc.)
- **Colors**: Select accessible color palette
- **Typography**: Choose font pairing
- **Effects**: Determine visual effects (shadows, gradients, etc.)

### Step 3: Supplement with Detailed Searches (as needed)

Get additional details for specific domains:

| Domain | Use For | Example |
|--------|---------|---------|
| product | Product type recommendations | SaaS, e-commerce, portfolio |
| style | UI styles, colors, effects | glassmorphism, minimalism |
| typography | Font pairings | elegant, playful, professional |
| color | Color palettes by product type | saas, healthcare, beauty |
| landing | Page structure, CTA strategies | hero, testimonial, pricing |
| chart | Chart types, library recommendations | trend, comparison, timeline |
| ux | Best practices, anti-patterns | animation, accessibility |
| web | Web interface guidelines | aria, focus, keyboard |

### Step 4: Stack Guidelines

Get implementation-specific best practices. If user doesn't specify a stack, **default to `html-tailwind`**.

| Stack | Focus |
|-------|-------|
| html-tailwind | Tailwind utilities, responsive, a11y (DEFAULT) |
| react | State, hooks, performance, patterns |
| nextjs | SSR, routing, images, API routes |
| vue | Composition API, Pinia, Vue Router |
| svelte | Runes, stores, SvelteKit |
| swiftui | Views, State, Navigation, Animation |
| react-native | Components, Navigation, Lists |
| flutter | Widgets, State, Layout, Theming |
| shadcn | shadcn/ui components, theming, forms |
| jetpack-compose | Composables, Modifiers, State Hoisting |

## Common Rules for Professional UI

These are frequently overlooked issues that make UI look unprofessional:

### Icons & Visual Elements

| Rule | Do | Don't |
|------|-----|-------|
| **No emoji icons** | Use SVG icons (Heroicons, Lucide) | Use emojis like 🎨 🚀 ⚙️ as UI icons |
| **Stable hover states** | Use color/opacity transitions on hover | Use scale transforms that shift layout |
| **Correct brand logos** | Research official SVG from Simple Icons | Guess or use incorrect logo paths |
| **Consistent icon sizing** | Use fixed viewBox (24x24) with w-6 h-6 | Mix different icon sizes randomly |

### Interaction & Cursor

| Rule | Do | Don't |
|------|-----|-------|
| **Cursor pointer** | Add `cursor-pointer` to all clickable elements | Leave default cursor on interactive elements |
| **Hover feedback** | Provide visual feedback (color, shadow, border) | No indication element is interactive |
| **Smooth transitions** | Use `transition-colors duration-200` | Instant state changes or too slow (>500ms) |

### Light/Dark Mode Contrast

| Rule | Do | Don't |
|------|-----|-------|
| **Glass card light mode** | Use `bg-white/80` or higher opacity | Use `bg-white/10` (too transparent) |
| **Text contrast light** | Use `#0F172A` (slate-900) for text | Use `#94A3B8` (slate-400) for body text |
| **Muted text light** | Use `#475569` (slate-600) minimum | Use gray-400 or lighter |
| **Border visibility** | Use `border-gray-200` in light mode | Use `border-white/10` (invisible) |

### Layout & Spacing

| Rule | Do | Don't |
|------|-----|-------|
| **Floating navbar** | Add `top-4 left-4 right-4` spacing | Stick navbar to `top-0 left-0 right-0` |
| **Content padding** | Account for fixed navbar height | Let content hide behind fixed elements |
| **Consistent max-width** | Use same `max-w-6xl` or `max-w-7xl` | Mix different container widths |

## Pre-Delivery Checklist

Before delivering UI code, verify these items:

### Visual Quality
- No emojis used as icons (use SVG instead)
- All icons from consistent icon set (Heroicons/Lucide)
- Brand logos are correct (verified from Simple Icons)
- Hover states don't cause layout shift
- Use theme colors directly (bg-primary) not var() wrapper

### Interaction
- All clickable elements have `cursor-pointer`
- Hover states provide clear visual feedback
- Transitions are smooth (150-300ms)
- Focus states visible for keyboard navigation

### Light/Dark Mode
- Light mode text has sufficient contrast (4.5:1 minimum)
- Glass/transparent elements visible in light mode
- Borders visible in both modes
- Test both modes before delivery

### Layout
- Floating elements have proper spacing from edges
- No content hidden behind fixed navbars
- Responsive at 375px, 768px, 1024px, 1440px
- No horizontal scroll on mobile

### Accessibility
- All images have alt text
- Form inputs have labels
- Color is not the only indicator
- `prefers-reduced-motion` respected

## Tips for Better Results

1. **Be specific with keywords** - "healthcare SaaS dashboard" > "app"
2. **Search multiple times** - Different keywords reveal different insights
3. **Combine domains** - Style + Typography + Color = Complete design system
4. **Always check UX** - Search "animation", "z-index", "accessibility" for common issues
5. **Use stack flag** - Get implementation-specific best practices
6. **Iterate** - If first search doesn't match, try different keywords
