# DCPlant Design Guide - Brite Theme

## Theme Overview
DCPlant uses the **Bootswatch Brite** theme - a vibrant, modern Bootstrap 5.3.7 theme with bold colors and clean aesthetics designed for contemporary web applications.

## Color Palette

### Primary Colors
- **Primary:** `#a2e436` (Bright Lime Green) - Main brand color for CTAs and key actions
- **Secondary:** `#ffffff` (White) - Secondary actions and clean backgrounds
- **Success:** `#68d391` (Soft Green) - Success states and positive actions
- **Info:** `#22d2ed` (Bright Cyan) - Informational elements
- **Warning:** `#ffc700` (Bright Yellow) - Warning states and alerts
- **Danger:** `#f56565` (Coral Red) - Errors and destructive actions
- **Light:** `#e9ecef` (Light Gray) - Subtle backgrounds
- **Dark:** `#000000` (Black) - High contrast elements

### Extended Palette
- **Blue:** `#61bcff` (Sky Blue)
- **Indigo:** `#828df9` (Soft Indigo)
- **Purple:** `#be82fa` (Lavender)
- **Pink:** `#ea4998` (Hot Pink)
- **Orange:** `#fa984a` (Tangerine)
- **Teal:** `#2ed3be` (Turquoise)
- **Cyan:** `#22d2ed` (Bright Cyan)
- **Green:** `#68d391` (Mint Green)
- **Red:** `#f56565` (Coral)
- **Yellow:** `#ffc700` (Golden)

### Gray Scale
- **Gray-100:** `#f8f9fa` (Lightest)
- **Gray-200:** `#e9ecef`
- **Gray-300:** `#dee2e6`
- **Gray-400:** `#ced4da`
- **Gray-500:** `#adb5bd`
- **Gray-600:** `#868e96`
- **Gray-700:** `#495057`
- **Gray-800:** `#343a40`
- **Gray-900:** `#212529` (Darkest)

## Typography

### Font Stack
```css
font-family: system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", 
             "Noto Sans", "Liberation Sans", Arial, sans-serif;
```

### Font Sizes
- **Base:** `0.875rem` (14px)
- **Small:** `0.765625rem` (12.25px)
- **Lead:** `1.09375rem` (17.5px)

### Headings
- **H1:** `2.1875rem` (35px) - Font-weight: 500
- **H2:** `1.75rem` (28px) - Font-weight: 500
- **H3:** `1.53125rem` (24.5px) - Font-weight: 500
- **H4:** `1.3125rem` (21px) - Font-weight: 500
- **H5:** `1.09375rem` (17.5px) - Font-weight: 500
- **H6:** `0.875rem` (14px) - Font-weight: 500

### Line Height
- **Default:** 1.5
- **Headings:** 1.2

## Spacing System

### Standard Spacing Scale
- **1:** `0.25rem` (4px)
- **2:** `0.5rem` (8px)
- **3:** `1rem` (16px)
- **4:** `1.5rem` (24px)
- **5:** `3rem` (48px)

### Gutter Widths
- **Default:** `1.5rem` (24px)
- **Small:** `0.25rem` to `0.5rem`
- **Large:** `3rem`

## Components

### Borders
- **Width:** `1px` standard, `2px` for emphasis
- **Color:** `#dee2e6` (light mode), `#495057` (dark mode)
- **Style:** Solid
- **Focus Ring:** `1px` width, `#000` color

### Border Radius
- **Small:** `0.25rem` (4px)
- **Default:** `0.375rem` (6px)
- **Large:** `0.5rem` (8px)
- **XL:** `1rem` (16px)
- **XXL:** `2rem` (32px)
- **Pill:** `50rem` (fully rounded)

### Forms
- **Border:** `2px solid` border
- **Padding:** `0.5rem 1rem` (default)
- **Focus:** Black border with 1px black box-shadow
- **Disabled:** Gray background (`#e9ecef`)

#### Form Sizes
- **Small:** `0.25rem 0.75rem` padding
- **Default:** `0.5rem 1rem` padding
- **Large:** `0.75rem 1.25rem` padding

### Buttons
- **Primary:** Lime green background (`#a2e436`) with black text
- **Secondary:** White background with black text
- **Border:** 2px solid
- **Padding:** Matches form control padding
- **Hover:** Slight darkening effect

