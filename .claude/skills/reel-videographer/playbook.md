# Videographer playbook: Reel Studio (talking and product reels, 30 fps, 1080x1920)

**Conventions**
- **Units:** f = one frame at 30 fps (33 ms). W = 1080, H = 1920.
- **C** = the cut frame, i.e. the first frame of the incoming material. For an in-shot move, C is the frame of the event. OUT = the frames before C; IN = C and the frames after it.
- **s** = virtual-camera scale over the shot's base framing.
- **e** = effective upscale = s x 1080 / (width of the sampled source). With today's 1080x1920 intermediates, e = s.
- **LU** = loudness relative to the dialogue's short-term LUFS. "-12 LU" means 12 LU quieter than her voice.
- **Easing slopes** (the slope at the fast end, used for velocity matching): in-cubic 3, out-cubic 3, in-quint 5, out-expo about 6.9.

**Evidence tags**
- [M] measured: a study, a standard, or platform data. Platform data is correlational and often platform-commissioned.
- [C] consensus of several editors' tutorials.
- [O] opinion or a single source.
- [FP] geometry or first principles.

Frame values come from tutorials made at 24 or 30 fps. Treat them as starting points and tune by eye within about 20%.

---

## 1. Principles

1. **A reel feels dead when the frame is the only thing that doesn't react to her.** The yocase_line draft shows this on every axis:
   - a 1.04 creep, 1.06 cut-ins and two 1.06 in-out punch blips, one flash, no transitions, and the same whoosh on every cut;
   - every move was under the roughly 10% threshold where a change reads as intended;
   - the two motions in the footage (the sweep and the bottle push) were ignored.

   A reel feels alive when the virtual camera answers her body. [C]
2. **Only add movement the footage motivates.** Every designed transition needs a motion you can name on screen:
   - sweep → swipe-whip;
   - push toward the lens → zoom-through;
   - a real lens cover → frame-fill cut;
   - a real rotation → spin.

   If you can't name the motion, use a hard cut, a match cut or an A/B step. Unmotivated presets are what reads as a "CapCut template". [C]
3. **The camera reacts; it never leads.** A virtual move starts at least 1-2 f after the real gesture starts. The cut goes on the gesture's peak speed (sweep) or maximum size (push), +/-1 f, and never after the gesture has ended. [C]
4. **Every cut needs motion after it.** The incoming shot must be moving within 1-3 f: subject action, a creep that starts on frame 1, or a transition tail.
   - Motion after the cut hides the cut; motion before it does not.
   - Edit blindness largely disappears without the soundtrack (Smith & Martin-Portugues Santacreu 2017). [M; applying this to virtual camera moves is [O]]
5. **Commit to a move or don't make it.** Scale changes on cuts are hard steps of at least 10%, held to the end of the thought.
   - Steps of 4-8% read as a stabiliser glitch.
   - In-out blips read as twitches.
   - No pumping: no zoom-out settle followed by a push-in, and no in/out alternation across cuts. [C]
6. **Rhythm comes from contrast.** A rush (whip or zoom-through, 16 f or less) is followed by calm (a read-hold of at least 45-60 f with the label steady).
   - Make a visual change every 1.5-4 s, at varied intervals.
   - Nothing stays static for more than 3-4 s.
   - One event move at a time, at least 15 f apart. [C/O]
7. **Keep the structure fixed and vary the intensity.** Use at most 2 designed transition types per reel and the same slot grammar for every product. Intensity follows a curve: full, then about 20% lighter, then full plus the hero accent. [C]
8. **Sound makes a move feel physical; resolution limits how far it can go.**
   - One sound family per event type, peaking on C or C+1.
   - Music and room tone run continuously.
   - Held frames stay at e ≤ 1.2; only 2-3 motion-blurred frames may reach 1.6. [M/C/FP]

---

## 2. Effects catalog

### 2.1 Swipe-whip on the hand sweep (the "camera turns" move) [C]
- **When**
  - The trigger is a sideways hand or arm sweep: horizontal flow of at least 25-40 px/f (at 1080 width) for 3 or more consecutive frames, with the hand crossing at least 25% of W within 10 f.
  - C = the frame of maximum horizontal speed, +/-1 f.
  - If C falls 2 f or less inside a word, move it to the word's end. Otherwise keep it and let the voice carry across the cut (J/L-cut).
  - Skip it if the sweep is slower than about 25 px/f, or if the spacing to the push cut fails the gap rule in 3.3.
- **Params**
  - **Timing:** 10-14 f in total. 15 f is the slow limit; 25 f is clearly sluggish. OUT is 4-5 f accelerating, IN is 6-10 f decelerating. In push mode the travel is one frame width (540 px per half).
  - **Velocity must match at C within +/-20%.** Peak speed per half = slope x 540 / frames.
    - Preset A: OUT 5 f in-cubic + IN 5 f out-cubic gives 324 px/f on both sides.
    - Preset B: OUT 4 f in-cubic (405 px/f) + IN 9 f out-expo (about 416 px/f; it looks settled by IN frame 5).
    - Never use OUT 4 in-cubic + IN 7 out-cubic: 405 against 231 px/f is a visible brake.
    - Target peak: 250-420 px/f.
  - **Blur:** a sub-frame shutter of 0.5-0.75 f gives a 150-300 px streak at C and under 15 px at both ends.
  - **Direction:** the picture travels with the hand, as if the hand throws the frame away. Use "follow" (picture against the hand) only for head turns or looks. One convention per reel.
  - **Camera-turn roll (optional):** 2-4 degrees toward the move, peaking at C and gone by C+6. It needs overscale of 1 + 0.031 x deg (3 degrees → 1.09).
  - **Overshoot (optional):** 2-4% of the travel (20-40 px), settling over 6-8 f.
  - **Two shots on screen?** Use push mode (the seam crosses centre at C) only when both shots' mean luma is within about 10%. Otherwise use a single-shot whip (mirror fill, cut inside the peak-blur frame) or a 2-3 f crossfade inside the peak-blur frames.
  - **Same-take landing** (the normal case here, since sweep and push are one take):
    - Drop dead frames between the sweep peak and the push, but leave at least 15 f of calm before the push starts.
    - Land on B framing, 1.12-1.15 anchored on the bottle, so the landing reads as a new angle.
    - Never land on the same framing.
    - A slow sweep may have its last 4 source frames sped up 1.3-1.5x, but only if there is no speech under them.
- **SFX**
  - One short swish, 8-15 f, with a fast attack. The audible onset is no earlier than the OUT start. The peak lands on C or C+1 (allowed C-1 to C+3). The tail may decay 6-12 f past C.
  - Level: 8-12 LU under the dialogue in a speech gap; 15 LU or more under if it overlaps speech (better to avoid).
  - Rotate `whoosh_quick_03_swish`, `whoosh_soft_02_wind_swoosh` and `whoosh_soft_01_air_sweep`. Optional pan of 30% or less.
- **Limit**
  - At most 1 per product block, 2-4 per 30 s, at least 45 f apart.
  - A weak or badly spaced sweep becomes a hard A→B punch cut on the sweep's peak frame, so the slot still gets something on the sweep.
- **Avoid**
  - Whipping when there is no real sweep, or a half-hearted one.
  - The picture and the hand moving in opposite directions.
  - A velocity jump at C.
  - Linear or constant speed (reads as a slide-show).
  - Longer than 15 f.
  - Mirrored faces or the seam readable for more than about 3 f.
  - A brightness jump at the seam.
  - Landing on the same framing.
  - A whoosh that starts before the hand moves.
  - The same sample every time.

### 2.2 Zoom-through: bottle pushed to the lens → hand-held close-up [C]
- **When**
  - The tracked bottle's area grows at least 1.5x within 10-15 f (or optical-flow divergence peaks on the bottle), and a close-up of the same product follows.
  - C = the frame where the bottle is largest, or the last sharp frame before it defocuses.
  - **Decide by bottle width b (as a fraction of W) at C:**
    - b ≥ 0.6, or the bottle's Laplacian sharpness drops more than 50% → use the frame-fill cut (2.3).
    - 0.2 ≤ b < 0.6 → zoom-through.
    - b < 0.2 → the push is too weak: hard punch to the bottle, then a plain cut.
