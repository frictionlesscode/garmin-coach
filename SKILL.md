---
name: garmin-coach
description: Use this skill whenever the user talks about their training, workouts, recovery, sleep, HRV, stress, weight/body-composition trend, or asks whether to adjust a training or diet plan based on how their body is actually responding -- even if they don't say "Garmin" or name a tool. Trigger on phrases like "how should I train today", "am I recovered enough to lift heavy", "how's my cut going", "log my weight", "did I overdo it this week", "should I take a rest day", or any request to check real training/recovery data against a plan, program, or goal the user has described. This skill explains which garmin-mcp tool answers which question, how to read the returned fields (units, what null means, what each metric actually measures), and how to weigh real data against the user's own stated plan -- it intentionally contains no training philosophy, thresholds, or programming rules of its own.
---

# Garmin Coach

You have access to a garmin-mcp connector exposing real data from the user's Garmin device: activities, sleep, HRV, VO2max, resting heart rate, body battery, stress, HR zones, training load, weight/blood-pressure/hydration trends, and write tools for weight, blood pressure, and hydration. This skill tells you which tool answers which question and how to read what comes back correctly. It does not tell you what "good" training looks like -- that comes from the user.

## The one rule that matters

**The user's plan lives in the conversation, not in this skill.** They'll tell you (now or earlier in the chat) what program they're running, what their diet target is, what "too much" or "not enough" means for them. Your job is to fetch the real data and reason about it *relative to what they told you* -- not to apply a generic fitness philosophy, invent thresholds ("HRV below 30 means rest"), or default to conventional wisdom they never asked for. If they haven't told you their plan and it matters for the answer, ask, or clearly caveat that you're reading the data at face value without a plan to compare it to.

This matters because two people with identical HRV and sleep data might get opposite correct recommendations depending on what they're training for. Don't guess their goals from the data -- get them from the user.

## Which tool answers which question

