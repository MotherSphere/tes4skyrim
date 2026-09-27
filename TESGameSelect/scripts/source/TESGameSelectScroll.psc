ScriptName TESGameSelectScroll extends ObjectReference
{Threads of Prophecy — the Elder Scroll. Reading it opens the travel menu.
Reading a book equips it, and vanilla ElderScrollScript hooks OnEquipped for
the player in exactly this way.}

TESGameSelectTravel Property Travel Auto

Event OnEquipped(Actor akActor)
  If akActor == Game.GetPlayer()
    Travel.Open()
  EndIf
EndEvent
