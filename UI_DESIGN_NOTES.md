# EcoRoute visual design research

The planner borrows interaction patterns from established routing tools while
keeping EcoRoute's actual scope and simulated-data limits visible.

| Reference | Pattern applied in EcoRoute |
|---|---|
| [Google Maps directions](https://support.google.com/maps/answer/144339?co=GENIE.Platform%3DDesktop&hl=en) and [eco routes](https://support.google.com/maps/answer/11470237?hl=en) | Distinct route alternatives, colored highlights, compact distance/fuel cards, and a clear efficiency tradeoff. |
| [MapQuest directions](https://help.mapquest.com/hc/en-us/articles/205362134-How-to-get-directions) | A compact starting/ending-location panel beside a dominant map. |
| [Komoot website planner](https://support.komoot.com/hc/en-us/articles/10194270667034-Plan-routes-on-the-website) | A map-centered workspace with an elevation profile to help explain the route. |

These are design interpretations, not copied branding, screenshots, or claims
of equivalent navigation functionality. EcoRoute does not add live traffic,
arrival-time predictions, or measured fuel accuracy.

## Implemented

- A two-column trip-panel/map layout, with responsive native Streamlit columns.
- A light neutral theme, teal actions, rounded controls, and bordered cards.
- A larger map with the existing road names, opacity controls, A/B markers,
  route-visibility choices, and fit control preserved.
- Two colored result cards showing actual computed distance and simulated fuel.
- A one-click prepared Fairview demo using real graph node IDs.
- A small elevation plot derived from saved node heights and actual edge lengths.
  Lines connect road-end samples; this is not a continuous measured road profile.
- Separate planner, evidence, and data workspaces, with trip inputs preserved
  while switching between them. Technical details remain expandable.

Native Streamlit layout and theme settings are used; there is no injected CSS,
copied product imagery, new map API key, or fabricated route result.
