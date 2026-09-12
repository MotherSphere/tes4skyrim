Issue Title: Creature Behavior Graph (converter issue/potential solution)

Converter Version:  0.629

ESM: Oblivion.esm/All

Details:
This is the result after trying (and failing) to rebuild the Idle Animations tree in the CK (that vanilla creatures all have). The behavior conversion in the end became the roadblock that I can't work around (unless I rebuild the graph for everyone). 🧐 These details came after comparing the vanilla draugr behavior file to the base minotaur behavior file after conversion. The standard behavior conversion/generation may have implications down the line, so figured I'd post it here. 

| Converted Minotaur behavior issue                                                     | Technical detail / required converter adjustment                                                                                                                                                                                                                                                                                                                                      |
| ------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Attack state machines have no neutral/readied starting state**                      | `Attack_H2H_SM` and `Attack_TwoH_SM` start directly on an actual attack animation. The converter should generate attack machinery that can remain active without automatically playing an attack.                                                                                                                                                                                     |
| **State 0 is Back Power**                                                             | H2H state 0 is `h2hattackbackpower`; TwoH state 0 is `twohandattackbackpower`. Because these are also the machines' default starting states, activating an attack machine inherently starts a Back Power attack.                                                                                                                                                                      |
| **Attack selection occurs too late in the hierarchy**                                 | TES4 attack events correctly map to individual attack states, but the appropriate nested attack machine must first be activated. On initial activation, its default attack state can become active before the requested attack event selects the intended state.                                                                                                                      |
| **Initial attack event is effectively lost across nested-machine activation**         | From the root/default portion of the graph, TES4 attack events transition into `AttackStanceState`. That activates `AttackStanceSelector`, which then activates the H2H/TwoH attack machine. The original event does not reliably carry through this activation sequence to select the requested nested attack state.                                                                 |
| **Attack events work once the machine is already active**                             | The nested attack machines' wildcard transitions correctly map TES4 attack events to the intended states. This demonstrates that the individual event mappings and attack animations are fundamentally correct; the defect is in initial activation/state-machine topology.                                                                                                           |
| **Changing `startStateId` cannot correctly solve the problem**                        | Changing the default from Back Power to another attack merely changes which attack automatically executes when the machine activates. The default needs to be a non-attacking/readied state, or initial event selection must occur before an attack generator becomes active.                                                                                                         |
| **`AttackStanceSelector` correctly selects weapon family**                            | Its `startStateId` is bound to `iRightHandType`, so H2H versus TwoH selection is already functioning. This portion should not be replaced merely to address the first-attack problem.                                                                                                                                                                                                 |
| **TwoH attack machinery is duplicated**                                               | The converted graph contains nine instances of `Attack_TwoH_SM`. The converter author should examine why identical TwoH attack state machines are generated repeatedly and whether this duplication contributes to activation/routing complexity.                                                                                                                                     |
| **Converted attack topology differs materially from Skyrim weapon-creature topology** | Skyrim's Draugr behavior keeps weapon/readied combat machinery active and transitions from a non-attacking/readied state into individual attacks. The converter instead enters an attack-specific machine whose default state is already an attack.                                                                                                                                   |
| **Recommended converter-level correction**                                            | Generate a persistent/non-attacking attack-ready state or equivalent topology so that the appropriate H2H/TwoH machinery is active **before** an attack-selection event is processed. An attack event should transition from a neutral/readied state to the requested attack, rather than activate a machine that immediately defaults to an arbitrary attack.                        |
| **Preserve existing TES4 event mappings**                                             | The mappings themselves have been verified: e.g. TwoH Back Power→state 0, Forward Power→1, Left→2, Left Power→3, Power→4, Right→5, Right Power→6. The problem is not that Left/Right events point at Back Power.                                                                                                                                                                      |
| **Separate converted StandingIdle issue**                                             | `StandingIdle` was generated with `syncVariableIndex=-1` and default start state 0 even though its states represent NonCombatIdle/CombatIdle and `iCombatStance` exists. It should synchronize its initial state to `iCombatStance` (variable index 10). Changing `syncVariableIndex` to 10 and start mode from DEFAULT to SYNC corrected combat idle restoration in runtime testing. |

--------------------------------------------------------

Issue Title: Creature Floating Idles

Converter Version:  0.632

ESM: FalloutNV.esm

Details: Creature mtidle.kf have high Z values, here's what fixes it. I can send you the mtidle corrections pack if it helps. 

| File                                   | Original `NPC Root [Root]` Z | Corrected Z |
| -------------------------------------- | ---------------------------: | ----------: |
| `libertyprime/animations/mtidle.hkx`   |                   378.490112 |           0 |
| `deathclaw/animations/mtidle.hkx`      |                   105.234467 |           0 |
| `centaur/animations/mtidle.hkx`        |                    19.450924 |           0 |
| `sentrybot/animations/mtidle.hkx`      |                    72.000000 |           0 |
| `nvvoid/animations/mtidle.hkx`         |                     6.170398 |           0 |
| `mirelurkking/animations/mtidle.hkx`   |                    65.513680 |           0 |
| `smbonecrusher/animations/mtidle.hkx`  |                    88.129883 |           0 |
| `ghoul/animations/mtidle.hkx`          |                    71.739166 |           0 |
| `dog/animations/mtidle.hkx`            |                     0.240689 |           0 |
| `nvtumbleweed/animations/mtidle.hkx`   |                    95.126343 |           0 |
| `mirelurk/animations/mtidle.hkx`       |                    74.003349 |           0 |
| `smbehemoth/animations/mtidle.hkx`     |                   111.749084 |           0 |
| `smspinebreaker/animations/mtidle.hkx` |                    88.129883 |           0 |