### Tables
- **Border:** Black borders (1px)
- **Padding:** `0.75rem`
- **Striped:** 5% opacity of emphasis color
- **Hover:** Transparent hover effect

### Cards
- **Background:** White (light mode), `#2b3035` (dark mode)
- **Border:** 1px solid `#dee2e6`
- **Border Radius:** `0.375rem`
- **Padding:** Standard spacing scale

### Shadows
- **Small:** `0 0.125rem 0.25rem rgba(0, 0, 0, 0.075)`
- **Default:** `0 0.5rem 1rem rgba(0, 0, 0, 0.15)`
- **Large:** `0 1rem 3rem rgba(0, 0, 0, 0.175)`

## Dark Mode

### Dark Mode Colors
- **Body Background:** `#212529`
- **Body Text:** `#dee2e6`
- **Secondary Background:** `#343a40`
- **Tertiary Background:** `#2b3035`
- **Border Color:** `#495057`
- **Link Color:** `#c7ef86` (Light Lime)
- **Link Hover:** `#d2f29e`

### Dark Mode Adjustments
- Primary colors become lighter/brighter
- Backgrounds shift to dark grays
- Text becomes light gray/white
- Borders become darker gray

## Breakpoints

- **XS:** 0px (default)
- **SM:** 576px
- **MD:** 768px
- **LG:** 992px
- **XL:** 1200px
- **XXL:** 1400px

## Container Max Widths
- **SM:** 540px
- **MD:** 720px
- **LG:** 960px
- **XL:** 1140px
- **XXL:** 1320px

## Animation & Transitions

### Default Transition
```css
transition: all 0.15s ease-in-out;
```

### Supported Properties
- Border color
- Box shadow
- Background color
- Color

### Reduced Motion
Respects `prefers-reduced-motion` media query

## Special Features

### Focus States
- Black border (`#000`)
- 1px black box-shadow ring
- High contrast for accessibility

### Form Validation
- **Valid:** Green (`#68d391`) border and text
- **Invalid:** Red (`#f56565`) border and text

### Links
- **Default:** Black with underline
- **Hover:** Black with maintained underline
- **Dark Mode:** Light lime (`#c7ef86`)

## Implementation Notes

### CSS Variables
All colors and properties are available as CSS custom properties:
```css
--bs-primary: #a2e436;
--bs-body-font-size: 0.875rem;
--bs-border-radius: 0.375rem;
/* etc. */
```

### Utility Classes
- Use Bootstrap 5 utility classes for spacing, colors, and layout
- Brite theme overrides provide consistent styling
- Dark mode automatically adjusts via `data-bs-theme="dark"`

### Best Practices
1. Use semantic color names (primary, success, danger) rather than specific colors
2. Leverage CSS variables for consistency
3. Maintain 2px borders for form elements
4. Use the established spacing scale (1-5)
5. Ensure sufficient contrast for accessibility
6. Test both light and dark modes

## Component Examples

### Button
```html
<button class="btn btn-primary">Primary Action</button>
<button class="btn btn-outline-secondary">Secondary</button>
```

### Form Control
```html
<input type="text" class="form-control" placeholder="Enter text">
<select class="form-select">
  <option>Choose...</option>
</select>
```

### Card
```html
<div class="card">
  <div class="card-body">
    <h5 class="card-title">Card Title</h5>
    <p class="card-text">Content here</p>
  </div>
</div>
```

### Alert
```html
<div class="alert alert-success">Success message</div>
<div class="alert alert-warning">Warning message</div>
```

## Accessibility Guidelines

1. **Contrast Ratios:** Maintain WCAG AA compliance
2. **Focus Indicators:** Clear black focus rings
3. **Font Sizes:** Base 14px for readability
4. **Interactive Elements:** Minimum 44x44px touch targets
5. **Color Independence:** Don't rely solely on color for meaning

## File References
- **Base CSS:** `/static/css/bootstrap_brite.css`
- **Custom Overrides:** `/static/css/style.css`
- **Theme Switching:** Managed via `data-bs-theme` attribute

---

*Last Updated: August 2025*
*Theme: Bootswatch Brite v5.3.7*