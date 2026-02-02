# Style Templates for Nano Banana Pro

Pre-built prompt patterns for common image generation use cases.

## UI/Web Styles

### Hero Banner (16:9, 1920x1080)

```
Create a hero banner for [TOPIC].

Format: hero banner
Aspect: 16:9
Size: 2K
Safe margins: 6% on all sides

Layout:
- Large bold headline on the left (40% width)
- Supporting visual on the right (50% width)
- Subtle gradient or solid background

Typography:
- Headline: Bold sans-serif, high contrast
- Subhead: Regular weight, smaller size

Text to render verbatim:
"""
[HEADLINE TEXT]
[SUBHEAD TEXT]
"""

Style: Clean, professional, modern, minimal clutter
```

### Social Media Card (1:1, 1200x1200)

```
Create a social media post card for [TOPIC].

Format: square social card
Aspect: 1:1
Size: 2K
Safe margins: 8% on all sides

Layout:
- Centered composition
- Main visual or icon in center
- Text overlaid or below

Typography:
- Primary text: Bold, readable at thumbnail size
- Secondary text: Smaller, lighter weight

Text to render verbatim:
"""
[PRIMARY TEXT]
[SECONDARY TEXT]
"""

Style: Eye-catching, scroll-stopping, brand-aligned
```

### App Screenshot (9:16, 1080x1920)

```
Create a mobile app screenshot for [FEATURE].

Format: mobile screenshot
Aspect: 9:16
Size: 2K
Safe margins: 5% on all sides

Layout:
- Status bar area at top (leave space)
- Main content in center
- Navigation area at bottom (leave space)

Elements:
- Clean UI components
- Realistic touch targets
- Proper visual hierarchy

Style: Modern mobile design, iOS/Android conventions
```

### Landing Page Section (4:3, 1600x1200)

```
Create a landing page section for [FEATURE/PRODUCT].

Format: landing page section
Aspect: 4:3
Size: 2K
Safe margins: 8% on all sides

Layout:
- Feature visual on one side (60%)
- Text content on the other (40%)
- Clear visual flow

Typography:
- Section headline: Bold, attention-grabbing
- Body text: Clean, readable
- CTA button: Prominent, actionable

Style: Conversion-focused, professional, trustworthy
```

### Icon Set (1:1, 512x512)

```
Create an icon for [CONCEPT].

Format: app icon or UI icon
Aspect: 1:1
Size: 1K (or 2K for retina)

Design:
- Simple, recognizable silhouette
- Works at small sizes (16px-512px)
- Clear meaning without text

Style options:
- Flat design (solid colors, no gradients)
- Outlined (stroke-based, minimal fill)
- Filled (solid shapes, consistent weight)
- Glyph (single color, symbolic)

Color palette: [SPECIFY COLORS OR "monochrome"]
```

## Marketing/Brand Styles

### Product Photography (4:3)

```
Create a product shot for [PRODUCT NAME].

Format: product photography
Aspect: 4:3
Size: 2K

Composition:
- Product centered or rule-of-thirds
- Clean background (white, gradient, or contextual)
- Soft shadows for depth

Lighting:
- Key light from upper left
- Fill light to reduce harsh shadows
- Rim light for product separation

Style: Professional, aspirational, purchase-inspiring
```

### Ad Creative (Various Aspects)

```
Create an advertisement for [PRODUCT/SERVICE].

Format: display ad
Aspect: [16:9 for banner / 1:1 for feed / 9:16 for stories]
Size: 2K

Layout:
- Eye-catching visual (60%)
- Clear value proposition (30%)
- CTA button or text (10%)

Typography:
- Headline: Bold, benefits-focused
- Body: Concise, action-oriented
- CTA: Contrasting, clickable

Text to render verbatim:
"""
[HEADLINE]
[BODY TEXT]
[CTA TEXT]
"""

Style: Attention-grabbing, brand-consistent, conversion-focused
```

### Logo Variations

```
Create a logo for [BRAND NAME].

Format: logo design
Aspect: 1:1 (or 2:1 for horizontal)
Size: 2K

Versions to consider:
- Full logo (icon + wordmark)
- Icon only (for small spaces)
- Wordmark only (for large applications)

Design principles:
- Simple, memorable, scalable
- Works in single color
- Distinct from competitors

Color palette: [PRIMARY] [SECONDARY] [ACCENT]
Font style: [SERIF/SANS-SERIF/SCRIPT/CUSTOM]
```