--------------------------------------------------------

Issue Title: No Creature iCombatStance State

Converter Version:  0.629

ESM: Any

Details: Converted creatures are not retaining/reaching iCombatStance. Here's a fix for the combat state and combat idle not being restored after an animation for creatures (posting for reference).

idle
Bip01 NonAccum heading 54.17° → 0°
NPC Root Z 85.17 → 0
walkforward
playback 47 → 24 frames
duration 1.533s → 0.767s
cast animations
Bip01 NonAccum heading 90.06° → 0°
attack animations
Bip01 NonAccum heading 54.17° → 0°
equip / unequip
Bip01 NonAccum heading 54.17° → 0°
awarevocal
Bip01 NonAccum heading 54.17° → 0°
stagger
Bip01 NonAccum heading 67.10° → 0°
turn left / right
Bip01 NonAccum heading 54.17° → 0°
death
Bip01 NonAccum heading 54.17° → 0°
ragdollpose
Bip01 NonAccum heading 54.17° → 0°

Here's the ash vampire fix. No more floating, no more strafing at end of walk animation lol 

--------------------------------------------------------

handtohandattackleft.hkx     Bip01 NonAccum = 0.000°
handtohandattackright.hkx    Bip01 NonAccum = 0.000°
casttarget_In.hkx            Bip01 NonAccum = 0.000°
casttarget_Loop.hkx          Bip01 NonAccum = 0.000°
casttarget_Out.hkx           Bip01 NonAccum = 0.000°
handtohandidle.hkx           Bip01 NonAccum = 0.000°

Here are the patched animation files and issue. Ash Zombie, Ash Ghoul, Ash Slave, Ascended Sleeper. Just animatio

--------------------------------------------------------

Issue Title: Scamp - Missing Spell Animations

Converter Version:  0.628

ESM: Oblivion.esm

Details: Scamps don't have their fire-and-forget spell animation. No firebolts for them.

--------------------------------------------------------

Issue Title: No Creature Get Up Animations

Converter Version:  0.629

ESM: Oblivion.esm

Details: Creatures are missing their "getup" animation. After ragdolling, they stay down.

--------------------------------------------------------

Issue Title: No Creature Magicka Regen

Converter Version:  0.629

ESM: Any

Details: Magicka Regen data value is 0.00 for converted creatures, effectively disabling their magicka regeneration.

--------------------------------------------------------

Full list of FNV animation fixes (idle floating, attack floating, Supermutant/Nightkin rotating during attacks, etc.).

Fallout New Vegas -> Skyrim Converted Creature Animation Corrections

Purpose

This record documents the animation-level corrections made after in-game
testing of the converted Fallout: New Vegas creature batch.

1. Vertical placement / floating

Affected non-locomotion animations contained an erroneous static Z
offset on animation track 0, NPC Root [Root]. The affected static Z
component was normalized to 0.0.

Bip01 NonAccum Z was deliberately preserved. Earlier testing that zeroed
NonAccum Z buried the creature, demonstrating that its vertical
placement is legitimate.

Locomotion/root-motion clips were not blanket-normalized.

Z-corrected HKX files: 226

-   alien/animations/1hmattackleft.hkx — NPC Root [Root] static Z
    normalized to 0.0.
-   alien/animations/1hmattackright.hkx — NPC Root [Root] static Z
    normalized to 0.0.
-   alien/animations/1hmattackrightchop.hkx — NPC Root [Root] static Z
    normalized to 0.0.
-   alien/animations/1hmattackrightpoke.hkx — NPC Root [Root] static Z
    normalized to 0.0.
-   alien/animations/2hrattack4.hkx — NPC Root [Root] static Z
    normalized to 0.0.
-   alien/animations/2hrattack4is.hkx — NPC Root [Root] static Z
    normalized to 0.0.
-   alien/animations/2hrattackleft.hkx — NPC Root [Root] static Z
    normalized to 0.0.
-   alien/animations/2hrattackright.hkx — NPC Root [Root] static Z
    normalized to 0.0.
-   alien/animations/h2hattackleft.hkx — NPC Root [Root] static Z
    normalized to 0.0.
-   alien/animations/h2hattackright.hkx — NPC Root [Root] static Z
    normalized to 0.0.
-   alien/animations/sneak2hrattack4.hkx — NPC Root [Root] static Z
    normalized to 0.0.
-   alien/animations/sneak2hrattack4up.hkx — NPC Root [Root] static Z
    normalized to 0.0.
-   centaur/animations/2hlattackleft.hkx — NPC Root [Root] static Z
    normalized to 0.0.
-   centaur/animations/h2hattackleft.hkx — NPC Root [Root] static Z
    normalized to 0.0.
-   centaur/animations/h2hattackright.hkx — NPC Root [Root] static Z
    normalized to 0.0.
-   centaur/animations/mtidle.hkx — NPC Root [Root] static Z normalized
    to 0.0.
-   centaur/animations/mtturnleft.hkx — NPC Root [Root] static Z
    normalized to 0.0.
-   centaur/animations/mtturnright.hkx — NPC Root [Root] static Z
    normalized to 0.0.
-   centaur/animations/ragdollpose.hkx — NPC Root [Root] static Z
    normalized to 0.0.
-   deathclaw/animations/h2hattacklefta.hkx — NPC Root [Root] static Z
    normalized to 0.0.