- **Params:** 11-16 f in total; no frames are dropped at C.
  - **OUT, 5-7 f**
    - Interpolate log(scale), not scale, with in-cubic easing so the log-scale rate peaks at C.
    - Pick the end scale by size matching rather than a fixed 2.2: s_out = clamp(b_cu x s_in0 / b, 1.25, 1.8), where b_cu is the bottle width on the close-up's first frame. This is typically 1.3-1.7.
    - Ease the crop centre onto the tracked label every frame, not onto a fixed point.
    - Resolution: on 1080 intermediates, s_out up to 1.6 is fine, because only the last 2 OUT frames exceed 1.2 and they are blurred. Above 1.6 you need 4K sampling. [FP]
    - Blur: a shutter of 0.5-0.75 f and no extra radial blur. At a peak log-rate of about 0.25/f this gives about 40 px streaks near the bottle and 120-170 px at the corners.
  - **Continuity at C:** the bottle's width on the first IN frame is 0.9-1.15x its width on the last OUT frame, and its centre is within +/-10% of W.
  - **IN: pick one mode per reel**
    - **(A) Continuous-in (default for premium beauty):** the close-up goes 1.00-1.05 → 1.08-1.12 with out-expo over 8-10 f, then creeps. The flow keeps its direction and no mirror fill is needed. The speed drop at the cut is the landing; if it reads as a brake, shorten IN to 6 f or end at 1.12-1.15. [FP]
    - **(B) Impact landing (the TikTok "zoom punch"):** the close-up goes 1.20-1.35 → 1.00 with out-expo over 6-8 f. The flow reverses, so it reads as a recoil. Allowed only if the size rule holds; pair it with the thump.
    - **(C) Kolder:** the incoming shot starts at about 0.6x with mirror tiles and grows to 1.0 over about 6 f. This is the 2017 travel-montage look and needs mirror fill. The outgoing shot peaks at about 1.7-2.0x, not 3x.
  - **Optional anticipation:** 1.00 → 1.10-1.20 riding the push over the 6-10 f before OUT, ease-in, starting at least 1-2 f after the push begins. It counts as part of this move.
- **SFX**
  - A rising air swell or reverse whoosh (`whoosh_05_swipe_zoom`, `whoosh_04_air_into_cut`), audible from the OUT start and stopping dead at C.
  - Then a soft low thump (energy below 100 Hz) peaking on C or C+1, at 10-14 LU under the dialogue. Use a different sample per product: `bass_thump_01_sub`, `bass_thump_02_synth`, `punch_soft_impact`.
  - Duck the music 3-4 dB for the hit.
  - Optional: a shimmer 6-10 f after C, once the label is sharp.