### Brand Asset

```
Create a branded [ASSET TYPE] for [BRAND NAME].

Format: [business card / letterhead / email header / etc.]
Aspect: [APPROPRIATE ASPECT]
Size: 2K

Brand elements:
- Logo placement: [TOP LEFT / CENTER / etc.]
- Primary color: [HEX CODE]
- Secondary color: [HEX CODE]
- Font family: [FONT NAME]

Style: Consistent with brand guidelines, professional, cohesive
```

## Artistic Styles

### Illustration (Flat Design)

```
Create an illustration of [SUBJECT].

Format: flat design illustration
Aspect: [ASPECT]
Size: 2K

Style characteristics:
- Solid colors, no gradients
- Simple geometric shapes
- Limited color palette (3-5 colors)
- No realistic shading or textures
- Vector-like, clean edges

Color palette: [COLORS]
Mood: [PLAYFUL / PROFESSIONAL / WHIMSICAL / etc.]
```

### Abstract Art

```
Create an abstract artwork inspired by [CONCEPT/EMOTION].

Format: abstract art
Aspect: [ASPECT]
Size: 2K

Style options:
- Geometric: Precise shapes, patterns, symmetry
- Fluid: Organic forms, flowing lines, gradients
- Textured: Layered effects, depth, tactile feel
- Minimal: Negative space, few elements, high impact

Color palette: [HARMONIOUS / COMPLEMENTARY / MONOCHROME / BOLD]
Mood: [CALM / ENERGETIC / MYSTERIOUS / etc.]
```

### Photo-Realistic

```
Create a photo-realistic image of [SUBJECT].

Format: photographic
Aspect: [ASPECT]
Size: 4K (recommended for detail)

Technical specifications:
- Camera angle: [EYE LEVEL / LOW / HIGH / OVERHEAD]
- Lens feel: [WIDE / NORMAL / TELEPHOTO / MACRO]
- Depth of field: [SHALLOW (bokeh) / DEEP (all in focus)]
- Lighting: [NATURAL / STUDIO / DRAMATIC / SOFT]

Environment: [INDOOR / OUTDOOR / STUDIO / ABSTRACT]
Time of day: [MORNING / NOON / GOLDEN HOUR / NIGHT]
Weather/atmosphere: [CLEAR / CLOUDY / FOGGY / etc.]
```

### Minimalist

```
Create a minimalist design for [SUBJECT/CONCEPT].

Format: minimalist
Aspect: [ASPECT]
Size: 2K

Principles:
- Maximum negative space (60%+ empty)
- Limited elements (1-3 focal points)
- Restricted color palette (1-3 colors)
- Clean typography (if text included)
- No decorative elements

Color approach: [MONOCHROME / DUOTONE / ACCENT COLOR ON NEUTRAL]
Grid: [CENTERED / ASYMMETRIC / RULE OF THIRDS]
```

### Retro/Vintage

```
Create a retro-style image for [SUBJECT].

Format: vintage/retro
Aspect: [ASPECT]
Size: 2K

Era to reference:
- 1950s: Mid-century modern, atomic age, pastel colors
- 1960s: Pop art, psychedelic, bold patterns
- 1970s: Earth tones, disco, groovy typography
- 1980s: Neon, synthwave, geometric patterns
- 1990s: Grunge, pixelated, early digital

Techniques:
- Color grading: Faded, warm tones, limited palette
- Textures: Grain, halftone dots, paper texture
- Typography: Period-appropriate fonts
- Effects: Light leaks, vignette, scratches (subtle)

Specific era: [DECADE]
Mood: [NOSTALGIC / PLAYFUL / AUTHENTIC / STYLIZED]
```

## Template Usage Tips

1. **Copy and customize** - Use these as starting points, not rigid rules
2. **Be specific about text** - Always include exact text in a literal block
3. **Specify colors** - Use hex codes when you have brand colors
4. **Match aspect to use case** - Social media has specific requirements
5. **Iterate with edit mode** - Generate first, then refine with specific changes