-   deathclaw/animations/h2hattackleftb.hkx — NPC Root [Root] static Z
    normalized to 0.0.
-   deathclaw/animations/h2hattackleftpower.hkx — NPC Root [Root] static
    Z normalized to 0.0.
-   deathclaw/animations/h2hattackrighta.hkx — NPC Root [Root] static Z
    normalized to 0.0.
-   deathclaw/animations/h2hattackrightb.hkx — NPC Root [Root] static Z
    normalized to 0.0.
-   deathclaw/animations/h2hattackrightpower.hkx — NPC Root [Root]
    static Z normalized to 0.0.
-   deathclaw/animations/mtidle.hkx — NPC Root [Root] static Z
    normalized to 0.0.
-   deathclaw/animations/mtturnleft.hkx — NPC Root [Root] static Z
    normalized to 0.0.
-   deathclaw/animations/mtturnright.hkx — NPC Root [Root] static Z
    normalized to 0.0.
-   deathclaw/animations/ragdollpose.hkx — NPC Root [Root] static Z
    normalized to 0.0.
-   dog/animations/mtidle.hkx — NPC Root [Root] static Z normalized to
    0.0.
-   dog/animations/mtturnright.hkx — NPC Root [Root] static Z normalized
    to 0.0.
-   dog/animations/ragdollpose.hkx — NPC Root [Root] static Z normalized
    to 0.0.
-   ghoul/animations/1gtattackthrow.hkx — NPC Root [Root] static Z
    normalized to 0.0.
-   ghoul/animations/h2hattackbackpower.hkx — NPC Root [Root] static Z
    normalized to 0.0.
-   ghoul/animations/h2hattackforwardpower.hkx — NPC Root [Root] static
    Z normalized to 0.0.
-   ghoul/animations/h2hattackleft.hkx — NPC Root [Root] static Z
    normalized to 0.0.
-   ghoul/animations/h2hattackleftb.hkx — NPC Root [Root] static Z
    normalized to 0.0.
-   ghoul/animations/h2hattackleftc.hkx — NPC Root [Root] static Z
    normalized to 0.0.
-   ghoul/animations/h2hattackleftdown.hkx — NPC Root [Root] static Z
    normalized to 0.0.
-   ghoul/animations/h2hattackleftdownb.hkx — NPC Root [Root] static Z
    normalized to 0.0.
-   ghoul/animations/h2hattackleftdownc.hkx — NPC Root [Root] static Z
    normalized to 0.0.
-   ghoul/animations/h2hattackleftpower.hkx — NPC Root [Root] static Z
    normalized to 0.0.
-   ghoul/animations/h2hattackleftup.hkx — NPC Root [Root] static Z
    normalized to 0.0.
-   ghoul/animations/h2hattackleftupb.hkx — NPC Root [Root] static Z
    normalized to 0.0.
-   ghoul/animations/h2hattackleftupc.hkx — NPC Root [Root] static Z
    normalized to 0.0.
-   ghoul/animations/h2hattackright.hkx — NPC Root [Root] static Z
    normalized to 0.0.
-   ghoul/animations/h2hattackrightb.hkx — NPC Root [Root] static Z
    normalized to 0.0.
-   ghoul/animations/h2hattackrightc.hkx — NPC Root [Root] static Z
    normalized to 0.0.
-   ghoul/animations/h2hattackrightdown.hkx — NPC Root [Root] static Z
    normalized to 0.0.
-   ghoul/animations/h2hattackrightdownb.hkx — NPC Root [Root] static Z
    normalized to 0.0.
-   ghoul/animations/h2hattackrightdownc.hkx — NPC Root [Root] static Z
    normalized to 0.0.
-   ghoul/animations/h2hattackrightpower.hkx — NPC Root [Root] static Z
    normalized to 0.0.
-   ghoul/animations/h2hattackrightup.hkx — NPC Root [Root] static Z
    normalized to 0.0.
-   ghoul/animations/h2hattackrightupb.hkx — NPC Root [Root] static Z
    normalized to 0.0.
-   ghoul/animations/h2hattackrightupc.hkx — NPC Root [Root] static Z
    normalized to 0.0.
-   ghoul/animations/mtidle.hkx — NPC Root [Root] static Z normalized to
    0.0.
-   ghoul/animations/mtturnleft.hkx — NPC Root [Root] static Z
    normalized to 0.0.
-   ghoul/animations/mtturnright.hkx — NPC Root [Root] static Z
    normalized to 0.0.
-   ghoul/animations/ragdollpose.hkx — NPC Root [Root] static Z
    normalized to 0.0.
-   libertyprime/animations/1gtattackthrow.hkx — NPC Root [Root] static
    Z normalized to 0.0.
-   libertyprime/animations/1hpattackright.hkx — NPC Root [Root] static
    Z normalized to 0.0.
-   libertyprime/animations/1hpattackrightdown.hkx — NPC Root [Root]
    static Z normalized to 0.0.
-   libertyprime/animations/mtidle.hkx — NPC Root [Root] static Z
    normalized to 0.0.
-   libertyprime/animations/mtturnleft.hkx — NPC Root [Root] static Z
    normalized to 0.0.
-   libertyprime/animations/mtturnright.hkx — NPC Root [Root] static Z
    normalized to 0.0.
-   libertyprime/animations/ragdollpose.hkx — NPC Root [Root] static Z
    normalized to 0.0.
-   mirelurk/animations/awarevocal.hkx — NPC Root [Root] static Z
    normalized to 0.0.
