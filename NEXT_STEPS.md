# Remaining work after the CP3 refinement

The CP3 evaluation and interface changes are implemented and committed locally.
Simulation remains an accepted proof of concept, not a measured-fuel model.

## Before the next team demonstration

1. Push the local commits and merge the branch into main after team review.
2. Have another teammate run the project on their own computer. A clean local
   copy was tested here; an independent computer and dependency installation
   have not yet been tested.
3. Use the saved 200-pair/27-scenario evidence to prepare CP3's report/video once
   its required template and rubric are available. Keep CP2's 20-pair results
   clearly separate from CP3's 200 pairs and 5,400 repeated comparisons.

## K'von: interface and integration

- Review the current road-name/coordinate workflow with a teammate.
- Add map-click selection if it improves the demo; address search remains optional.
- Confirm map labels and route overlays are readable in the recorded video.
- Keep simulation warnings visible and handle unavailable data clearly.

## Bryce: model reasoning and sensitivity

- Review and explain why the simple direct calculation is currently preferable
  to ML: faster, no approximation error against this same synthetic formula.
- Review the two ML/direct disagreement cases and the worst off-nominal cases.
- Independently justify or revise the hypothetical vehicle assumptions. A more
  complicated learned model is not required merely to make the ML component
  appear useful. Measured-fuel calibration is optional future scope, not a
  prerequisite for presenting this accepted simulation proof of concept.

## Azalea: GIS plausibility

- Inspect the 60 steep directed edges identified in steep_roads_review.csv;
  some are reverse directions of the same physical road.
- Review the 146 posted-speed tags in posted_speed_review.csv. A legal limit
  is not a measured driving speed; document any new speed assumptions.
- Review important turn restrictions and possible elevation/road-shape errors.
  Automated checks establish consistency, not agreement with field conditions.

## Optional improvements after the core demo

Use fuller elevation profiles, model stops and acceleration, or compare with
independent vehicle measurements. These expand the simulation scope and require
new evidence and evaluation; they should not delay a clear account of current
results.
