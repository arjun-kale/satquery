# ADR-012: Mission-control visual system

## Decision

Use a dark-default, flat professional-GIS interface with functional colour
tokens, Inter for UI prose, and JetBrains Mono for measured data.

## Context

The screen is primarily evaluated by a remote-sensing panel under projector
lighting. A consumer SaaS visual language would compete with imagery and weaken
the instrument-panel credibility of the evidence trace.

## Options considered

- Dark mission-control/GIS system
- Generic light SaaS dashboard
- Glassmorphism/gradient marketing aesthetic

## Chosen approach and trade-offs

Cyan labels optical evidence; violet labels SAR; status hues remain semantic.
Scientific raster ramps are never recoloured. A light theme is out of scope.

## Future migration path

Accessibility review can introduce a verified high-contrast mode without
changing the semantic token contract.