- **Limit:** once per product (4 in the lineup reel, as the format's repeating beat; vary only the intensity). Elsewhere, 2 or fewer per 30 s.
- **Avoid**
  - Centring on the frame or the face instead of the bottle.
  - A fixed target while the bottle moves.
  - Linear scale interpolation.
  - The bottle smaller, or jumping sideways, on the first close-up frame.
  - OUT longer than 8 f (soft upscaled frames become readable).
  - e above 1.6 even on blurred frames.
  - Radial blur stacked on the shutter (a double smear).
  - Flash, shake and zoom stacked on every product.
  - The same hit sample 4 times.
  - A CapCut "pull in" preset added on top of a real push.

### 2.3 Frame-fill (occlusion) cut: only when the footage really covers the lens [C]
- **When**
  - The bottle or hand covers at least 90% of the frame (or 60-80% plus heavy defocus) for 2 f or more, typically at the end of a hard push (b ≥ 0.6).
  - CapCut (June 2026) calls the staged hand-cover reveal crowded, so use only covers that happen naturally.
- **Params**
  - Cut on the first frame with 90% or more coverage. Keep 1-3 fully covered frames; never 4 or more.
  - The incoming close-up starts defocused (Gaussian blur 20-40 px decaying to 0 over 3-5 f, out-cubic) or covered by a similar colour, and the reveal moves in the direction the cover was travelling.
  - Optionally add 1.05-1.10 → 1.0 over 6-8 f, or the continuous-in 1.0 → 1.08.
  - If luma or colour differ across the cut, add a 1-2 f fill of the bottle's dominant colour or a dip to 50% white.
  - In a reel that uses the zoom-through, run frame-fill products as a zoom-through with s_out of 1.15 or less, so the grammar stays the same.
- **SFX:** an air whoosh or fabric "fwump" peaking on the covered frame (C or C+1), plus an optional light tap (`pop_02_bubble_a`) when the close-up sharpens. Alternatively, put the covered frame on a downbeat and let the kick do the work.
- **Limit:** 0-1 per reel as a stand-alone move, or as the frame-fill variant of the push slot.
- **Avoid**
  - A partial cover with readable background (the jump shows).
  - A covered or black screen held for 4 f or more.
  - Occluder colour or brightness that doesn't match.
  - A reveal moving the opposite way.
  - A staged palm.
  - Stacking it with a full zoom-through on the same cut.

### 2.4 Spin / roll: only on a real rotation [C]
- **When:** a real rotation in the footage (a bottle twist, a body turn) at a section boundary or the finale. For a generic "camera turn" feel, use the 2-4 degree roll on the whip instead.
- **Params**
  - 8-12 f, the same rotation direction in both halves, pivot on the subject.
  - OUT in-cubic, IN out-expo, with velocity matched at C.
  - A micro-roll of 20-30 degrees out and back. Full 180-360 degree spins only under heavy blur. Rotational shutter 0.5-1.0 f.
  - **Corner coverage on 9:16:** s(θ) = cos θ + (H/W) sin θ. That is 1.06 at 2°, 1.09 at 3°, 1.15 at 5°, 1.29 at 10°, 1.55 at 20°, 1.76 at 30° and 1.96 at 45°. [FP] Either scale up to s(θ), which spends the e budget, or accept mirror fill only on frames with rotational blur of at least 0.75 f. A 30° spin with zoom 1.3 shows mirrored corners.
- **SFX:** a doppler whirl, 10-15 f, peaking at C (`whoosh_06_synth`).
- **Limit:** 0-1 per reel.
- **Avoid**
  - Spin, cube, flip or page-curl presets on footage that doesn't rotate.
  - Halves spinning in opposite directions.
  - Mirrored faces or black corners.
  - Longer than 0.5 s.
  - Text spinning with the shot.

### 2.5 Match cut on action: the default invisible cut [M]
- **When:** the same action is visible on both sides of the cut (lifting the bottle, stepping in, turning, reaching, opening the cap), or a wide take cuts to a tighter one of the same gesture.
- **Params**
  - Cut 2-4 f after the movement starts, while it is clearly under way; never after it ends.
  - At least 4-6 f of motion must continue after the cut.
  - The object keeps its screen position (+/-10% of W) and its direction.
  - Never repeat action. A small gap of 0-6 f is fine.
    - Hecht & Kalkofen 2009 found a mean preferred gap of 182 ms, but with an SD of 797 ms, only 8 observers and "remarkable tolerance". That supports "gap rather than overlap", not a precise number.
    - The paper reports a larger gap when the next shot is wider.
  - Music and room tone stay continuous; the voice may lead or trail by 3-8 f.
- **SFX:** none. Use real foley only (a step, a bottle clack).
- **Limit:** as often as the footage allows; most non-transition cuts, typically 4-10 per 30 s.
- **Avoid**
  - Repeated action (stutter).
  - Reversed motion or swapped hands.
  - The object jumping across the screen.
  - A cut on a dead frame after the gesture.
  - An audio gap or room-tone change.
  - Any whoosh on an invisible cut.

### 2.6 Punch-in on the stressed word (hold it, don't blip it) [C]
- **When**
  - The onset of a stressed word, the product name, a number or a turn ("але", "і ось"), found from words.json plus the prosodic peak, at -2 to 0 f.
  - A sentence start after a jump cut.
  - Any on-camera stretch longer than about 3 s with no other change.
- **Params**
  - Scale 1.12-1.18 over the current framing; 1.10 is the floor for it to read as deliberate.
  - Either a hard step on the word onset, or a 3-4 f out-expo "snap" with a 0.5 f shutter.
  - Hold to the end of the thought: at least 30 f, typically 45-120 f. Release only at the next cut. If a release inside the shot is unavoidable, use 8-12 f of in-out-cubic inside a pause.
  - **Anchor-preserving centre:** c = a - (p - (W/2, H/2)) / s, where a is the eye point in source pixels and p is its current screen position, frozen when the punch starts. The eye line stays at y 640-760.
  - **Budget:** punches multiply the current framing. B framing at 1.15 x a 1.15 punch = 1.32, which is over the e limit. On 1080 intermediates, punch only from A framing, or switch A→B instead. 1.25-1.35 needs the 4K source. [FP]
- **SFX:** usually none. On the single biggest line, a soft tick or pop 20-24 LU under (`click_01_tick`, `pop_04_light`). Never a whoosh.
- **Limit:** 3-6 per 30 s of on-camera talk, at most one per sentence; about 1 per product line in the lineup reel.
- **Avoid**
  - In-out blips (the draft's 1.06 with 0.10 s in and 0.15 s out reads as a twitch).
  - Steps under 10%.
  - Landing mid-word or on a breath.
  - Re-centring the face to frame centre (the head slides).
  - A fixed interval.
  - Cropping the bottle.
  - e above 1.2 (the eyes go soft).

### 2.7 Jump-cut zoom alternation (A/B framing) and dead-air trim [C]
- **When:** silences longer than 12-15 f inside a sentence, fillers, restarts, take heads and tails, and any cut where both sides share the same setup and background.
- **Params**
  - **Trim:**
    - Cut silences longer than 0.4-0.5 s.
    - Keep 3-5 f before a take's first word and 2-4 f after its last word; never zero.
    - Cut on word boundaries with a 2 f (66 ms) audio crossfade.
    - Keep an 8-15 f pause after a punchline or key claim.
  - **Framing:**
    - A = 1.00 and B = 1.12-1.18, as a hard step exactly at the cut (0 animation frames), anchor-preserving on the eyes.
    - Switch every 2nd or 3rd cut, with irregular shot lengths.
    - Consecutive same-setup framings must differ by at least 10% in scale or 55-85 px of reframe; otherwise don't cut there.
    - No settle and no push reset on these cuts.
    - A 2-4 f morph or smooth cut is allowed only if head displacement is under about 2% of W.
- **SFX:** none. A whoosh on a jump cut advertises the edit.
- **Limit:** trim every take. Framing switches on most same-setup cuts, about 4-8 per 30 s.
- **Avoid**
  - The same scale on both sides (the head teleports).
  - 4-7% steps (the current draft).
  - A mechanical A/B/A/B pattern with equal shot lengths.
  - Removing every breath.
  - Clipped consonants.
  - Cutting the pause after the punchline.

### 2.8 Slow push (constant-velocity creep) [O]
- **When:** a shot of 2 s or more with no other camera event: a sincere or benefit line, or a product close-up under voice-over.
- **Params**
  - 1.0-2.0% per second on talking shots; 2% per second or less during a label read (for example 1.00 → 1.04 over 2.5 s).
  - Constant velocity from the shot's first frame, with no ease-in after a cut. Use a 6-10 f sine ease-out only if the shot ends on a hold.
  - Never one in-out-cubic stretched over the whole take: it gives near-zero speed at both cuts and a surge in the middle.
  - Anchor on the eyes or the label. Never reverse inside a shot.
  - On a same-setup cut, either carry the scale across or step 10% or more.
- **SFX:** none.
- **Limit:** 30-60% of held shots; skip shots that already have a punch, a gesture push or real hand-held motion. A creep does not count as a pattern interrupt.
- **Avoid**
  - Alternating push-in and pull-out across consecutive shots (pumping).
  - The identical drift on every shot (Ken Burns slideshow).
  - Faster than about 3% per second (it reads as an intended zoom).
  - Running under a whip or zoom-through (doubled motion).
  - Layering it on real hand-held movement.

### 2.9 Cut-in settle (restricted) [O]
- **When:** only a hard cut into a new setup (the next product's walk-in, B-roll, a music insert) where nothing else moves in the first 6 f. Never on same-setup jump cuts, and never after a designed transition.
- **Params**
  - Prefer a push-in settle: 1.00 → 1.04-1.05 with out-expo over 8 f, then continuing as the shot's creep.
  - A zoom-out settle (1.06-1.08 → 1.00, out-expo, 6-8 f) is allowed only if the shot then holds or keeps pulling out.
  - Vary the amount by 2-3% between uses.
- **Limit:** 2-4 per 30 s.
- **Avoid**
  - A zoom-out settle on every cut plus a push-in (0.2-0.5 Hz pumping, which is what the current draft does).
  - An identical settle every time.
  - Longer than 12 f (floaty).
  - Overshoot or bounce on a talking head.

### 2.10 Speed ramp, speed-up only [C]
- **When**
  - Walking in, reaching for or picking up the bottle, turning, or the last 4-6 f before a whip or push, as long as there is no speech under it.
  - Start every product block mid-stride or 8-12 f before the first word.
- **Params**
  - 1.5-2.5x on the travel portion, 1 s or less of output.
  - Ramp back to 1.0x over 4-6 f with in-out (bezier) easing; normal speed holds for at least 4-6 f before the first word.
  - Above 2x, use nearest frames or a 2-frame blend.
  - **Slow motion:** never below about 0.7x from 30 fps sources unless you use RIFE-class interpolation and check the result for artefacts. ffmpeg minterpolate breaks on hair, fingers and bottle edges. Check the capture fps first; 35-50% speed is only for footage shot at 60 fps or more.
- **SFX:** mute the production audio in the ramped part and let the music carry it. Optionally add a soft air whoosh peaking where speed returns to 1.0x.
- **Limit:** one per walk-in (up to 4 in the lineup reel), otherwise 0-2 per 30 s.
- **Avoid**
  - Ramped speech (chipmunk voice, lip desync).
  - 30 fps footage slowed to 25-50% (judder or ghosting).
  - Every clip ramped (velocity-template look).
  - Un-eased speed steps.
  - A ramp that ends on the first syllable.

### 2.11 Product close-up read-hold (hand-held plus voice-over J-cut) [O; product and USP lift is M]
- **When:** every hand-held close-up carrying the voice-over line that names the product or its benefit.
- **Params**
  - Close-up length 45-75 f. The label stays steady for at least 45-60 f: creep of 2% per second or less, no blur, shake of 2 px or less.
  - Partial stabilisation: remove jitter above about 2 Hz and keep the slow hand drift. A full lock-off looks floaty, and 2D stabilisation can't fix rolling-shutter wobble. Crop 1.06 or less.
  - The voice-over starts 4-8 f before C (J-cut), or lands 3-6 f before the product name.
  - The product named in the voice-over is the one on screen.
- **SFX:** only the landing thump at C and the callout pop. Product foley (cap click, pump) at 20-24 LU under the voice-over if it is clean. Nothing during the read.
- **Evidence:** in Meta/Toluna 2024 (100 Reels ads, correlational, commissioned by Meta), showing the product more than once gave 2.7x the odds of a top-20% purchase-intent ad, and product plus USP gave 5.3x.
- **Avoid**
  - Cutting away within 1 s.
  - Zoom, shake or flash during the read.
  - The name popping on the cut frame.
  - Uncorrected jitter, or floaty over-stabilisation.
  - A voice-over describing another product.
  - Music louder than the voice-over.

### 2.12 Hero product beat: masked light sweep, optional freeze with flash entry [O]
- **When:** the hero (or last) product's sharpest close-up frame with the label facing the camera (maximum Laplacian variance in the bottle box), or the final lineup frame.
- **Params**
  - **Light sweep**
    - A soft white band 25-35% of the bottle's width, angled 20-35 degrees, with about 20 px of feather.
    - Screen-blended at 50-70% and masked to the bottle silhouette.
    - It crosses in 12-20 f with in-out easing. Ledet's 1-2 s is for logos and too slow here.
  - **Glint (optional):** a 4-point star of 40-70 px at the cap or shoulder, scaling 0 → 1 → 0 over 8-10 f.
  - **Freeze (optional):** 15-24 f on a sharp frame (30-36 f at the reel's end) with a 1.00 → 1.03 creep during it. It enters with a flash/exposure pop plus a shutter sound.
  - **Stacking cap:** at most 2 visual accents plus 1 SFX layer at once.
- **SFX:** either `camera_shutter_01` on the flash frame, or `shimmer_sparkle_whoosh` timed to the band crossing the label, at 14-18 LU under. Not both plus a chime.
- **Limit:** 1 per reel; 2 at most if the opening product also gets a light version.
- **Avoid**
  - An unmasked sweep over the hand and background (reads as a filter).
  - A sweep slower than 1 s or above 80% opacity.
  - Freezing a motion-blurred frame.
  - A freeze longer than 1.5 s mid-reel.
  - The full stack (flash, shake, sparkle, sweep) on every product.
  - Full-frame glitter.

### 2.13 Flash / exposure pop [C]
- **When:** the hero freeze entry, the start of the final lineup, or a strong music drop. Never on a routine cut.
- **Params**
  - An additive exposure lift of about +1 to +1.5 EV (roughly a 0.5-0.8 white mix), peaking on a single frame (C) and decaying over 3-6 f with a quadratic falloff.
  - 100% white for 3 f or more reads as a render glitch.
  - At most 3 flashes in any 1 s (WCAG 2.3.1) [M]; in practice keep them at least 1 s apart.
- **SFX:** a camera shutter or short flash "pop" on the peak frame.
- **Limit:** 1-2 per 30 s.
- **Avoid**
  - A flash on every cut or every product (strobe, accessibility risk).
  - Coloured lens-flare presets.
  - Flash stacked with shake and glitch.
  - A long full-white hold.

### 2.14 Micro shake

**Impact shake** [C]
- **When:** an audible transient (thump, kick, drop) or a visible contact. No hit, no shake.
- **Params**
  - 6-10 f. Translation 8-16 px, rotation 0.6 degrees or less, exponential decay with a time constant of about 3 f.
  - Use decaying noise at 6-12 Hz with a random phase per axis. 30 fps can't show anything above 15 Hz, and a 15 Hz sine that starts on a frame is zero on every frame. [FP]
  - Overscale = 1 + 2 x amp / W + 0.031 x deg (about 1.03-1.05). Shutter 0.5 f. Captions stay screen-locked.
- **SFX:** the hit itself, on frame 0 of the shake.
- **Limit:** 0-2 per 30 s in beauty reels.
- **Avoid**
  - Shaking during speech or under captions.
  - Shaking a label that is being read.
  - Longer than 0.5 s.
  - A continuous wiggle or a periodic sine.
  - 20-40 px at 1.5 degrees (too violent for soft beauty).

**Micro handheld drift** (a brand-level switch) [O]
- **When:** tripod talking takes of 3 s or more, if the brand wants the hand-held UGC feel. Never on the hand-held close-ups.
- **Params:** smoothed noise with 2-3 octaves and energy at 1-4 Hz; 2-5 px RMS; 0.05-0.2 degrees; 1.01-1.02 headroom; no component below 0.5 Hz larger than about 5 px. Apply it to the whole talking section or not at all.
- **Avoid:** a sine wobble, a large slow sway, layering it on real hand-held footage, captions that jitter, or a crop of 1.3x or tighter.

### 2.15 Text entrance tied to motion: product name and benefit callout [C; USP lift M]
- **When:** the voice-over or line names the product or its benefit, normally during the close-up.
- **Params**
  - **Placement:** beside the bottle on its emptier side, aligned with the label or shoulder, 30-60 px from the bottle edge; never over the label or face; inside the safe-zone profile (section 4).
  - **Size:** name 64-84 px in the brand font; benefit of 4 words or fewer at 40-52 px.
  - **Timing tied to motion**
    - Text never animates during the camera's peak.
    - It enters 6-15 f after C (once the landing settles, never on the cut frame) and 0-3 f before the word is spoken.
    - Pop: scale 0.85 → 1.04 → 1.00 over 8-10 f, with a 1-2 f per-letter stagger.
  - **Hold:** max(0.8 s, characters/15 + 0.3 s). About 17 cps is the Cyrillic adult limit in Netflix's Russian guide.
  - **Exit:** 4-6 f before the next transition, or ride the transition with its shot (the renderer moves overlay text with the picture during transitions).
  - **Consistency:** same position, size, animation and SFX for every product; only the product's accent colour changes.
  - The callout may be world-locked to the tracked bottle; subtitles stay screen-locked.
- **SFX:** `pop_04_light` at 20-23 LU under, on the name. Nothing, or a faint tick, on the benefit.
- **Limit:** one name-plus-benefit callout per product.
- **Avoid**
  - Text over the label, the face, the bottom caption/CTA band or the right-hand button rail.
  - Fonts or positions changing between products.
  - A benefit longer than 6 words.
  - Text arriving after the line is spoken, or held under 0.8 s.
  - Captions naming a different product from the one on screen.

### 2.16 Beat sync [C; endpoint-on-beat is M]
- **When:** there is a music bed and the cut is free to move: product changes, the hook teaser, the ending, and transitions not pinned to a word.
- **Params**
  - Tempo 100-128 bpm. One 4/4 bar = 7200/bpm frames (120 bpm: beat 15 f, bar 60 f; 105 bpm: bar 68.6 f).
  - The picture cut lands 0-1 f before the beat.
  - Product changes go on bar downbeats. Transitions go on beats only if the gesture timing allows; the gesture frame wins, so slip the music instead.
  - Dialogue cuts follow words; then slide the music start so the single most important cut hits a beat.
  - Align movement endpoints (the bottle stopping) to beats (Takehana 2019).
- **SFX:** the music supplies the accent; any SFX on that cut peaks on the beat frame.
- **Limit:** every music-driven cut, about 4-8 per 30 s.
- **Avoid**
  - Cutting on every beat in a talking reel.
  - Cuts 2-4 f late.
  - Clipping words to hit a beat.
  - Dialogue shots under 0.5 s.
  - Every cut on the same audio spike (templated, per CapCut June 2026).

### 2.17 Beat micro-bounce (drops and lists only) [O]
- **When:** a music drop, or 2-4 rhythmic items with no speech over them (the teaser hook, the lineup ending).
- **Params:** 1.00 → 1.04-1.06 in 2 f out-expo, back over 6-8 f in-out, on at most 2-4 consecutive downbeats, anchored on the subject.
- **Limit:** 0-1 burst per 30 s.
- **Avoid:** pulsing a whole section, bouncing under speech, or bouncing on top of a punch or a crop of 1.3x or tighter.

### 2.18 Motion blur from a true sub-frame shutter [C]
- **When:** any camera move faster than about 3% scale (0.03 in log-scale) or 20 px per frame.
- **Params**
  - Average N samples of the camera path across the shutter interval.
  - Shutter: 0.5 f for snaps, shakes and gesture pushes; 0.5-0.75 f for whips and zoom-throughs (1.0 f only if the move is under 8 f in total); 0 for creeps.
  - Streak = speed x shutter, so blur fades automatically at the ends of an eased move.
  - Directional (pan), radial (zoom) and rotational streaks all come out of sampling the affine path; no separate filters are needed.
  - Never add a fixed radial blur on top. The source's own subject blur (phone shutter of about 1/50-1/100 s) adds to it.
- **Avoid:** blur on slow moves, blur lingering past the landing, a blurred label during the read-hold, or a flat 2D Gaussian.

### 2.19 SFX palette, sync and levels [M sync; C palette]

| Event | Family | Library samples (rotate) | Peak | Level vs dialogue |
|---|---|---|---|---|
| Swipe-whip | short swish 8-15 f | whoosh_quick_03_swish, whoosh_soft_02_wind_swoosh, whoosh_soft_01_air_sweep | C or C+1 | -8 to -12 LU (in a gap) |
| Zoom-through rush | air swell / reverse whoosh | whoosh_05_swipe_zoom, whoosh_04_air_into_cut | stops dead at C | -10 to -14 LU |
| Zoom-through landing | low thump below 100 Hz | bass_thump_01_sub, bass_thump_02_synth, punch_soft_impact | C or C+1 | -10 to -14 LU; music dipped 3-4 dB |
| Frame-fill | air / fabric fwump | whoosh_04_air_into_cut | covered frame | -10 to -14 LU |
| Spin | doppler whirl | whoosh_06_synth | C | -10 to -14 LU |
| Callout name | pop | pop_04_light, pop_02_bubble_a, pop_03_bubble_b | text entrance | -20 to -23 LU |
| Biggest punch only | tick | click_01_tick | word onset | -20 to -24 LU |
| Hero | shutter or shimmer | camera_shutter_01/02, shimmer_sparkle_whoosh, sparkle_hit_fairy | flash frame / band on label | -14 to -18 LU |
| Impact shake | the hit | bass_thump_* | shake frame 0 | -10 to -14 LU |
| CTA | soft chime | ding_02_soft_chime | CTA text | about -18 LU [O] |
| Match / jump cuts, punches, creeps | none (real foley only) | | | |

**Rules**
- Align the sample's peak (`peak_at`), not the file start.
- At 30 fps, the allowed peak window is C-1 to C+3. ITU-R BT.1359 puts the detectability limits at +45 ms audio lead and -125 ms lag; 2 f early is a fail.
- The audible build never starts before the visual move. A riser stops dead at C. The tail may decay past the move.
- One sound per event; two layers at most (rush plus hit).
- Never use the same whoosh at the same level on every cut (the yocase_line draft does this).
- The library has only 2-3 samples per family. For a 4th use, vary gain by +/-2 dB or pitch by +/-1 semitone. [O]
- Never in brand reels: record_scratch_*, cartoon_*, boing_*, tada_brass, cha_ching_register, digital static. [O]

### 2.20 Mix (voice first) [C; speech+music lift M]
- **Dialogue:** -16 to -14 LUFS short-term.
- **Music:** 12-18 LU under the dialogue while she speaks; up 4-6 dB in non-speech gaps (whips, hook, ending).
- **Ducking:** use keyframed ducking that starts 100-200 ms before the first word with a 300-500 ms release. audio.py's sidechain is off by default because it pumped.
- **Continuity:** room tone continuous under every edit; 2 f crossfades on all speech cuts.
- **Master:** about -14 LUFS integrated, true peak -1 dBTP.
- **Ending:** end on a musical phrase or downbeat, or fade over 0.5-0.8 s.
- **Evidence:** speech plus music gave 2.0x the odds of a top-20% ad for brand interest (Meta/Toluna).

### 2.21 Shot matching [C]
- Per-take `gains` match the close-up to the medium shot on a neutral or skin patch: skin luma within +/-5% and no visible white-balance shift.
- A light shared contrast curve. No heavy LUTs, crushed blacks or vignettes; keep `grade.vignette` at 0-0.05.
- A push-mode whip needs both shots' luma within about 10%.
- Never beautify the hair-result shot (claims risk).

### 2.22 Never in a 2026 beauty reel [C]
- Glitch / RGB split: 0. At most one, only for a deliberate "error" or comparison beat, 3-6 f.
- Cube, flip, page-curl and 3D-rotate presets: 0.
- Full-frame glitter, lens-flare or sparkle overlays: 0. At most one cluster of 2-3 code-drawn stars, kept off the label.
- Staged hand-cover reveals: 0.
- Unmodified phone mock-up or freeze-outline templates: 0-1, and only with clean mattes.
- More than 2 designed transition types in one reel: no.

---

## 3. Format grammar: "product lineup"

### 3.1 Reel skeleton (example at about 105 bpm, bar ≈ 69 f, block = 3 bars ≈ 206 f)

| Section | Frames | Seconds | Content |
|---|---|---|---|
| Hook | 0-68 (1 bar) | 0-2.3 | Motion plus product on frame 0 (see 3.5). Hook text by f3. |
| Product 1 | 69-274 | 2.3-9.1 | Full intensity |
| Product 2 | 275-480 | 9.1-16.0 | About 20% lighter |
| Product 3 | 481-686 | 16.0-22.9 | About 20% lighter |
| Product 4 / hero | 687-892 | 22.9-29.7 | Full plus hero accent; music lift or riser into it |
| Ending | 893-995 | 29.7-33.2 | Recap plus CTA; loop frame |

- **Fitting blocks to the music:** choose the tempo so that 3 bars ≈ one block, i.e. bpm ≈ 21600 / block frames (195 f → 111 bpm, 225 f → 96 bpm).
- **With the 120 bpm house track:** bar = 60 f. Use 3.5-bar blocks (210 f) with product changes on bar or half-bar downbeats, or 3-bar blocks (180 f) with a 60 f close-up.
- **Length:** a 4-product lineup should run 21-34 s. TikTok's 2021 machine-learning analysis reported +280% conversion in that window (correlational, auction ads). [M]

### 3.2 Block template (frames relative to the block's start; the start is a bar downbeat)

| rel f | Beat | Picture / camera | Sound |
|---|---|---|---|
| 0 | Hard cut, 0-1 f before the downbeat | Walk-in mid-stride at 1.6-2.0x. Creep starts on frame 1. Optional push-in settle 1.00 → 1.04 over 8 f. | Music. Production audio muted under the ramp. |
| 4-10 | Ramp back to 1.0x over 4-6 f, in-out | | Optional soft air whoosh peaking at 1.0x |
| ≤ 18 | First word (at least 5 f after reaching 1.0x) | A framing 1.00; eye line y 630-770; face x 380-620 | Voice; music 12-18 LU under |
| name onset (about 30-45) | Punch | 1.15 hard step, anchored on the eyes, held to the end of the line (at least 30 f) | None |
| about 96-108, C_sweep about 100 | Sweep slot | Swipe-whip with the hand: preset B (OUT 4 / IN 9) for products 1 and 4, preset A (5/5) for products 2 and 3. Land on B framing 1.12-1.15 anchored on the bottle; dead frames dropped. | Swish peak at C or C+1 |
| 109-123 | Calm (at least 15 f) | B framing holds while she starts the push | |
| about 122-126 | | | Voice-over starts (J-cut, 4-8 f before C_push) |
| 124-129, C_push about 130 | Push slot | Zoom-through: OUT 6 f, log-scale in-cubic to s_out, centred on the tracked label; cut on maximum bottle size | Swell from C-6, stopping dead at C |
| 130-138 | Landing | Continuous-in 1.00 → 1.10, out-expo over 9 f | Thump at C or C+1; music dipped 3-4 dB |
| 138-142 | Callout | Name pops, then the benefit (4 words or fewer) | Pop on the name |
| 139-205 | Read-hold | Creep of 2% per second or less; stabilised; label steady for at least 45-60 f | Voice-over; optional product foley |
| about 200 | | Callout exits | |
| 206 | Next block | Hard cut on the next bar downbeat | |

### 3.3 Per-block decision rules
1. **Spacing rule:** C_push - C_sweep ≥ IN_whip + 15 + OUT_push, which comes to about 25-30 f. If it is short, use preset A and OUT 5 f. If it is still under about 25 f, downgrade the sweep to an A→B hard punch cut on its peak frame. [O]
2. **Weak sweep** (under about 25 px/f, or travel under 25% of W in 10 f): an A→B punch cut on the sweep's peak frame. Never use a half-strength whip.
3. **Bottle width b at C_push**
   - b ≥ 0.6, or sharpness collapses: frame-fill. In a reel that uses the zoom-through, run it as a zoom-through with s_out of 1.15 or less.
   - b < 0.2: a hard punch to the bottle plus a plain cut.
4. **Luma across the whip seam** differs by more than about 10%: use the single-shot whip or a 2-3 f crossfade inside the peak blur.
5. **Mirrored or smeared frames** readable for more than 3 f: shorten the transition. Never lengthen it.

### 3.4 Energy curve (keep the structure fixed and vary the intensity)

| | Product 1 | Products 2-3 | Product 4 / hero |
|---|---|---|---|
| Whip | Preset B, 3° roll, optional 2-4% overshoot | Preset A, no roll (or a punch cut if the sweep is weak) | Preset B, 3° roll |
| Zoom-through s_out | From the size match (about 1.5-1.7) | About 20% less log-travel (for example 1.5 → 1.38) | Full |
| Landing | 1.00 → 1.10 | 1.00 → 1.08 | 1.00 → 1.12 |
| Accent | None (or a light hero version if the brand wants it) | None | Masked light sweep; optional 15-24 f freeze with flash entry and shutter |
| Music | | | Lift or riser into the block |

- All blocks stay within +/-10% of each other's length (brand parity).
- The hero product goes last by default. If the brand insists on hero first, it gets the accent and product 4 gets the light version. [O]

### 3.5 Hook (one option per render; render the alternatives as variants) [M for timing; options are O]
- **(A) Cold open (default):** the reel's best push-to-zoom-through beat (about 1.5-2 s), then a hard cut to product 1. Her first word comes within 0.3 s.
- **(B) Teaser:** 4 bottles at 6-8 f each, cut on beats, with an optional micro-bounce, ending on product 1. Here the hook text replaces speech, and her first word comes by about 1.5 s.
- **(C) Phone mock-up pop-out** (a 2025-26 trend): only with clean hair and finger mattes, and held 3 s or less.
- **Always**
  - No logo, fade or walk-in.
  - Hook text of 7 words or fewer by frame 3, at y 270-700, not over the face.
  - Product on screen within 3 s; brand plus main message within 5 s (1.7x top-20% purchase-intent odds, Meta/Toluna).
  - Music starts on a downbeat at frame 0.
  - One sound for the hook's main move; don't whoosh every teaser cut.

### 3.6 Ending (2.5-3.5 s) [M]
- All bottles together, or a 4-way recap at 6-8 f each, then hold. This re-shows every product (2.7x odds for showing the product more than once).
- The CTA is both spoken and on screen, 5 words or fewer, visible for at least 2 s before the end, with the same pop grammar as the callouts. The SFX is `ding_02_soft_chime`.
- The brand is visible at least twice but for no more than 25% of the runtime (4.8x odds in the direct-response subset).
- For organic posts, make the last frame compositionally close to frame 0 so the loop is seamless.
- End on a music downbeat. No logo end card, and no new product at the end.

### 3.7 Budget for a 30-34 s lineup
- 4 zoom-throughs, 2-4 whips, 3-5 punches, 1-2 flashes (hero and/or the lineup start), 0-1 shake, 1 hero light sweep, 0-1 bounce burst, 4 walk-in ramps, about 12-15 cuts.
- That makes about 6-8 designed transitions, all motivated by on-screen motion. This is the difference between "edited" and "preset demo reel".

---

## 4. Universal grammar for any talking reel

**Order of work**
1. Trim dead air.
2. Pick takes.
3. Place match cuts.
4. Apply A/B framing on same-setup cuts.
5. Add punches on stressed words.
6. Add designed transitions, only on named motions.
7. Add creeps on the remaining held shots.
8. Run the pattern-interrupt scan.
9. Add text.
10. Add SFX.
11. Mix.
12. Lint (see 5.6).

**Cadence** [C, partly M]
- 8-15 cuts per 30 s.
- A visual change every 1.5-4 s at varied intervals; nothing static for more than 3-4 s (creeps don't count).
- The first change comes by 1.0-1.5 s.
- About 0.33-0.37 cuts/s is a reported talking-head norm (Dost & Huang 2026, not independently verified).
- Related changes (a punch, an A/B switch) can come every 1.5-3 s. A cut to new content needs at least 1.5-2 s on screen. Fast, unrelated cutting hurts encoding (Lang, LC4MP).

**Pattern-interrupt fill order** (when a span exceeds 3-4 s)
1. New content (a close-up or insert).
2. An A/B switch.
3. A punch on the next stressed word.
4. A text pop.
5. A creep.

Use an effect only when no content change exists. The hook is the densest section and the CTA the lightest.

**Speech takes precedence**
- Camera events are placed from words.json on word boundaries.
- Never ramp speech.
- Speed is back to 1.0x at least 4-6 f before a word.
- Audio stays continuous: music and room tone run across every cut, with J/L-cuts of 3-8 f.

**Safe zone** (choose one profile per reel)
- **Organic:** critical text and labels inside x 128-952, y 250-1480 (Instagram crops ~100 px per side on 19.5:9 / 20:9 phones; the right rail starts near x 850 from y 1050).
- **Possible paid or partnership use:** Meta Reels-ads margins of 14% top, 35% bottom, 6% sides, i.e. y 270-1248. These figures are as reported by adnova; the guide doesn't link Meta's own spec.
- **Faces:** eye line y 630-770; face centre x 380-620, biased away from the right-hand button rail.

**When not to add an effect**
- You can't name the motion that motivates it: use a hard cut, match cut or A/B step.
- Another event move ended less than 15 f ago.
- During a label read or callout read, or while captions carry a key line: no shake, bounce, flash or zoom.
- On a same-setup jump cut: no whoosh, no settle, no animation.
- It would push e above 1.2 on a held frame.
- The cut already brings new content; the new shot is the interrupt.
- On sincere or emotional lines: creep only.
- The gesture is weak: never use a half-strength whip.
- It would add a third designed transition type.
- A content change is available instead.
- It is on the never-list (2.22).

---

## 5. Implementation priorities (deterministic renderer, at most two source frames per output frame)

### 5.1 Ranked by impact and effort

The "current state" column was written against the engine before the first fixes; the **Done** notes below
each table row mark what has landed since (2026-10-10). The script syntax for every effect is in SKILL.md.

| # | Change | Impact | Effort | Current state | To do |
|---|---|---|---|---|---|
| 1 | Swipe-whip correctness | Very high (developer fix #1) | Low | `push` has separate out/in frames, roll with coverage, and a two-layer composite. **Done:** `ease_in: "expo"` (preset B); lint_edit.py checks the speed match. | Add per-half easing (out-expo IN). Validate that the two peak speeds are within 20%; until then, use equal halves. Add a single-shot mirror mode plus a luma test. Add optional overshoot. Add same-take landing (EDL drop plus B framing anchored on the bottle). |
| 2 | Zoom-through correctness | Very high (developer fix #2) | Medium | `zoom_through` interpolates in log space. The target is a fixed point (centre lerps by min(1, 3e)). **Done:** continuous-in = `land: 1.0` + the close-up's `push_takes` `ease: "expo"`. | Track the target per frame. Compute s_out from bottle widths (clamped 1.25-1.8). Add `land_mode` = continuous_in (default) / impact / kolder. Check the size and centre continuity rule at C. |
| 3 | Scale grammar | High (cures "dead" and "twitchy") | Low | **Done:** `anchor: true` punches, `ease: "linear"` creeps, `push_takes` target [x, y]; `cut_in` is simply left out. lint_edit.py flags blips, pumping, fast creeps. | Anchor-preserving punches, step-and-hold of at least 1.12. A/B framing with at least 10% difference. Constant-velocity creep. Restrict `cut_in` and add a push-in settle. |
| 4 | Trigger detection | High (stops the LLM guessing frames) | Medium | motion.py finds sweeps (p95 Farneback x-flow in the person matte above 28 px/f for 3 f; peak) and to_lens events (similarity growth above 1.012 per frame for 3 f; stop point). | See 5.4. |
| 5 | SFX palette and levels | High per unit of effort | Low | SFX are placed by `peak_at`; peaks are stored in credits_sfx.json. | Enforce one family per event, rotation, and levels in LU (gain_db = dialogue LUFS - target LU - the sample's own short-term LUFS). Window check C-1 to C+3. |
| 6 | Callouts tied to C | Medium-high | Low-medium | overlay.html already does per-letter animation; text rides transitions via `ovm`. | Callout type with anchor = bottle box, entrance C+6 to C+15, the hold formula, exit before the next transition. |
| 7 | Beat grid | Medium | Low | **Done:** beats.py finds the beat phase (BPM from the filename) and `fit` / `snap` move cuts onto beats within per-shot frame budgets. Downbeats (bar 1) are still unknown. | Store BPM plus the first-downbeat offset per music file (hand-annotated once, or librosa beat_track plus madmom downbeats). Snap free cuts 0-1 f before beats. |
| 8 | 4K sampling path | Medium (sharp held punches above 1.2, s_out above 1.6) | Medium-high | ingest.py converts everything to 1080x1920 before the camera pass. | Keep a 2160x3840 proxy. In video_pass, sample through the same affine with the matrix scaled by 0.5, plus a prefilter (Gaussian sigma about 0.5 x minification), or render at 2x and area-downscale (hair aliases). |
| 9 | Speed ramps in the EDL | Medium | Medium | Not supported. | Per-segment speed curves; nearest frame below 2x, 2-frame blend above (outside two-shot transitions only). |
| 10 | Close-up partial stabilisation | Medium (read-hold) | Medium | None. | Track the bottle; low-pass the path to remove jitter above 2 Hz; crop 1.06 or less. |
| 11 | Shake and spin fixes | Low-medium | Trivial | Shakes are sines at 15 Hz by default (aliases). Spin applies rotation without corner coverage. | Decaying noise at 6-12 Hz with random phase. Apply s(θ), or gate mirror fill on rotational blur of at least 0.75 f. |
| 12 | Hero light sweep and glint | Medium (once per reel) | Medium-high | None. | Needs a bottle silhouette matte (SAM2-class); the sweep is a code-drawn screen-blend inside the matte. |
| 13 | Phone pop-out hook, freeze-outline | Low | High | None. | Defer; needs clean hand and hair mattes. |

**Script fields:** see the effect table in SKILL.md (it supersedes the interim mapping that was here).

### 5.2 The two-source-frame budget

| Effect | Source frames per output frame | Notes |
|---|---|---|
| Whip, push mode | 2 (outgoing and incoming), each warped N times for the shutter | The core two-shot case. A 2-3 f crossfade inside the peak blur reuses the same 2 frames. |
| Whip, single-shot | 1, plus mirror fill (BORDER_REFLECT101) | Cut inside the peak-blur frame. |
| Zoom-through (any landing mode) | 1 (outgoing up to C, incoming from C) | Kolder mode uses mirror fill, not a second frame. |
| Frame-fill, spin, punches, A/B, creep, shake, flash, freeze | 1, plus code-drawn overlays | |
| Speed ramp above 2x with blending | 2 frames of the same clip | Forbidden inside a push-mode whip (that would need 3-4 frames); use nearest frames there. |
| Phone pop-out | 1 source frame used twice (screen plus matted cut-out) | |

Anything that would need 3 or more source frames falls back: nearest-frame ramps, single-shot whips, or a hard cut.

### 5.3 Motion blur implementation [FP]
- Keep video_pass's true shutter: sub-sample the camera path (affine per layer) across the shutter and average the warped frames.
- Today N = ceil(corner shift / 4), capped at 24. That is fine but costly. The cheaper floor is N = ceil(streak / 8), minimum 4. Sample spacing above about 10-15 px shows ghost copies on high-contrast edges.
- Measure the streak at the frame corners, so zooms and rolls get enough samples: radial streaks are largest there.
- In push mode, sample both layers at every sub-sample (already done).
- Turn off the separate radial `blur` (on cut_in and punches) whenever shutter sampling is active.
- Shutter by move type: 0.5 for snaps, shakes and gesture pushes; 0.6 for whips and zoom-throughs; 0.75-1.0 for spins (1.0 only for moves under 8 f); 0 for creeps and holds.

### 5.4 Automatic trigger detection
- **Sweep** (extend motion.py)
  - Keep: Farneback flow inside the person matte, p95 horizontal flow above 28 px/f for 3 f or more, C = argmax.
  - Add a travel test: the centroid of the fastest region must cross at least 0.25 W within 10 f.
  - Add a direction-consistency test.
  - Snap C to the word end if C is 2 f or less inside a word (words.json).
  - Add an `ok_whip` flag that applies the spacing rule against the following to_lens event in output time.
  - Report the dead frames between the sweep's end and the push's start, for the same-take drop.
  - Use optical flow, not MediaPipe landmarks, for timing: landmarks drop out on blurred fast frames.
- **Push to the lens** (extend to_lens)
  - Growth is linear: an area growth of 1.5x ≈ 1.22x linear, about 1.014-1.02 per frame over 10-15 f.
  - Add a per-frame bottle box, from an open-vocabulary detector prompted with "bottle" on keyframes plus a tracker, or from the matte component nearest the lens.
  - From the box, emit:
    - b at C;
    - the Laplacian variance inside the box (a drop of more than 50% → frame-fill);
    - frame coverage (90% or more for at least 2 f → frame-fill);
    - the label-centre track, as the zoom target;
    - b_cu from the close-up's first frame, for s_out.
- **Rotation (spin eligibility):** a flow-curl peak inside the bottle box.
- **Hero frame:** maximum Laplacian variance in the bottle box while the box is frontal (stable aspect ratio, or the best label OCR confidence).
- **Whip mode:** the mean luma of the last OUT frame and the first IN frame (after gains) within 10% → push mode allowed.
- **Words:** words.json onsets (already snapped in prep). The stressed word = the RMS or pitch maximum within the clause, preferring product names, numbers and turns ("але", "і ось").
- **Beats:** BPM plus downbeat offset per track; snap free cuts 0-1 f before beats, with product changes on bar downbeats.

### 5.5 Who decides what
- The detector proposes candidates: sweeps, pushes, hero frames, beat grid, stressed words, each with its scores.
- The LLM script picks among the candidates and sets intensity following the energy curve.
- The renderer enforces the hard constraints in 5.6.

### 5.6 Script lint (fail or auto-fix before rendering)
- **Resolution:** e ≤ 1.2 on any frame with streak under 20 px; e ≤ 1.6 everywhere.
- **Transitions**
  - 10-16 f in total; out/in speed mismatch within 20%.
  - Mirrored or smeared frames readable for 3 f or less.
  - At least 15 f between event moves.
  - C_sweep to C_push at least about 25 f.
- **Framing:** same-setup scale steps of at least 10% (or at least 55 px reframe).
- **Punches:** held at least 30 f; no in-out blips.
- **Creeps:** at most 3% per second, and no direction reversal inside a shot.
- **No pumping:** no zoom-out settle followed by a push-in in the same shot.
- **Accent budget:** flashes at least 1 s apart (WCAG: 3 or fewer per second); shakes only on hits; at most 2 designed transition types.
- **SFX:** peaks within C-1 to C+3; builds don't start before their move; no SFX on match cuts, jump cuts or punches (except the one tick); no family repeats the same sample twice in a row.
- **Static spans:** none longer than 4 s without a change.
- **Read-hold:** the label is steady for at least 45 f in every close-up; callouts are inside the safe zone, not over the label or face, and hold at least max(0.8 s, chars/15 + 0.3 s).
- **Speech:** no speech under a speed ramp; 1.0x speed at least 4 f before a word.

---

## 6. Sources

**Measured: studies, standards, platform data**
- Smith & Martin-Portugues Santacreu 2017, motion after the cut and edit blindness: https://eprints.bbk.ac.uk/id/eprint/14904
- Hecht & Kalkofen 2009, gap at action cuts: https://experimental.psychologie.uni-mainz.de/files/2024/06/2009hecht-kalkofen.pdf
- Smith & Henderson 2008, edit blindness: https://doi.org/10.16910/jemr.2.2.6
- ITU-R BT.1359, AV sync thresholds: https://www.itu.int/dms_pubrec/itu-r/rec/bt/R-REC-BT.1359-0-199802-S!!PDF-E.pdf ; summary: https://www.forasoft.com/learn/audio-for-video/articles-audio/lip-sync-itu-r-bt-1359-tolerance-windows
- Takehana et al. 2019, movement endpoints perceived on the beat: https://www.ncbi.nlm.nih.gov/pmc/articles/PMC6711538/
- Diels & Howarth, frequency of visually induced motion sickness: https://repository.lboro.ac.uk/articles/Frequency_characteristics_of_visually_induced_motion_sickness/9346865/files/16955915.pdf
- Wals et al., visual complexity and scene cuts: https://researchportal.bath.ac.uk/en/publications/the-dynamic-effects-of-visual-complexity-and-scene-cuts-on-viewer/
- Lang, LC4MP: https://en.wikipedia.org/wiki/LC4MP
- Dost & Huang 2026, talking-head cut rate (reported, not verified): https://archives.marketing-trends-congress.com/2026/pages/PDF/paper_professor_DOST_HUANG.pdf
- WCAG 2.3.1, three flashes: https://www.w3.org/WAI/WCAG22/Understanding/three-flashes-or-below-threshold.html
- Meta/Toluna Reels study: https://ppc.land/meta-and-toluna-study-finds-emojis-lift-reels-purchase-intent-2-5x/
- TikTok, creative that drives conversions: https://ads.tiktok.com/business/en-US/blog/creative-that-drives-conversions
- TikTok, top-performing ads: https://ads.tiktok.com/business/en-US/blog/creative-best-practices-top-performing-ads
- TikTok, creative best practices: https://ads.tiktok.com/help/article/creative-best-practices
- TikTok Creative Center, beauty and personal care: https://ads.tiktok.com/business/creativecenter/quicktok/online/creative-tips-for-beauty-personal-care/pc/en
- Instagram Skip Rate: https://www.socialsamosa.com/news-2/instagram-retention-chart-skip-rate-new-performance-metrics-reels-9730992
- EyeSee/TikTok: https://www.quirks.com/articles/eyesee-virtual-session-tiktok-creative-that-works-insights-from-eyesee-3m-scotch-brite-and-tiktok
- Netflix Russian timed-text guide (Cyrillic reading speed): https://partnerhelp.netflixstudios.com/hc/en-us/articles/215346638-Russian-Timed-Text-Style-Guide
- Neurensics, focus dip after scene changes (single vendor): https://www.neurensics.com/en/learning-6-3-tips-to-make-sure-your-viewers-stay-focused-during-your-ad

**Transitions: editors' tutorials and trend pieces**
- Miracamp whip: https://www.miracamp.com/learn/premiere-pro/whip-transition
- tutvid whip: https://tutvid.com/premiere-pro/whip-pan-blurring-transition-effect-premiere-pro/
- PremiumBeat whip: https://www.premiumbeat.com/blog/create-whip-pan-using-built-effects-premiere-pro/
- No Film School whip: https://nofilmschool.com/2017/09/5-steps-create-perfect-whip-pan-transition
- Photofocus whip: https://photofocus.com/software/tutorials-software/easy-whip-swish-pan-in-after-effects/
- Sam Kolder zoom (4kshooters): https://www.4kshooters.net/2017/02/18/creating-the-appealing-sam-kolders-smooth-zoom-in-and-zoom-out-transition-effects-in-premiere-pro-cc
- AEJuice zoom blur: https://aejuice.com/blog/how-to-create-a-smooth-zoom-blur-transition-in-after-effects/
- Larry Jordan, scale keyframes: https://larryjordan.com/?p=169842
- Remotion zoom blur: https://remotion.dev/docs/effects/zoom-blur
- nemovideo TikTok transitions: https://www.nemovideo.com/blog/tiktok-transitions-tutorial
- Motion Array zoom transitions: https://motionarray.com/learn/premiere-pro/zoom-transitions-in-premiere-pro/
- tutvid spin: https://tutvid.com/premiere-pro/smooth-spin-radial-blur-transition-premiere-pro/
- AEJuice spin: https://aejuice.com/blog/how-to-do-a-spin-transition-on-after-effects
- No Film School in-camera transitions: https://nofilmschool.com/2017/11/watch-6-creative-transitions-you-can-pull-camera
- journalism.co.uk in-camera transitions: https://www.journalism.co.uk/5-in-camera-video-transitions-to-make-your-social-content-more-engaging/
- CapCut transition trends (June 2026): https://www.capcut.com/create/video-transition-trends-viral-short-form-edits
- Editors Keys, amateur mistakes: https://www.editorskeys.com/blogs/news/5-editing-mistakes-that-make-your-videos-look-amateur-and-how-to-avoid-them
- Vidpros, short-form transitions: https://vidpros.com/best-transitions-for-short-form-videos/
- Match on action: https://howtofilmschool.com/dictionary/match-on-action/
- Picsart pop-out-of-phone trend: https://picsart.com/blog/pop-out-of-phone-trend-tutorial/
- Clipchamp glitch: https://clipchamp.com/ru/blog/add-glitch-effect-videos/

**Camera, talking head, framing**
- 1of10 jump cuts: https://1of10.com/blog/what-is-a-jump-cut/
- async, editing Reels: https://async.com/blog/how-to-edit-instagram-reels/
- FireCut zoom: https://firecut.ai/blog/how-to-zoom-in-on-premiere-pro-a-step-by-step-guide-for-beginners/
- Submagic zoom: https://www.submagic.co/da/blog/how-to-zoom-in-on-premiere-pro
- Vizard, punch-in cycling: https://agent.vizard.ai/how-to/stop-the-punch-ins-cycling-too-fast-in-a-talking-head-edit.html
- PremiumBeat, Resolve smooth cut: https://www.premiumbeat.com/blog/easier-interview-editing-with-davinci-resolves-smooth-cut-transition
- Joseph Nilo zoom guide: https://josephnilo.com/blog/ultimate-guide-to-all-things-zooming-in-premiere-pro/
- Morphic slow zoom: https://morphic.com/ai-glossary/slow-zoom
- Mozaik, motion on clips: https://mozaik.featurebase.app/en/changelog/add-motion-to-any-clip-mag
- StudioBinder, Murch's rule of six: https://www.studiobinder.com/blog/walter-murch-rule-of-six/
- Safe zones: https://adnova.ai/blogs/meta-ad-safe-zones-guide ; https://www.inro.social/tools/instagram-reels-safe-zone-checker ; https://www.remotion.dev/elements/overlays/social-safe-zones/
- Handheld frequency: https://www.dpreview.com/forums/post/54682702
- WebKit, responsive design for motion: https://webkit.org/blog/7551/responsive-design-for-motion/
- CapCut pulse effect: https://www.antwort.net/a/tutorial/so-erstellst-du-einen-pulse-effekt-in-capcut-tutorial.html

**Speed, shake, flash, light, text, sound**
- Speed ramps: https://amateurphotographer.com/video/how-to/what-is-speed-ramping-and-how-do-i-do-it ; https://www.kapwing.com/resources/how-to-use-the-speed-ramp-effect/ ; https://motionarray.com/premiere-pro/premiere-pro-speed-ramping-tutorial/ ; https://www.nemovideo.com/blog/capcut-slow-motion-speed-ramp
- Shake: https://schoolofmotion.com/blog/how-to-simulate-camera-shake-adobe-after-effects ; https://miracamp.com/learn/premiere-pro/camera-shake-effect ; https://cenareo.com/en/blog/tuto-transition-video-tremblement
- Flash: https://www.dvinfo.net/forum/archive/index.php/t-104689.html ; https://forum.shotcut.org/t/whoof-transition-does-it-have-a-proper-name/5047
- Light sweep: https://www.ledet.com/after-effects-tip-of-the-week-create-a-cinematic-light-sweep-on-text/ ; https://www.premiumbeat.com/blog/light-sweep-in-adobe-after-effects-creates-dramatic-effect
- Text pop: https://creativecow.net/?p=224621
- J/L-cuts: https://www.adobe.com/creativecloud/video/discover/j-cut-and-l-cut
- Beat sync: https://www.vegascreativesoftware.info/us/forum/syncing-video-cuts-to-audio-beats--63186 ; https://sonilo.com/blog/guides/how-to-make-video-sync-with-music
- Mix: https://vidpros.com/fix-background-music-too-loud-video/
- Transition SFX: https://morphic.com/resources/sounds/transition-sound-effects
- UGC editing: https://www.usetwirl.com/ugc-diaries/editing-dos-and-don-ts-elevating-your-ugc-content-quality ; https://goprimer.com/blog/7-creative-tactics-tiktok-top-ads

**Unverified or rejected claims (do not cite as fact)**
- Dost & Huang's 0.37 cuts/s: reported only; the PDF was not readable.
- Salminen's 85.2% early exit: not re-checked.
- "Smith 2012: whip pans scatter gaze with a seasick effect": unsupported; the abstract says nothing about whip pans.
- TikTok's "5-10 words per second": ignore it for static text.
- Vendor retention claims ("+38% with 1-2 s cuts", "+35% watch time from transitions"): not traceable to primary data.