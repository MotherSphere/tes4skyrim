ScriptName TES4_ConfidenceFlee extends ActiveMagicEffect Hidden
{Effect of the TES4ConfidenceFlee ability. Each of its effects starts once the
owner's health falls to the line its TES4 Confidence (rank in
TES4ConfidenceFaction) sets and ends when the owner heals above it; either way
TES4Polyfill.ApplyConfidence re-reads rank and health and picks Cowardly or
Foolhardy. See docs/commentary/tes5_import_actors.md#confidence-tiers}

Faction Property TES4ConfidenceFaction Auto

Event OnEffectStart(Actor akTarget, Actor akCaster)
  TES4Polyfill.ApplyConfidence(akTarget, TES4ConfidenceFaction)
EndEvent

Event OnEffectFinish(Actor akTarget, Actor akCaster)
  TES4Polyfill.ApplyConfidence(akTarget, TES4ConfidenceFaction)
EndEvent