-   mirelurk/animations/mtidle.hkx — NPC Root [Root] static Z normalized
    to 0.0.
-   mirelurk/animations/ragdollpose.hkx — NPC Root [Root] static Z
    normalized to 0.0.
-   mirelurkking/animations/awarevocal.hkx — NPC Root [Root] static Z
    normalized to 0.0.
-   mirelurkking/animations/h2hattackforwardpower.hkx — NPC Root [Root]
    static Z normalized to 0.0.
-   mirelurkking/animations/h2hattackleftbackhand.hkx — NPC Root [Root]
    static Z normalized to 0.0.
-   mirelurkking/animations/h2hattackleftjab.hkx — NPC Root [Root]
    static Z normalized to 0.0.
-   mirelurkking/animations/h2hattackpower.hkx — NPC Root [Root] static
    Z normalized to 0.0.
-   mirelurkking/animations/h2hattackrightjab.hkx — NPC Root [Root]
    static Z normalized to 0.0.
-   mirelurkking/animations/h2hattackrightslice.hkx — NPC Root [Root]
    static Z normalized to 0.0.
-   mirelurkking/animations/mtidle.hkx — NPC Root [Root] static Z
    normalized to 0.0.
-   mirelurkking/animations/mtturnleft.hkx — NPC Root [Root] static Z
    normalized to 0.0.
-   mirelurkking/animations/mtturnright.hkx — NPC Root [Root] static Z
    normalized to 0.0.
-   mirelurkking/animations/ragdollpose.hkx — NPC Root [Root] static Z
    normalized to 0.0.
-   nvcazadores/animations/h2hattackleft.hkx — NPC Root [Root] static Z
    normalized to 0.0.
-   nvsecuritron/animations/h2hattackforwardpower.hkx — NPC Root [Root]
    static Z normalized to 0.0.
-   nvsecuritron/animations/h2hattackpower.hkx — NPC Root [Root] static
    Z normalized to 0.0.
-   nvsecuritron/animations/h2hattackright.hkx — NPC Root [Root] static
    Z normalized to 0.0.
-   nvtumbleweed/animations/mtidle.hkx — NPC Root [Root] static Z
    normalized to 0.0.
-   nvtumbleweed/animations/ragdollpose.hkx — NPC Root [Root] static Z
    normalized to 0.0.
-   nvvoid/animations/mtidle.hkx — NPC Root [Root] static Z normalized
    to 0.0.
-   nvvoid/animations/ragdollpose.hkx — NPC Root [Root] static Z
    normalized to 0.0.
-   protectron/animations/h2hattackleftchop.hkx — NPC Root [Root] static
    Z normalized to 0.0.
-   protectron/animations/h2hattackleftslash.hkx — NPC Root [Root]
    static Z normalized to 0.0.
-   protectron/animations/h2hattackrightchop.hkx — NPC Root [Root]
    static Z normalized to 0.0.
-   protectron/animations/h2hattackrightslash.hkx — NPC Root [Root]
    static Z normalized to 0.0.
-   protectron/animations/mtturnleft.hkx — NPC Root [Root] static Z
    normalized to 0.0.
-   protectron/animations/mtturnright.hkx — NPC Root [Root] static Z
    normalized to 0.0.
-   sentrybot/animations/2hhattackloop.hkx — NPC Root [Root] static Z
    normalized to 0.0.
-   sentrybot/animations/2hhattackloopdown.hkx — NPC Root [Root] static
    Z normalized to 0.0.
-   sentrybot/animations/2hhattackloopup.hkx — NPC Root [Root] static Z
    normalized to 0.0.
-   sentrybot/animations/2hhattackspin.hkx — NPC Root [Root] static Z
    normalized to 0.0.
-   sentrybot/animations/2hhattackspindown.hkx — NPC Root [Root] static
    Z normalized to 0.0.
-   sentrybot/animations/2hhattackspinup.hkx — NPC Root [Root] static Z
    normalized to 0.0.
-   sentrybot/animations/2hlattackleft.hkx — NPC Root [Root] static Z
    normalized to 0.0.
-   sentrybot/animations/2hlattackleftdown.hkx — NPC Root [Root] static
    Z normalized to 0.0.
-   sentrybot/animations/2hlattackleftup.hkx — NPC Root [Root] static Z
    normalized to 0.0.
-   sentrybot/animations/2hrattackspin.hkx — NPC Root [Root] static Z
    normalized to 0.0.
-   sentrybot/animations/2hrattackspindown.hkx — NPC Root [Root] static
    Z normalized to 0.0.
-   sentrybot/animations/2hrattackspinup.hkx — NPC Root [Root] static Z
    normalized to 0.0.
-   sentrybot/animations/mtidle.hkx — NPC Root [Root] static Z
    normalized to 0.0.
-   sentrybot/animations/mtturnleft.hkx — NPC Root [Root] static Z
    normalized to 0.0.
-   sentrybot/animations/mtturnright.hkx — NPC Root [Root] static Z
    normalized to 0.0.
-   sentrybot/animations/ragdollpose.hkx — NPC Root [Root] static Z
    normalized to 0.0.
-   smbehemoth/animations/1gtattackthrow.hkx — NPC Root [Root] static Z
    normalized to 0.0.
-   smbehemoth/animations/2hmattackforwardpower.hkx — NPC Root [Root]
    static Z normalized to 0.0.
-   smbehemoth/animations/2hmattacklefta.hkx — NPC Root [Root] static Z
    normalized to 0.0.
