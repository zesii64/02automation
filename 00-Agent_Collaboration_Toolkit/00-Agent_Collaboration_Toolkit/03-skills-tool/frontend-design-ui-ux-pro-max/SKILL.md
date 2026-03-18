---
name: frontend-design-ui-ux-pro-max
description: Generate production-grade, visually stunning HTML/CSS/JS pages with modern UI/UX design. Use when the user asks to create web pages, landing pages, dashboards, travel plans, portfolios, or any visual HTML output. Triggers on keywords like HTML, page, UI, frontend, design, website, landing page, dashboard, beautiful page.
---

# Frontend Design & UI-UX PRO MAX

When generating any HTML page, follow every principle below to produce a world-class, visually stunning result.

## Design System

### Color Palette

Always define a CSS custom properties system in `:root`. Never use raw hex values inline.

```css
:root {
  --primary: #...;
  --primary-light: #...;
  --primary-dark: #...;
  --accent: #...;
  --surface: #...;
  --surface-alt: #...;
  --text: #...;
  --text-light: #...;
  --shadow-sm: 0 2px 8px rgba(...);
  --shadow-md: 0 8px 32px rgba(...);
  --shadow-lg: 0 16px 48px rgba(...);
  --radius: 16px;
  --radius-sm: 10px;
  --transition: all 0.35s cubic-bezier(0.4, 0, 0.2, 1);
}
```

- Choose a cohesive palette of 2-3 primary colors + neutrals
- Ensure WCAG AA contrast (4.5:1 text, 3:1 large text)
- Use `linear-gradient` for visual depth on hero sections, badges, CTAs

### Typography

- Load Google Fonts: one display/serif + one body/sans-serif
- Use `clamp()` for fluid responsive font sizes: `font-size: clamp(min, preferred, max)`
- Establish clear hierarchy: hero > section title > card title > body > caption
- Line-height: 1.15 for headings, 1.6-1.8 for body text
- Letter-spacing: slight tracking (1-2px) on labels, badges, small caps

### Spacing & Layout

- Use 8px grid system (multiples of 8 for all padding/margins/gaps)
- Max content width: 1200-1320px centered with `margin: 0 auto`
- Section padding: 80px vertical (56px on mobile)
- Card padding: 20-28px
- Grid gaps: 16-32px

## Component Library

### Hero Section (required for full pages)

- Full viewport height (`100vh`, `min-height: 700px`)
- Background: high-quality image + gradient overlay + optional slow zoom animation
- Glassmorphism badge: `backdrop-filter: blur(12px); background: rgba(255,255,255,0.15)`
- Gradient text for emphasis: `background-clip: text; -webkit-text-fill-color: transparent`
- Stats bar or key metrics below headline
- Scroll-down hint with bounce animation

### Sticky Navigation

- `position: sticky; top: 0` with `backdrop-filter: blur(16px)`
- Pill-shaped nav links with hover/active states
- Horizontal scroll on mobile with hidden scrollbar
- Active section tracking via IntersectionObserver or scroll spy

### Cards

- White background, `border-radius: 16px`, shadow on rest, deeper shadow on hover
- Hover: `translateY(-4px to -6px)` lift effect
- Image area with `object-fit: cover` + zoom on hover (`scale(1.06-1.08)`)
- Overlay badges (top-left) and price tags (bottom-right) with `backdrop-filter`
- Clear visual hierarchy: tag → title → description → meta/CTA

### Section Structure

- Section tag/badge (small, colored pill, uppercase, letter-spacing)
- Section title (serif font, large, dark)
- Section description (lighter color, max-width 600px, centered)
- Content grid below

### Data Tables

- `border-collapse: separate` with rounded corners on wrapper
- Gradient header row
- Hover highlight on rows
- Special styling for total/summary rows

### Timeline / Itinerary

- Vertical line with gradient color
- Dot markers alternating colors
- Cards attached to timeline with tags/chips

### Links / Resources Grid

- Card with icon (colored square) + title + description + arrow
- Flex layout: icon | info | arrow(right-aligned)

### Image Gallery

- CSS Grid with `span` for featured items
- Overlay gradient from transparent to dark at bottom
- Title + subtitle on overlay
- Zoom on hover

## Interaction & Animation

### Scroll Reveal

Always add IntersectionObserver-based scroll reveal:

```js
const observer = new IntersectionObserver(entries => {
  entries.forEach(entry => {
    if (entry.isIntersecting) {
      entry.target.style.opacity = '1';
      entry.target.style.transform = 'translateY(0)';
    }
  });
}, { threshold: 0.08 });

document.querySelectorAll('.animate-on-scroll').forEach((el, i) => {
  el.style.opacity = '0';
  el.style.transform = 'translateY(30px)';
  el.style.transition = `opacity 0.6s ease ${i * 0.05}s, transform 0.6s ease ${i * 0.05}s`;
  observer.observe(el);
});
```

### Hover Effects

- Cards: lift + shadow deepen
- Images: scale 1.06-1.08
- Buttons: slight lift + background darken
- Links: color transition

### Transitions

- Default: `all 0.35s cubic-bezier(0.4, 0, 0.2, 1)` (Material ease)
- Images: `transform 0.5-0.6s ease`
- Use `transition` property, avoid `animation` for simple state changes

### Micro-interactions

- Pulse animation for status indicators (available/limited)
- Bounce animation for scroll hints
- Staggered reveal (increment delay per item)

## Responsive Design

### Breakpoints

```css
@media (max-width: 900px)  { /* tablet */ }
@media (max-width: 500px)  { /* mobile */ }
```

### Rules

- Grids collapse: 3-col → 2-col → 1-col
- Hero min-height reduces: 700px → 600px
- Section padding reduces: 80px → 56px
- Font sizes use `clamp()` so they auto-scale
- Navigation becomes horizontally scrollable
- Tables get `overflow-x: auto` wrapper
- Images maintain aspect ratio via `object-fit: cover`

## Image Strategy

### For Single-File HTML

Use Unsplash with parameters for quality/size:

```
https://images.unsplash.com/photo-{ID}?w={width}&q=80
```

- Hero: `w=1920&q=85`
- Cards: `w=600-800&q=80`
- Thumbnails: `w=400&q=75`
- Always set `alt` attributes
- Always use `loading="lazy"` except for hero

### Embedded Maps

Use Google Maps embed iframe for location-based content.

## Output Rules

1. **Single file**: everything in one `.html` file (inline CSS + JS)
2. **No external dependencies** except Google Fonts and Unsplash images
3. **Semantic HTML5**: `<section>`, `<nav>`, `<header>`, `<footer>`, `<article>`
4. **Smooth scroll**: `html { scroll-behavior: smooth; }`
5. **Reset**: `* { margin: 0; padding: 0; box-sizing: border-box; }`
6. **No emoji in code** unless user explicitly requests
7. **Chinese-friendly**: include `Noto Sans SC` / `Noto Serif SC` when content is Chinese
8. **Accessible**: proper contrast, alt text, focus states
9. **Performance**: lazy loading images, minimal JS, CSS-first animations

## Quality Checklist

Before delivering, verify:

- [ ] CSS variables defined in `:root`
- [ ] Google Fonts loaded
- [ ] Hero section is full-viewport with overlay + animation
- [ ] Sticky nav with scroll spy
- [ ] All cards have hover lift + shadow
- [ ] Scroll reveal animation on all content blocks
- [ ] Responsive at 900px and 500px breakpoints
- [ ] All images have alt text
- [ ] All external links open in `target="_blank"`
- [ ] Smooth scroll enabled
- [ ] Footer with attribution and date
