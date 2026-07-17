# Finance dashboard design audit

## Scope

Reviewed all Acuity pages (Executive Summary, Revenue & Contracts, Renewals & Retention, Sales Performance, Financial Performance, Historical Trends) and both MarketReader pages (Billing Overview and Historical Trends). The audit covered the shared shell, navigation, KPI cards, comparisons, charts, tables, and loading, error, and empty states.

## Findings and changes

| Severity | Issue found | Change made |
| --- | --- | --- |
| High | Placeholder diamond mark could be mistaken for an approved logo. | Replaced it with the supplied white-and-orange Acuity logo on the Steel Grey sidebar, preserving its aspect ratio. |
| High | Entity and reporting context were separated and easy to miss. | Grouped entity/reporting controls and added a persistent context line showing the selected entity, live reporting state, and completed comparison period. |
| High | Previous navy/teal/red styling did not match the supplied brand palette. | Centralized Steel Grey, Alert Orange, neutral, surface, and semantic comparison colours in `src/dashboard_theme.py`. |
| Medium | Navigation, filters, refresh, and snapshot capture competed visually. | Added explicit sidebar sections and moved snapshot capture into a secondary administration disclosure. Capture logic is unchanged. |
| Medium | Page width and card styling were oversized at common laptop widths. | Reduced the content maximum width, flattened radius/shadows, standardized card padding/heights, and added a narrow-laptop breakpoint. |
| Medium | Typography and hierarchy were inconsistent. | Added a restrained editorial display stack for major headings and a single sans-serif UI stack for figures, labels, controls, and body copy. |
| Medium | Chart colours used framework defaults. | Added a shared Altair theme with Steel Grey as the primary series and Alert Orange as the principal highlight, plus quieter axes and gridlines. |
| Low | Small muted text risked insufficient contrast. | Darkened secondary text to `#5F5F5B`/`#767676` on light surfaces and reserved lighter text for the dark sidebar. |
| Low | Comparison meaning relied too heavily on colour. | Retained arrows, signed values, units, and baseline labels alongside positive, negative, and neutral colours. |

## Components redesigned

- Application background and constrained content canvas
- Sidebar hierarchy, entity controls, navigation, and data controls
- Reporting context strip
- Standard Streamlit metric cards and month-on-month comparison cards
- Page headings, section headings, supporting copy, tables, alerts, and chart theme
- Desktop and narrow-laptop spacing and typography

## Accessibility considerations

- Financial movement retains arrows and signed text, so colour is not the sole signal.
- Positive (`#247A5A`) and negative (`#B33A3A`) states are distinct from Alert Orange and provide strong contrast on white.
- Small secondary text uses darker greys than the supplied Neutral Grey where needed for practical WCAG AA contrast.
- Values use tabular numerals and consistent unit formatting.
- Controls retain native Streamlit semantics and keyboard behaviour.
- The layout avoids horizontal page scrolling at common laptop widths; wide data tables retain their own bounded scrolling where necessary.

## Remaining recommendations

1. Supply properly licensed webfont files if exact Soleil rendering is required. The dashboard currently uses the approved fallback stack.
2. Supply or approve a DM Serif Text webfont asset if guaranteed cross-device rendering is required. The CSS requests the font but falls back to Georgia when it is unavailable.
3. Consider a separate future accessibility review with automated contrast and keyboard testing in the deployed Railway environment.

## Screenshots

Before and after screenshots were captured during local browser verification. They are retained in the delivery task rather than committed because the brief did not include an approved repository location or retention policy for live financial-data images.