-   smbehemoth/animations/2hmattackleftdowna.hkx — NPC Root [Root]
    static Z normalized to 0.0.
-   smbehemoth/animations/2hmattackleftupa.hkx — NPC Root [Root] static
    Z normalized to 0.0.
-   smbehemoth/animations/2hmattackpower.hkx — NPC Root [Root] static Z
    normalized to 0.0.
-   smbehemoth/animations/2hmattackrighta.hkx — NPC Root [Root] static Z
    normalized to 0.0.
-   smbehemoth/animations/2hmattackrightb.hkx — NPC Root [Root] static Z
    normalized to 0.0.
-   smbehemoth/animations/2hmattackrightdowna.hkx — NPC Root [Root]
    static Z normalized to 0.0.
-   smbehemoth/animations/2hmattackrightdownb.hkx — NPC Root [Root]
    static Z normalized to 0.0.
-   smbehemoth/animations/2hmattackrightupa.hkx — NPC Root [Root] static
    Z normalized to 0.0.
-   smbehemoth/animations/2hmattackrightupb.hkx — NPC Root [Root] static
    Z normalized to 0.0.
-   smbehemoth/animations/h2hattacklefta.hkx — NPC Root [Root] static Z
    normalized to 0.0.
-   smbehemoth/animations/h2hattackleftb.hkx — NPC Root [Root] static Z
    normalized to 0.0.
-   smbehemoth/animations/h2hattackleftdowna.hkx — NPC Root [Root]
    static Z normalized to 0.0.
-   smbehemoth/animations/h2hattackleftdownb.hkx — NPC Root [Root]
    static Z normalized to 0.0.
-   smbehemoth/animations/h2hattackleftupa.hkx — NPC Root [Root] static
    Z normalized to 0.0.
-   smbehemoth/animations/h2hattackleftupb.hkx — NPC Root [Root] static
    Z normalized to 0.0.
-   smbehemoth/animations/h2hattackrighta.hkx — NPC Root [Root] static Z
    normalized to 0.0.
-   smbehemoth/animations/h2hattackrightb.hkx — NPC Root [Root] static Z
    normalized to 0.0.
-   smbehemoth/animations/h2hattackrightdowna.hkx — NPC Root [Root]
    static Z normalized to 0.0.
-   smbehemoth/animations/h2hattackrightdownb.hkx — NPC Root [Root]
    static Z normalized to 0.0.
-   smbehemoth/animations/h2hattackrightupa.hkx — NPC Root [Root] static
    Z normalized to 0.0.
-   smbehemoth/animations/h2hattackrightupb.hkx — NPC Root [Root] static
    Z normalized to 0.0.
-   smbehemoth/animations/mtidle.hkx — NPC Root [Root] static Z
    normalized to 0.0.
-   smbehemoth/animations/mtturnleft.hkx — NPC Root [Root] static Z
    normalized to 0.0.
-   smbehemoth/animations/mtturnright.hkx — NPC Root [Root] static Z
    normalized to 0.0.
-   smbehemoth/animations/ragdollpose.hkx — NPC Root [Root] static Z
    normalized to 0.0.
-   smbonecrusher/animations/1gtattackthrow.hkx — NPC Root [Root] static
    Z normalized to 0.0.
-   smbonecrusher/animations/2haattackloop.hkx — NPC Root [Root] static
    Z normalized to 0.0.
-   smbonecrusher/animations/2haattackloopdown.hkx — NPC Root [Root]
    static Z normalized to 0.0.
-   smbonecrusher/animations/2haattackloopup.hkx — NPC Root [Root]
    static Z normalized to 0.0.
-   smbonecrusher/animations/2hhattackloop.hkx — NPC Root [Root] static
    Z normalized to 0.0.
-   smbonecrusher/animations/2hhattackloopdown.hkx — NPC Root [Root]
    static Z normalized to 0.0.
-   smbonecrusher/animations/2hhattackloopup.hkx — NPC Root [Root]
    static Z normalized to 0.0.
-   smbonecrusher/animations/2hhattackspin.hkx — NPC Root [Root] static
    Z normalized to 0.0.
-   smbonecrusher/animations/2hhattackspindown.hkx — NPC Root [Root]
    static Z normalized to 0.0.
-   smbonecrusher/animations/2hhattackspinup.hkx — NPC Root [Root]
    static Z normalized to 0.0.
-   smbonecrusher/animations/2hlattackright.hkx — NPC Root [Root] static
    Z normalized to 0.0.
-   smbonecrusher/animations/2hlattackrightdown.hkx — NPC Root [Root]
    static Z normalized to 0.0.
-   smbonecrusher/animations/2hlattackrightup.hkx — NPC Root [Root]
    static Z normalized to 0.0.
-   smbonecrusher/animations/2hmattackforwardpower.hkx — NPC Root [Root]
    static Z normalized to 0.0.
-   smbonecrusher/animations/2hmattacklefta.hkx — NPC Root [Root] static
    Z normalized to 0.0.
-   smbonecrusher/animations/2hmattackleftpower.hkx — NPC Root [Root]
    static Z normalized to 0.0.
-   smbonecrusher/animations/2hmattackpower.hkx — NPC Root [Root] static
    Z normalized to 0.0.
-   smbonecrusher/animations/2hmattackrighta.hkx — NPC Root [Root]
    static Z normalized to 0.0.
-   smbonecrusher/animations/2hmattackrightb.hkx — NPC Root [Root]
    static Z normalized to 0.0.
-   smbonecrusher/animations/2hmattackrightpower.hkx — NPC Root [Root]
    static Z normalized to 0.0.
