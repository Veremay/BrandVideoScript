---
name: Frozen Sunlight
colors:
  surface: '#faf8ff'
  surface-dim: '#d2d9f4'
  surface-bright: '#faf8ff'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f2f3ff'
  surface-container: '#eaedff'
  surface-container-high: '#e2e7ff'
  surface-container-highest: '#dae2fd'
  on-surface: '#131b2e'
  on-surface-variant: '#3e4850'
  inverse-surface: '#283044'
  inverse-on-surface: '#eef0ff'
  outline: '#6e7881'
  outline-variant: '#bec8d2'
  surface-tint: '#006591'
  primary: '#006591'
  on-primary: '#ffffff'
  primary-container: '#0ea5e9'
  on-primary-container: '#003751'
  inverse-primary: '#89ceff'
  secondary: '#006686'
  on-secondary: '#ffffff'
  secondary-container: '#7ed4fd'
  on-secondary-container: '#005b78'
  tertiary: '#576065'
  on-tertiary: '#ffffff'
  tertiary-container: '#949da3'
  on-tertiary-container: '#2c3539'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#c9e6ff'
  primary-fixed-dim: '#89ceff'
  on-primary-fixed: '#001e2f'
  on-primary-fixed-variant: '#004c6e'
  secondary-fixed: '#c0e8ff'
  secondary-fixed-dim: '#7bd1fa'
  on-secondary-fixed: '#001e2b'
  on-secondary-fixed-variant: '#004d66'
  tertiary-fixed: '#dbe4ea'
  tertiary-fixed-dim: '#bfc8ce'
  on-tertiary-fixed: '#141d21'
  on-tertiary-fixed-variant: '#3f484d'
  background: '#faf8ff'
  on-background: '#131b2e'
  surface-variant: '#dae2fd'
typography:
  display-lg:
    fontFamily: Hanken Grotesk
    fontSize: 56px
    fontWeight: '700'
    lineHeight: 64px
    letterSpacing: -0.02em
  display-lg-mobile:
    fontFamily: Hanken Grotesk
    fontSize: 40px
    fontWeight: '700'
    lineHeight: 48px
    letterSpacing: -0.02em
  headline-md:
    fontFamily: Hanken Grotesk
    fontSize: 32px
    fontWeight: '600'
    lineHeight: 40px
    letterSpacing: -0.01em
  headline-md-mobile:
    fontFamily: Hanken Grotesk
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
    letterSpacing: -0.01em
  body-lg:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '400'
    lineHeight: 28px
  body-md:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  body-sm:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  label-code:
    fontFamily: JetBrains Mono
    fontSize: 13px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: 0.05em
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  base: 8px
  xs: 4px
  sm: 12px
  md: 24px
  lg: 48px
  xl: 80px
  gutter: 24px
  margin-mobile: 16px
  margin-desktop: 64px
---

## Brand & Style

The design system embodies the crystalline clarity of an arctic morning. It targets professional environments that require a sense of calm, precision, and high-end technical sophistication. The emotional response is one of "focused serenity"—a space that feels expansive and breathable yet structurally rigorous.

The visual style is a refined **Glassmorphism** evolution tailored for light environments. It utilizes translucent white panes, subtle refraction, and high-frequency blurs to create depth without the heavy shadows of traditional skeuomorphism. This is balanced with **Minimalist** layouts to ensure the ethereal effects do not compromise functional clarity or professional utility.

## Colors

The palette transitions from the deep shadows of polar nights to the blinding clarity of midday snow.

- **Primary (#0ea5e9):** A deepened "Solar Sky" blue used for high-importance actions and interactive states to ensure accessibility against light surfaces.
- **Secondary (#7dd3fc):** The legacy "Ice Blue," now utilized primarily for decorative accents, progress indicators, and soft highlights.
- **Tertiary (#f0f9ff):** "Glacial Wash," the base for translucent layers and subtle component backgrounds.
- **Neutral (#0f172a):** "Obsidian Ice," a high-contrast dark navy used for primary typography and iconography to ensure maximum legibility.
- **Background:** Pure white (#FFFFFF) serves as the base canvas to maximize the "Sunlight" effect.

## Typography

Typography focuses on high-contrast legibility and technical precision. **Hanken Grotesk** provides a sharp, contemporary feel for large displays, while **Inter** ensures workhorse reliability for dense data and body text. **JetBrains Mono** is used sparingly for labels and metadata to reinforce the system's "engineered" aesthetic. All headings use a tighter letter-spacing to maintain a compact, premium feel on light backgrounds.

## Layout & Spacing

The system employs a **Fluid Grid** model built on an 8px base unit. 

- **Desktop:** 12-column grid with a maximum content width of 1440px. 64px outside margins provide "breathing room" to enhance the airy aesthetic.
- **Tablet:** 8-column grid with 32px margins.
- **Mobile:** 4-column grid with 16px margins.

Spacing is used to create "visual silences." Large components are separated by `lg` or `xl` units to prevent the light UI from feeling cluttered. Elements within components use `xs` and `sm` for tight, logical grouping.

## Elevation & Depth

Depth in this design system is achieved through **Luminous Stacking** rather than traditional heavy shadows.

1.  **Base Layer:** Pure White (#FFFFFF).
2.  **Glass Layer:** Semi-transparent white (#FFFFFF at 60% opacity) with a 20px Backdrop Blur and a 1px solid white border at 40% opacity to simulate light catching the edge of a crystal.
3.  **Floating Elements:** For dropdowns and modals, use a "Sunlit Shadow"—an extremely diffused, large-radius shadow using the Primary Sky color at 8% opacity (e.g., `0px 20px 40px rgba(14, 165, 233, 0.08)`).
4.  **Inclusion:** Elements do not "sit" on the page; they float within it, separated by varying intensities of blur and white-on-white borders.

## Shapes

The shape language is "Soft Geometric." The `0.5rem` base roundedness provides a friendly, approachable feel that counteracts the coldness of the blue palette. 

- **Standard Buttons & Inputs:** 0.5rem (Rounded).
- **Cards & Panes:** 1rem (Rounded-LG).
- **Tooltips & Small Badges:** 0.25rem (Soft).

This consistency ensures that even with complex glass effects, the structural integrity of the UI remains predictable and professional.

## Components

- **Buttons:** Primary buttons use a solid `#0ea5e9` fill with white text. Secondary buttons use the "Glass Layer" style: a semi-transparent white background with a thin `#0ea5e9` border and text.
- **Input Fields:** Use a subtle `tertiary_color_hex` (#f0f9ff) background with a 1px border. On focus, the border becomes the primary blue with a soft "glow" (4px blur shadow).
- **Cards:** Defined by a 1px white border (40% opacity) and a 20px backdrop blur. Background is white at 70% opacity. 
- **Chips:** Highly rounded (Pill-shaped) with a very light blue background and dark navy text. Use for status or tags.
- **Glass Panes:** Large container components used to group content. They should always have a `backdrop-filter: blur(20px)` to maintain the "Frozen Sunlight" aesthetic as the user scrolls content underneath.
- **Lists:** Separated by 1px "Ice Lines" (#f0f9ff) rather than heavy borders or shadows.
