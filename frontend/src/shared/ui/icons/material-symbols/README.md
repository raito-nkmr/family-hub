# Material Symbols

These SVGs were selected in the [Material Symbols icon browser](https://fonts.google.com/icons) and are distributed
under the [Apache License 2.0](https://github.com/google/material-design-icons/blob/master/LICENSE).

Selection settings: outlined style, fill 0, weight 400, grade 0, optical size 24. The downloaded files were renamed by
semantic role, stripped of fixed dimensions, and changed from a fixed gray fill to `currentColor` for application themes.

Keep each UI symbol as an individual SVG in this directory, regardless of which feature currently uses it. Centralizing
icons keeps naming, theme behavior, accessibility, attribution, and reuse consistent as the application grows. Reserve
feature asset directories for logos, illustrations, and other non-icon SVGs owned exclusively by that feature.

Use Material Symbols for all UI icons. The Family Hub brand mark uses `family-group.svg`, while group navigation and
group content use `groups.svg`.

Pair prominent action buttons with a suitable icon by default to keep the interface visually consistent. Keep visible
text labels for labeled actions; an icon supplements the label rather than replacing it. Icon-only controls must retain
an accessible name through `aria-label`.