-   smbonecrusher/animations/2hrattack4.hkx — NPC Root [Root] static Z
    normalized to 0.0.
-   smbonecrusher/animations/2hrattack4down.hkx — NPC Root [Root] static
    Z normalized to 0.0.
-   smbonecrusher/animations/2hrattack4up.hkx — NPC Root [Root] static Z
    normalized to 0.0.
-   smbonecrusher/animations/h2hattackforwardpower.hkx — NPC Root [Root]
    static Z normalized to 0.0.
-   smbonecrusher/animations/h2hattacklefta.hkx — NPC Root [Root] static
    Z normalized to 0.0.
-   smbonecrusher/animations/h2hattackleftb.hkx — NPC Root [Root] static
    Z normalized to 0.0.
-   smbonecrusher/animations/h2hattackleftpower.hkx — NPC Root [Root]
    static Z normalized to 0.0.
-   smbonecrusher/animations/h2hattackrighta.hkx — NPC Root [Root]
    static Z normalized to 0.0.
-   smbonecrusher/animations/h2hattackrightb.hkx — NPC Root [Root]
    static Z normalized to 0.0.
-   smbonecrusher/animations/h2hattackrightpower.hkx — NPC Root [Root]
    static Z normalized to 0.0.
-   smbonecrusher/animations/mtdeath.hkx — NPC Root [Root] static Z
    normalized to 0.0.
-   smbonecrusher/animations/mtidle.hkx — NPC Root [Root] static Z
    normalized to 0.0.
-   smbonecrusher/animations/mtturnleft.hkx — NPC Root [Root] static Z
    normalized to 0.0.
-   smbonecrusher/animations/mtturnright.hkx — NPC Root [Root] static Z
    normalized to 0.0.
-   smbonecrusher/animations/ragdollpose.hkx — NPC Root [Root] static Z
    normalized to 0.0.
-   smspinebreaker/animations/1gtattackthrow.hkx — NPC Root [Root]
    static Z normalized to 0.0.
-   smspinebreaker/animations/1gtattackthrowdown.hkx — NPC Root [Root]
    static Z normalized to 0.0.
-   smspinebreaker/animations/1gtattackthrowup.hkx — NPC Root [Root]
    static Z normalized to 0.0.
-   smspinebreaker/animations/2haattackloop.hkx — NPC Root [Root] static
    Z normalized to 0.0.
-   smspinebreaker/animations/2haattackloopdown.hkx — NPC Root [Root]
    static Z normalized to 0.0.
-   smspinebreaker/animations/2haattackloopup.hkx — NPC Root [Root]
    static Z normalized to 0.0.
-   smspinebreaker/animations/2hhattackloop.hkx — NPC Root [Root] static
    Z normalized to 0.0.
-   smspinebreaker/animations/2hhattackloopdown.hkx — NPC Root [Root]
    static Z normalized to 0.0.
-   smspinebreaker/animations/2hhattackloopup.hkx — NPC Root [Root]
    static Z normalized to 0.0.
-   smspinebreaker/animations/2hhattackspin.hkx — NPC Root [Root] static
    Z normalized to 0.0.
-   smspinebreaker/animations/2hhattackspindown.hkx — NPC Root [Root]
    static Z normalized to 0.0.
-   smspinebreaker/animations/2hhattackspinup.hkx — NPC Root [Root]
    static Z normalized to 0.0.
-   smspinebreaker/animations/2hlattackright.hkx — NPC Root [Root]
    static Z normalized to 0.0.
-   smspinebreaker/animations/2hlattackrightdown.hkx — NPC Root [Root]
    static Z normalized to 0.0.
-   smspinebreaker/animations/2hlattackrightup.hkx — NPC Root [Root]
    static Z normalized to 0.0.
-   smspinebreaker/animations/2hmattackforwardpower.hkx — NPC Root
    [Root] static Z normalized to 0.0.
-   smspinebreaker/animations/2hmattacklefta.hkx — NPC Root [Root]
    static Z normalized to 0.0.
-   smspinebreaker/animations/2hmattackleftdowna.hkx — NPC Root [Root]
    static Z normalized to 0.0.
-   smspinebreaker/animations/2hmattackleftpower.hkx — NPC Root [Root]
    static Z normalized to 0.0.
-   smspinebreaker/animations/2hmattackleftupa.hkx — NPC Root [Root]
    static Z normalized to 0.0.
-   smspinebreaker/animations/2hmattackpower.hkx — NPC Root [Root]
    static Z normalized to 0.0.
-   smspinebreaker/animations/2hmattackrighta.hkx — NPC Root [Root]
    static Z normalized to 0.0.
-   smspinebreaker/animations/2hmattackrightb.hkx — NPC Root [Root]
    static Z normalized to 0.0.
-   smspinebreaker/animations/2hmattackrightdowna.hkx — NPC Root [Root]
    static Z normalized to 0.0.
-   smspinebreaker/animations/2hmattackrightdownb.hkx — NPC Root [Root]
    static Z normalized to 0.0.
-   smspinebreaker/animations/2hmattackrightpower.hkx — NPC Root [Root]
    static Z normalized to 0.0.
-   smspinebreaker/animations/2hmattackrightupa.hkx — NPC Root [Root]
    static Z normalized to 0.0.
-   smspinebreaker/animations/2hmattackrightupb.hkx — NPC Root [Root]
    static Z normalized to 0.0.
-   smspinebreaker/animations/2hrattack3.hkx — NPC Root [Root] static Z
    normalized to 0.0.