| User is asking about... | Call | Notes |
|---|---|---|
| "How should I train today?" / recovery check / readiness | `get_readiness()` | Composite snapshot: today's HRV + 7d baseline, resting HR + 7d baseline, last night's sleep score, current body battery, last 3 activities, days since last rest day. **No tool takes a date range** -- it's always "right now." |
| Recent workouts / "what did I do this week" | `get_activities(days, activity_type)` | `activity_type` filters against Garmin's actual type values (e.g. `"strength_training"`, `"running"`) -- unlike Garmin's own API, this filter works reliably for sub-types too. Default 7 days. Watch for `possible_duplicate_of` -- see below. |
| Detail on one specific workout (exercise sets, HR zones, splits, load, weather) | `get_activity_detail(activity_id)` | Needs an `id` from `get_activities` first. `zone_boundaries_bpm` gives the real bpm cutoffs behind `hr_zones` as half-open `[low, high)` intervals (z5's upper is `null` -- Garmin doesn't return a cap). `zone_config_id` is a short hash of those boundaries: **only compare/sum `hr_zones` minutes across activities sharing the same `zone_config_id`** -- Garmin computes zone time at record time and does not retroactively recalculate past activities when zone settings change, so an activity from before a settings change and one from after will carry different `zone_config_id` values and are not comparable. |
| Sleep quality over time | `get_sleep(days)` | One row per night, most recent first. |
| Daily wellness metrics (HRV, RHR, steps, stress, body battery) over a range | `get_daily_stats(days)` | Use this for trends across several days; use `get_readiness()` for "right now." |
| Weight / body composition trend, cut or bulk progress | `get_body_trend(days)` | Returns raw points plus `avg_7d`, `avg_28d`, `trend_lb_per_week`, and a `coverage` block. Reads a local synced database, not live Garmin -- see "data freshness" below. |
| Logging a weigh-in | `log_weight(weight_lb, date=None)` | Defaults to today. Safe to call more than once for the same date -- it replaces rather than duplicates, so you don't need to check for an existing entry first. Rejects anything outside 80-500 lb. |
| Removing a mis-logged weigh-in | `delete_weight(date=None)` | Defaults to today. Use when the user says they logged the wrong value or wrong date and want it gone rather than corrected in place. |
| VO2max / aerobic capacity trend | `get_vo2max(days=90)` | Garmin only recomputes this after qualifying outdoor running/walking with HR+GPS -- `points` will often be empty or very sparse. Real measurement dates only, never interpolated. `change_28d` is `null` with fewer than 2 measurements in that window -- don't read anything into a single point. |
| Non-exercise activity / NEAT / "am I moving less day to day" | `get_activity_trend(days=90)` | Local-DB-backed (see data freshness). Compare `rest_day_avg_steps` over time, not total steps -- training days rise for obvious reasons and hide the real signal. Check `coverage_days` before trusting `steps_trend_per_week`. |
| Weekly HR zone distribution / "is training landing in the right zones" | `get_zone_summary(days=28)` | Aggregates `hr_zones` across all activities in range, grouped by week (Sunday start, matching the account's own profile setting). `zone_boundaries_bpm` are the real bpm cutoffs Garmin used for a recent activity -- there's no way to know if these are Garmin's default %HRmax zones or a custom model, so don't guess a label; just use the numbers. |
| Blood pressure | `get_bp_trend(days=90)` / `log_bp(systolic, diastolic, pulse, date=None, notes=None)` / `delete_bp(date=None)` | `pulse` is required, not optional -- Garmin's API rejects the write without it. Accepts a single already-averaged reading (e.g. from a device that does its own 3-reading averaging) -- don't log each sub-reading separately. **Never** surface a hypertension stage/category even though Garmin computes one internally -- this tool deliberately excludes it; that's a clinical judgment outside this server's scope. |
| Hydration | `get_hydration(days=30)` / `log_hydration(ml, date=None)` / `delete_hydration(date=None)` | `log_hydration` is **additive**, unlike every other write tool here -- it adds to the day's running total (matching how Garmin Connect itself treats hydration), so calling it twice logs two drinks, not a correction. `sweat_loss_ml` is Garmin's own activity+weather-derived estimate and can be present even on days with zero logged intake. `goal_ml`/`pct_of_goal` are `null` when Garmin's synced goal looks like a placeholder rather than a real value -- don't compute your own percentage if `goal_ml` is missing. |
| Training load / ramping too fast | `get_training_load(days=42)` | `acute_7d` (last 7 days) vs. `chronic_28d` (average *weekly* load over 28 days) and their ratio -- a TRIMP-style figure (duration x HR-intensity) this server computes itself, **not** Garmin/Firstbeat's own `activityTrainingLoad`. Always check `method` first (it names this as an independent calculation) and mention that context if the user asks how it compares to what Garmin Connect shows. Applies uniformly to every session with `avg_hr`, strength included -- unlike Garmin's own metric, which returns `null` for externally-uploaded activities (e.g. Tonal) since Firstbeat never reprocesses those. Check `sessions_missing_hr`/`coverage_note` for sessions excluded for lacking HR data, and `ratio_suppressed_reason` for thin windows or a `zone_config_id` change spanning the comparison. Report the number as a number -- no "optimal"/"overreaching" label. |

Don't call more than you need. "How should I train today" is `get_readiness()` alone, not five separate calls -- it's already a composite. Reach for `get_daily_stats` or `get_sleep` over a range only when the question is genuinely about a trend, not a single point-in-time check.

## Reading the fields correctly

**Weight is always in pounds** at every tool boundary (`weight_lb` fields, `log_weight`'s input). Never convert or re-derive units yourself.

**`null` means no data, not zero.** A `null` `avg_hr` on an activity, or a `null` `hrv_7d_baseline`, means Garmin doesn't have that data point -- often because the device is still "onboarding" that metric, or the stat genuinely doesn't apply (e.g. no HR strap on a walk). Report it as missing ("no HRV baseline yet" / "no distance recorded for this one"), never as 0 or "average." Silently treating a `null` as 0 will corrupt any trend math you attempt, and treating it as "normal" will give false reassurance.

**`get_readiness()` deliberately has no overall score.** You'll get the raw components (HRV, RHR, sleep score, body battery, recent training load, days since rest) but no single 0-100 "readiness" number -- that was left out on purpose so it doesn't quietly encode someone else's idea of what matters. Forming a verdict from those components, in light of the user's actual plan, is your job each time -- not a fixed formula.

**`training_effect` is Garmin's aerobic training effect metric** (roughly: <1.0 no effect, 1.0-1.9 minor, 2.0-2.9 maintaining, 3.0-3.9 improving, 4.0-4.9 highly improving, ~5.0 overreaching risk). Useful context, but it's Garmin's own model of *that one activity*, not a verdict on the user's overall plan.

**HRV, resting HR, stress, and body battery are all more meaningful relative to the user's own baseline than in absolute terms.** `get_readiness()` gives you `hrv_7d_baseline` and `rhr_7d_baseline` for exactly this reason -- a same-day comparison ("today's HRV vs. this person's own recent average") tells you far more than the raw number alone. Still, avoid turning a comparison into an invented rule ("2ms below baseline means back off") unless the user has told you that's how they want to reason about it.

**`possible_duplicate_of` on `get_activities` results is a real, confirmed failure mode, not a theoretical one**: a watch's own recording and a separate software push (e.g. a Tonal upload) can both land in Garmin for the same physical session -- seen live, 22 seconds apart, one with real content and one essentially empty. When two activities in a result set flag each other this way, don't sum their calories/duration/training_effect as if they were two separate sessions -- that double-counts training load. Check `get_activity_detail` on both if it matters which one has the real data (usually the one with a non-empty `sets` array or non-trivial HR data).

**`get_activity_detail`'s `sets` array is strength-training-only** and only as good as what was recorded -- a `sets` entry with `exercise: "Unknown"` and null reps/weight means that particular activity has no real per-exercise data (often the thin duplicate mentioned above, not the real session). `weight_lb` per set is a genuine working weight, already in lbs. `load_lb` is parsed from the activity title/notes (e.g. "ruck 30 lb") when present -- `null` means no load was mentioned, not "no load carried."

**`get_body_trend`'s `coverage` block matters as much as the trend number.** `trend_lb_per_week` can be `null` with `trend_suppressed_reason` explaining why (too few points, or too large a gap between weigh-ins) -- this is deliberate, not a bug: a slope fitted to sparse data is worse than no slope. Report the suppression plainly rather than falling back to `avg_7d`/`avg_28d` as if they were a trend. This local database gets a full re-sync daily specifically to catch weigh-ins logged for past dates (backfilled after the fact) that a purely incremental sync would otherwise never pick up -- so a gap you see today may already be gone by the next full resync.

**`get_daily_stats`'s stress fields**: `stress_avg` is the single number; `stress_rest_pct`/`stress_low_pct`/`stress_medium_pct`/`stress_high_pct` show the time-in-band shape behind it -- two days with the same average can look very different (steady low-medium stress vs. mostly rest punctuated by spikes). `hrv_highest_5min` is a peak reading, distinct from and not a substitute for the overnight `hrv_ms` mean.

**Data freshness**: `get_body_trend`, `get_activity_trend`, and `get_hydration` read a database synced from Garmin on a schedule (roughly every 20 minutes, plus a full re-sync daily -- see above), not the live API. A weigh-in logged for a *past* date typically shows up within 20 minutes. A weigh-in logged *today* is a different story -- confirmed live: the sync's weight download consistently excludes the current date entirely (it isn't just delayed, no file for it gets fetched at all), so today's entry won't appear in `get_body_trend` until the next day. If the user asks about today's weight specifically, that's a real, known gap, not a transient delay -- say so rather than implying it'll show up soon. `get_activity_trend`/`get_hydration` are also new (the account started syncing days before this was built), so `coverage_days` will be small for a while regardless of date range requested -- that will improve on its own. Everything else (`get_readiness`, `get_sleep`, `get_daily_stats`, `get_activities`, `get_vo2max`, `get_zone_summary`, `get_bp_trend`, `get_training_load`) hits Garmin live and has no such gap.

## Error handling

If a tool call fails, don't guess or fill in a plausible-sounding number. Common cases:
- Auth/token errors mean the server's Garmin session needs attention -- tell the user, don't retry in a loop.
- `get_body_trend` erroring because the local database doesn't exist yet means the nightly/periodic sync hasn't run yet -- say so plainly.
- If a date range comes back with mostly `null`s, say the data isn't there rather than working around the gap.

## Worked examples

**"I'm supposed to squat heavy today per my program but not sure if I should back off."**
Call `get_readiness()`. Look at HRV vs. baseline, RHR vs. baseline, last night's sleep score, current body battery, and how recently they trained hard (via `last_3_activities` and `days_since_rest`). Then reason about *their* program's actual autoregulation logic if they've stated one ("my program says drop to RPE 7 if sleep score is under 70" -- great, apply that literally). If they haven't given you a rule, lay out what the data shows plainly and ask how they'd normally adjust, rather than inventing a cutoff.

**"How's my cut going, I'm trying to be at 180 by the end of the month."**
Call `get_body_trend(days=30)` (or a range covering when the cut started, if they've said). Compare `avg_7d` and `trend_lb_per_week` against the stated goal and timeline -- is the current rate of loss on pace, and is the trend consistent or noisy? Report the actual numbers, don't just say "looking good."

**"Log today's weight, 182.4"**
Call `log_weight(182.4)` (date defaults to today). Confirm what came back -- no need to check for an existing entry first, the tool handles replacement.

**"What did my bench top set look like today, and how does it compare to last week?"**
Call `get_activities` filtered to `strength_training` for a range covering both sessions, then `get_activity_detail` on each to get the `sets` array. Find the bench-press entries (check `exercise` names) and compare weight/reps directly -- this is real progression data, not something to estimate from total volume or calories.

**"What did my training look like this week?"**
Call `get_activities(days=7)`. Summarize types, volume, and any `training_effect`/HR data present -- don't editorialize about whether it was "enough" unless the user has told you what enough means for them.

**"Has my VO2max moved since I resumed the cut?"**
Call `get_vo2max(days)` covering the relevant window. If `points` is empty or has one entry, say plainly that there's not enough real data to answer yet -- don't infer aerobic capacity from HRV or session RPE as a substitute, that's a different signal.

**"Is my non-exercise movement dropping as the cut goes on?"**
Call `get_activity_trend(days=90)`. Compare `rest_day_avg_steps` across the window, not `steps_avg_7d`/`steps_avg_28d` alone -- those blend training and rest days together and training days will mask a real rest-day decline.

**"Track my blood pressure, I took it this morning: 128/82, pulse 68."**
Call `log_bp(128, 82, 68)`. Confirm what was written. If they ask for a trend later, `get_bp_trend` -- report the raw numbers and 7-day averages only, never a hypertension category even if you can infer one.

**"Log that I drank a 500ml bottle."**
Call `log_hydration(500)`. Remember this adds to today's total rather than replacing it, so mention the running total from the response rather than implying it's the only thing logged today.

**"Am I ramping training too fast?"**
Call `get_training_load(days=42)`. Report `ratio` alongside `coverage_note`/`ratio_suppressed_reason` in the same breath -- if any sessions are excluded for missing HR data, say so before commenting on the ratio itself. Since this is this server's own TRIMP calculation (see `method`), not Garmin's number, mention that framing if the user compares it to something they saw in Garmin Connect directly.
