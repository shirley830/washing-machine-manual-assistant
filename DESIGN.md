# Interface Design System

## Direction

The interface is a restrained appliance product experience. It uses the pacing of a premium product page: a quiet brand bar, one short promise, real supported-machine photography, and then the task itself. It must not resemble a generic AI dashboard.

## Typography

- Navigation, controls, body copy, answers, and evidence use the native Apple system stack, resolving to SF Pro Text on Apple devices.
- The hero title and closing slogan use the same native stack with SF Pro Display as the preferred display face.
- The top wordmark, eyebrow, and hero title use regular weight; hierarchy comes from scale, colour, and spacing rather than bold text.
- Helvetica Neue and Arial provide metric-safe fallbacks on non-Apple platforms.
- Hero copy stays short and uses no more than two title lines on desktop.

## Colour

- Canvas: `#ffffff`
- Ink: `#092547`
- Action blue: `#165ee8`
- Accent cyan: `#55d7e8`
- Answer paper: `#ffffff`
- Secondary text: `#526e83`

Blue identifies the main action and key phrase. It is not used as a decorative background block.

## Layout

- Keep the logo and product name in a separate, quiet top bar.
- The hero is centred and spacious, with real supported machines below the title.
- Brand and exact-model selection remain visually paired.
- The question field is one continuous control rather than a collection of cards.
- Evidence follows the answer in normal reading order.

## Photography

Use only official product photography for models represented in the local manual catalogue. Preserve natural proportions and keep every machine on a shared baseline. Image sources are documented in `assets/machines/SOURCES.md`.

## Motion

- The hero copy and machines enter once with a short, staggered reveal.
- While answering, a rotating drum and scanning line communicate retrieval and evidence checking.
- All nonessential animation is disabled by `prefers-reduced-motion`.

## Responsive Behaviour

- Desktop keeps a wide product stage and two model selectors on one row.
- Mobile stacks the hero, preserves the machine lineup, and uses touch targets at least 44 px.
- The page must never scroll horizontally at 390 px.

## Avoid

- Dashboard card grids
- Decorative statistic tiles
- Floating badges and ornamental pills
- Gradient text
- Multiple competing accent colours
- Visible latency or estimated-cost metrics in the user answer