-   smspinebreaker/animations/2hrattack3down.hkx — NPC Root [Root]
    static Z normalized to 0.0.
-   smspinebreaker/animations/2hrattack3up.hkx — NPC Root [Root] static
    Z normalized to 0.0.
-   smspinebreaker/animations/h2hattackforwardpower.hkx — NPC Root
    [Root] static Z normalized to 0.0.
-   smspinebreaker/animations/h2hattacklefta.hkx — NPC Root [Root]
    static Z normalized to 0.0.
-   smspinebreaker/animations/h2hattackleftb.hkx — NPC Root [Root]
    static Z normalized to 0.0.
-   smspinebreaker/animations/h2hattackleftdowna.hkx — NPC Root [Root]
    static Z normalized to 0.0.
-   smspinebreaker/animations/h2hattackleftdownb.hkx — NPC Root [Root]
    static Z normalized to 0.0.
-   smspinebreaker/animations/h2hattackleftpower.hkx — NPC Root [Root]
    static Z normalized to 0.0.
-   smspinebreaker/animations/h2hattackleftupa.hkx — NPC Root [Root]
    static Z normalized to 0.0.
-   smspinebreaker/animations/h2hattackleftupb.hkx — NPC Root [Root]
    static Z normalized to 0.0.
-   smspinebreaker/animations/h2hattackrighta.hkx — NPC Root [Root]
    static Z normalized to 0.0.
-   smspinebreaker/animations/h2hattackrightb.hkx — NPC Root [Root]
    static Z normalized to 0.0.
-   smspinebreaker/animations/h2hattackrightdowna.hkx — NPC Root [Root]
    static Z normalized to 0.0.
-   smspinebreaker/animations/h2hattackrightdownb.hkx — NPC Root [Root]
    static Z normalized to 0.0.
-   smspinebreaker/animations/h2hattackrightpower.hkx — NPC Root [Root]
    static Z normalized to 0.0.
-   smspinebreaker/animations/h2hattackrightupa.hkx — NPC Root [Root]
    static Z normalized to 0.0.
-   smspinebreaker/animations/h2hattackrightupb.hkx — NPC Root [Root]
    static Z normalized to 0.0.
-   smspinebreaker/animations/mtidle.hkx — NPC Root [Root] static Z
    normalized to 0.0.
-   smspinebreaker/animations/mtturnleft.hkx — NPC Root [Root] static Z
    normalized to 0.0.
-   smspinebreaker/animations/mtturnright.hkx — NPC Root [Root] static Z
    normalized to 0.0.
-   smspinebreaker/animations/ragdollpose.hkx — NPC Root [Root] static Z
    normalized to 0.0.
-   smspinebreaker/animations/swimmtidle.hkx — NPC Root [Root] static Z
    normalized to 0.0.
-   smspinebreaker/animations/swimmtturnleft.hkx — NPC Root [Root]
    static Z normalized to 0.0.
-   smspinebreaker/animations/swimmtturnright.hkx — NPC Root [Root]
    static Z normalized to 0.0.

2. Super Mutant / Nightkin attack facing

Certain smbonecrusher and smspinebreaker attack animations contained an
unwanted approximately +90-degree heading on animation track 1,
Bip01 NonAccum. In Skyrim this caused the actor to turn left when the
attack began.

The correction removes the erroneous +90-degree base heading from
Bip01 NonAccum.

For static NonAccum rotations, the single stored rotation was corrected.
For the three spline-animated Nightkin power attacks, the heading
correction was applied to every quaternion control point, preserving the
attack’s authored relative rotational motion.

Facing-corrected attack HKX files: 41

-   smbonecrusher/animations/2haattackloopdown.hkx — Bip01 NonAccum
    static heading corrected by removing the baked approximately
    +90-degree rotation.
-   smbonecrusher/animations/2haattackloopup.hkx — Bip01 NonAccum static
    heading corrected by removing the baked approximately +90-degree
    rotation.
-   smbonecrusher/animations/2hhattackloopdown.hkx — Bip01 NonAccum
    static heading corrected by removing the baked approximately
    +90-degree rotation.
-   smbonecrusher/animations/2hhattackloopup.hkx — Bip01 NonAccum static
    heading corrected by removing the baked approximately +90-degree
    rotation.
-   smbonecrusher/animations/2hhattackspindown.hkx — Bip01 NonAccum
    static heading corrected by removing the baked approximately
    +90-degree rotation.
-   smbonecrusher/animations/2hhattackspinup.hkx — Bip01 NonAccum static
    heading corrected by removing the baked approximately +90-degree
    rotation.
-   smbonecrusher/animations/2hlattackrightdown.hkx — Bip01 NonAccum
    static heading corrected by removing the baked approximately
    +90-degree rotation.
-   smbonecrusher/animations/2hlattackrightup.hkx — Bip01 NonAccum
    static heading corrected by removing the baked approximately
    +90-degree rotation.
-   smbonecrusher/animations/2hmattackforwardpower.hkx — Bip01 NonAccum
    static heading corrected by removing the baked approximately
    +90-degree rotation.
-   smbonecrusher/animations/2hmattackleftpower.hkx — Bip01 NonAccum
    static heading corrected by removing the baked approximately
    +90-degree rotation.
-   smbonecrusher/animations/2hmattackpower.hkx — Bip01 NonAccum static
    heading corrected by removing the baked approximately +90-degree
    rotation.
