ScriptName TESGameSelectTravelPlayer extends ReferenceAlias
{Threads of Prophecy — the travel quest's Player alias. Brings a loaded save's
travel state up to date (renumbered game ids, the game it began with).}

TESGameSelectTravel Property Travel Auto

Event OnPlayerLoadGame()
  Travel.Sync()
EndEvent