-   smbonecrusher/animations/2hmattackrightpower.hkx — Bip01 NonAccum
    static heading corrected by removing the baked approximately
    +90-degree rotation.
-   smbonecrusher/animations/2hrattack4down.hkx — Bip01 NonAccum static
    heading corrected by removing the baked approximately +90-degree
    rotation.
-   smbonecrusher/animations/2hrattack4up.hkx — Bip01 NonAccum static
    heading corrected by removing the baked approximately +90-degree
    rotation.
-   smbonecrusher/animations/h2hattackforwardpower.hkx — Bip01 NonAccum
    static heading corrected by removing the baked approximately
    +90-degree rotation.
-   smbonecrusher/animations/h2hattackrightpower.hkx — Bip01 NonAccum
    static heading corrected by removing the baked approximately
    +90-degree rotation.
-   smspinebreaker/animations/2haattackloopdown.hkx — Bip01 NonAccum
    static heading corrected by removing the baked approximately
    +90-degree rotation.
-   smspinebreaker/animations/2haattackloopup.hkx — Bip01 NonAccum
    static heading corrected by removing the baked approximately
    +90-degree rotation.
-   smspinebreaker/animations/2hhattackloopdown.hkx — Bip01 NonAccum
    static heading corrected by removing the baked approximately
    +90-degree rotation.
-   smspinebreaker/animations/2hhattackloopup.hkx — Bip01 NonAccum
    static heading corrected by removing the baked approximately
    +90-degree rotation.
-   smspinebreaker/animations/2hhattackspindown.hkx — Bip01 NonAccum
    static heading corrected by removing the baked approximately
    +90-degree rotation.
-   smspinebreaker/animations/2hhattackspinup.hkx — Bip01 NonAccum
    static heading corrected by removing the baked approximately
    +90-degree rotation.
-   smspinebreaker/animations/2hlattackrightdown.hkx — Bip01 NonAccum
    static heading corrected by removing the baked approximately
    +90-degree rotation.
-   smspinebreaker/animations/2hlattackrightup.hkx — Bip01 NonAccum
    static heading corrected by removing the baked approximately
    +90-degree rotation.
-   smspinebreaker/animations/2hmattackforwardpower.hkx — Bip01 NonAccum
    spline heading corrected across 71 quaternion control points.
-   smspinebreaker/animations/2hmattackleftdowna.hkx — Bip01 NonAccum
    static heading corrected by removing the baked approximately
    +90-degree rotation.
-   smspinebreaker/animations/2hmattackleftpower.hkx — Bip01 NonAccum
    spline heading corrected across 71 quaternion control points.
-   smspinebreaker/animations/2hmattackrightdowna.hkx — Bip01 NonAccum
    static heading corrected by removing the baked approximately
    +90-degree rotation.
-   smspinebreaker/animations/2hmattackrightdownb.hkx — Bip01 NonAccum
    static heading corrected by removing the baked approximately
    +90-degree rotation.
-   smspinebreaker/animations/2hmattackrightpower.hkx — Bip01 NonAccum
    spline heading corrected across 61 quaternion control points.
-   smspinebreaker/animations/2hrattack3down.hkx — Bip01 NonAccum static
    heading corrected by removing the baked approximately +90-degree
    rotation.
-   smspinebreaker/animations/2hrattack3up.hkx — Bip01 NonAccum static
    heading corrected by removing the baked approximately +90-degree
    rotation.
-   smspinebreaker/animations/h2hattackforwardpower.hkx — Bip01 NonAccum
    static heading corrected by removing the baked approximately
    +90-degree rotation.
-   smspinebreaker/animations/h2hattackleftdowna.hkx — Bip01 NonAccum
    static heading corrected by removing the baked approximately
    +90-degree rotation.
-   smspinebreaker/animations/h2hattackleftdownb.hkx — Bip01 NonAccum
    static heading corrected by removing the baked approximately
    +90-degree rotation.
-   smspinebreaker/animations/h2hattackleftupa.hkx — Bip01 NonAccum
    static heading corrected by removing the baked approximately
    +90-degree rotation.
-   smspinebreaker/animations/h2hattackleftupb.hkx — Bip01 NonAccum
    static heading corrected by removing the baked approximately
    +90-degree rotation.
-   smspinebreaker/animations/h2hattackrightdowna.hkx — Bip01 NonAccum
    static heading corrected by removing the baked approximately
    +90-degree rotation.
-   smspinebreaker/animations/h2hattackrightdownb.hkx — Bip01 NonAccum
    static heading corrected by removing the baked approximately
    +90-degree rotation.
-   smspinebreaker/animations/h2hattackrightupa.hkx — Bip01 NonAccum
    static heading corrected by removing the baked approximately
    +90-degree rotation.
-   smspinebreaker/animations/h2hattackrightupb.hkx — Bip01 NonAccum
    static heading corrected by removing the baked approximately
    +90-degree rotation.

Important implementation notes

-   Vertical correction: NPC Root [Root] static Z -> 0.0 on the audited
    affected non-locomotion clips.
-   Facing correction: remove the baked approximately +90-degree heading
    from Bip01 NonAccum on the listed Super Mutant/Nightkin attacks.
-   Do not zero Bip01 NonAccum Z.
-   Do not apply these corrections indiscriminately to locomotion.
-   Preserve authored relative spline motion when removing a baked base
    heading.
-   No behavior HKX, attack timing, HitFrame/preHitFrame timing, or
    locomotion was intentionally changed by the facing pass.
-   The facing-fix files were built on top of the Z-corrected animation
    batch, so overlapping files retain their vertical correction.