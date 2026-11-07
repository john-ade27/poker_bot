# Poker Bot Build Brief

**Manchester AI Society poker bot hackathon, Saturday 7 November 2026.** Heads-up no-limit Texas Hold'em. Submissions open 16:00, deadline 18:00.

Everything in section 1 was read from the organisers' repository (`Manchester-AI-Society/poker_bot`, commit `b852bd5`, 7 Nov 2026 13:11 UTC) and the event website. Where this brief and the repo ever disagree, **the repo wins**.

---

## 0. How to use this brief with Claude Code

1. Copy this file into the root of your fork as `BRIEF.md` (or give Claude Code the PDF).
2. Open Claude Code in the repo root and paste this prompt, with your team name filled in:

```text
Read CLAUDE.md, README.md and BRIEF.md in full before writing any code.
Build the bot described in BRIEF.md in model.py plus flat helper files next
to it. Follow the milestones in BRIEF.md section 8 strictly in order, and
do not start a milestone until the previous one passes its acceptance tests.
After every milestone run, from the repo root:
  .venv\Scripts\python -m pytest tests/test_model.py -q
  .venv\Scripts\python -m evals --deals 500
  .venv\Scripts\python -m submit --team <TEAM>
(on macOS/Linux use .venv/bin/python). Commit after each milestone passes.
Never edit card_utils.py, player_action.py, game_state.py, game_interface.py.
Keep every rule in BRIEF.md section 7 (safety and code review). If the repo
and BRIEF.md disagree, follow the repo and tell me. Tell me the time-critical
status after each milestone: what passes, bb/100 vs each dummy, max move time.
```

---

## 1. The event: verified facts

| Item | What the code and site say |
|---|---|
| Game | Heads-up no-limit Hold'em. One round: every bot plays every other bot; each pairing is a **duplicate match** (same decks, seats swapped). |
| Blinds and stacks | 10/20. **Stacks 500 chips = 25 big blinds**, reset every hand (`MatchConfig.stack = 500`; the event's `run` does not override it). |
| Hands per opponent | `python -m arena.event run --deals 200` is the default: 200 decks, each played once per seat, so **400 hands per opponent**. |
| Position | In duplicate mode the button is always seat 0. So in one half (200 hands) you are **always the button/small blind**, and in the other half **always the big blind**. |
| Memory between hands | Your model is rebuilt from the pickle for each half and keeps its attributes for the 200 hands of that half. Nothing survives between halves or opponents. |
| Score | bb/100 (big blinds won per 100 hands), pooled over every hand against every opponent. Best score is champion. Results appear on the site with a delay. |
| Possible opponents | Other teams, and possibly the repo's dummy bots, which the code describes as "fillers for the arena": `fold`, `call`, `random`, `shove`, `tight`, `equity`. |
| Time | **10 s per call** (`seed`, `run`, `end_game`). The first call also includes start-up (process start, imports, unpickling). A timeout kills your bot: it checks or folds for the rest of that match. |
| Faults | An exception or illegal move is a fault for that move only: the engine checks (if free) or folds instead. Faults in `end_game` count too. |
| Memory | 2 GB per bot process. |
| Libraries | `requirements.txt` is only `pydantic==2.14.3`. The code review accepts numpy, but numpy is **not** in the requirements, so **do not use numpy** unless an organiser confirms it is installed on the machine that plays. Python 3.10+; the organisers' exact version is unknown, so write Python 3.10-compatible code. |
| What your bot sees | `seed(hand, player_id)` once per hand; `run(actions, game_state)` on each turn (`actions` = everything since your last turn, your own move and board cards included); `end_game(actions, game_state)` after every hand, **including the opponent's hole cards at a showdown** and who won what. `game_state.teams` gives team names. |
| Submission | `python -m submit --team <team>` writes `<team>.pkl`, runs the same review the organisers run, plays it against dummies, and lists the files to upload (the `.pkl` plus your `.py` files). Upload all of them in the form (link appears on the site at 16:00). The newest upload that works before 18:00 plays; a broken newer upload never replaces a working one. |
| Code review limits | Max 20 `.py` files, each 1 MB or less, pickle 50 MB or less. Files flat next to `model.py`, names of letters, digits and `_`, not named like a standard-library module. Details in section 7. |

---

## 2. What these facts mean for the design

1. **25 big blinds is a short stack.** Preflop decisions decide most of the result. After a 2.2 bb open and a call the pot is 4.4 bb with 22.8 bb behind (stack-to-pot ratio about 5). After a 3-bet it is about 1 to 2. Many decisions are "get it all in, or fold". All-in preflop logic is central, not an edge case.
2. **The score is chips per hand, pooled over all opponents.** Winning big against weak and predictable bots matters far more than edging a strong one. A bug, timeout or leak that hands chips to everyone is the biggest risk. Each pairing is noisy (about ±50 to 100 bb/100 at 500 deals), so the reliable edges are large, simple exploits.
3. **The opponent model must learn fast.** It gets 200 hands, in one position, then is wiped. It needs sensible starting assumptions (priors) and must adapt within 15 to 30 hands. Showdown cards make it much sharper than action counts alone.
4. **10 s is generous, but keep decisions near 50 to 100 ms.** Local `evals` runs thousands of decisions; slow bots make testing slow. Hard stop at 1 s.
5. **Pure Python, with your own fast evaluator.** `card_utils.evaluate` validates its input with pydantic and checks all 21 five-card subsets: fine for tests, far too slow for Monte Carlo simulation.
6. **Plain code passes the review fastest.** Flagged code waits for an organiser to read it, which could delay your bot.

---

## 3. The logic behind poker bots, and what this bot uses

- **Hidden information.** Unlike chess, you cannot see the opponent's cards. You reason about their **range**: every hand they could hold, weighted by how likely their actions make it.
- **Equity.** Your chance of winning at showdown against that range. Estimated by **Monte Carlo simulation**: deal random opponent hands (from the range) and random remaining board cards many times and count wins. On the river it can be enumerated exactly.
- **Pot odds.** Calling `c` chips into a pot of `P` (opponent's bet included) needs equity of at least `c / (P + c)`.
- **Expected value (EV).** For each option (fold, call, bet sizes), estimate chips won on average, and pick the best. For a bet: the opponent folds with probability `f` and you win the pot; otherwise you play the pot with your equity against the hands that call.
- **Position.** Acting last is an advantage. Heads-up, the button acts first preflop and last on every later street, so it plays more hands.
- **Game-theory optimal (GTO) vs exploitative play.** A GTO strategy (a Nash equilibrium) cannot be beaten in the long run, but wins little from weak players. An exploitative strategy deviates to punish specific leaks (never bluff a bot that always calls; bluff a bot that always folds). In a hackathon field, exploitation wins more chips.

**What top research bots do, and why this one does not.** Libratus, DeepStack, Pluribus and Slumbot compute near-GTO strategies by self-play with **counterfactual regret minimisation (CFR)** and its variants, plus real-time solving of the rest of the hand. Their human-free training took millions of core-hours or months of work and huge strategy tables. **Reinforcement learning** (self-play RL, NFSP, PPO) is weaker than CFR for poker and needs neural networks. **LLM agents** are slow and lose to solver bots. None of this fits a 4-hour, pure-Python, 10-second event. Using CFR offline to compute a small preflop table is possible but optional and out of scope for today.

**This bot:** precomputed preflop hand rankings and charts, Monte Carlo equity against an estimated opponent range, EV-based choice of action, an opponent model that adjusts the ranges and the exploits, and strict safety wrappers.

**What about professional players' data?** The strongest bots learned from self-play, not from human hand histories; human data is noisy and reproduces human mistakes. For this event it adds nothing you can use in 4 hours. The useful "expert knowledge" is in the solver-style preflop ranges and push/fold charts linked in section 12.

---

## 4. Architecture and files

All bot files are flat, next to `model.py`, and imported (directly or indirectly) by `model.py`, because `python -m submit` only uploads the modules the model imports.

| File | Contents |
|---|---|
| `model.py` | The `Model` class: `__init__`, `seed`, `run`, `end_game`; the safety wrapper; per-hand state; opponent stats stored as plain dicts. |
| `pk_cards.py` | Card encoding as ints 0..51 (`rank*4 + suit`), conversion from `Card` (via `str(card)`), the 169 starting-hand classes (pairs, suited, offsuit) and their combo lists. |
| `pk_eval.py` | Fast 7-card evaluator returning one comparable int (bigger wins, equal splits). Tables built at import time or in `pk_tables.py`. |
| `pk_tables.py` | Generated constants only: preflop ranking of the 169 classes, equity of each class against a random hand and against "top x%" ranges. Generated by `tools/build_tables.py`. |
| `pk_equity.py` | Time-boxed Monte Carlo equity against a weighted range; exact enumeration on the river. |
| `pk_ranges.py` | "Top x%" ranges from the ranking; postflop range narrowing (section 5.3). |
| `pk_preflop.py` | Preflop policy (section 5.1). |
| `pk_postflop.py` | Postflop EV policy (section 5.2). |
| `pk_opponent.py` | Opponent statistics, shrinkage, archetype labels, adjustments (section 6). |
| `tools/` | **Not imported by the bot and not uploaded:** `build_tables.py`, `test_pk_eval.py`, extra sparring bots, gauntlet scripts. Offline tools may use anything (numpy, eval7). |

**Model attributes must be plain data:** ints, floats, strings, lists, dicts, tuples, `bytes`, and one `random.Random`. **Do not store `Card` objects** (pydantic version coupling) or `array.array` (refused by the pickle review) in attributes. Convert cards to ints in `seed` and `run`.

---

## 5. Strategy specification (starting parameters, then tune)

Units: `bb = game_state.big_blind` (20 chips). Effective stack at the start of every hand: 25 bb. All parameters below are **starting values** to tune with `evals` (section 8).

**Hand ranking.** Rank the 169 starting-hand classes by equity against a random hand (computed offline, stored in `pk_tables.py`). "Top x%" means the best classes in that order, counting combos (pairs 6, suited 4, offsuit 12) until x% of the 1,326 combos are covered.

### 5.1 Preflop

**As the button (small blind, acts first):**

- Raise to **2.2 bb** with the **top 70%**; fold the rest (no limping, for simplicity). Tune between 60% and 85%.
- Facing a 3-bet or all-in: if putting in more chips would commit a third or more of your stack, go **all-in or call all-in with the top 15%** of hands (wider against opponents who 3-bet often: use their estimated 3-bet range and the all-in rule below); otherwise fold.

**As the big blind:**

- Facing an open of 3 bb or less: **all-in with the top 12 to 15%**, **call with the next hands up to the top 65%** (the price is good: calling 1.2 bb to win 4.4 bb needs about 27% equity), fold the rest.
- Facing a limp: raise to 3.5 bb with the top 30%, otherwise check.
- Facing a bigger raise (3 to 8 bb): all-in with the top 10 to 12%, fold most of the rest.

**All-in rule (any seat, any street):** when facing an all-in, or deciding whether to call one, call if `equity(hand vs estimated all-in range) > price + 0.02`, where `price = to_call / (pot + to_call)`. Default all-in range for an unknown opponent: top 30%. Use the opponent model's estimate once it has data (against a bot that shoves every hand the range is 100%, so you call with roughly the better half of hands).

**Going all-in instead of opening** pays against opponents who call too much: if an opponent calls all-ins with range R, going all-in for 25 bb beats folding the small blind when your equity against R is above about 49%.

### 5.2 Postflop (flop, turn, river)

1. Estimate `eq` = equity against the opponent's current range (Monte Carlo, about 60 ms, at least 200 samples; exact on the river).
2. Candidate actions: check (if free), fold (if facing a bet), call, and bets/raises of **33%, 66%, 100% of the pot and all-in**.
3. EV of each candidate, in chips, counting from now:
   - Fold: 0. Check: `eq * pot`. Call: `eq * (pot + to_call) - to_call`.
   - Bet adding `b` chips: `f * pot + (1 - f) * (eq_called * (pot + 2b) - b)`, where `f` = probability the opponent folds to this size (opponent model, default 0.40) and `eq_called` = your equity against the **stronger** `(1 - f)` part of their range.
4. Pick the best EV. Then apply the rules:
   - **Never fold when checking is free.**
   - If the stack-to-pot ratio is 1.5 or less and `eq >= 0.55`, go all-in.
   - If a bet would leave less than about 10% of your stack behind, go all-in instead.
   - **Bluff** (bet with `eq < 0.35`) only if the opponent's shrunk fold-to-bet rate is 0.5 or more and they are not labelled a calling station.
   - Facing a raise: continue only if `eq` against their raising range beats the price.

### 5.3 Estimating the opponent's range

- **Preflop:** set the range to a top-x% range from the opponent's action and seat (for example, their open, call, 3-bet or all-in frequency from the model, shrunk towards defaults). Remove combos that clash with your hole cards and the board.
- **Each new street:** score every remaining combo by its hand strength on the current board (one evaluation per combo; about 1,000 combos).
- **When they bet or raise:** keep the strongest `a` fraction of the range, where `a` is their betting frequency in that spot, plus a bluff share `beta` of the weaker part (`beta` learned from showdowns, default 0.25).
- **When they check or call:** mildly reduce the weight of the very strongest combos (they would often have bet them) and drop the weakest when they call a large bet.

---

## 6. Opponent model and exploits

Key every statistic by the opponent's team name: `game_state.teams[opponent_id]`. Store stats as nested dicts of counts in the model. Update in `end_game`, which sees every action of the hand (including the opponent's folds) and the showdown cards.

**Statistics (count hits and opportunities):**

- Preflop as button: fold %, open-raise %, limp %, all-in %, average open size.
- Preflop as big blind: fold to an open, call, 3-bet, all-in.
- Postflop: bet when checked to; fold to a bet (separately for small, medium and large bets); raise; call down to the river.
- Showdown: for every shown hand, the actions they took and their hand strength, giving a **bluff rate** (bets/raises with weak hands) and a **call-down-light rate** (calls with weak hands).

**Shrinkage, so a few hands never cause a big adjustment:** `estimate = (hits + k * prior) / (opportunities + k)` with `k = 10`. Priors: a sensible human-like player (for example fold to an open 35%, fold to a bet 40%, bluff rate 0.25).

**Labels and exploits** (re-evaluate every hand; the repo's dummy bots are perfectly consistent and show up within about 15 to 20 hands):

| Label | How to spot it | Exploit |
|---|---|---|
| Folder | Folds to bets/opens 75% or more | Raise every hand preflop; bet small at every chance; give up when they fight back. |
| Calling station | Calls 70% or more of bets, rarely folds or raises | Never bluff. Bet bigger with value hands, go all-in with any hand that has better than 50% equity against their calling range. |
| Maniac / shover | Raises or goes all-in 50% or more | Play tighter, call all-ins with equity above the price against a wide range, check and call rather than bet into them. |
| Random | Actions unrelated to showdown strength | Value-heavy: bet good hands for value, no bluffs, call with decent equity. |
| Tight / solid / unknown | None of the above | Default strategy, with the 5.1 and 5.2 parameters. |

**Expect many entries to resemble the repo's example bot or `EquityBot`** (equity against a random hand, bet the pot when above 50%). Such bots overvalue medium hands and call too much, so value-bet thinner and bluff less than a GTO bot would.

**Limit the exploit by sample size:** blend `strategy = (1 - lam) * default + lam * exploit` with `lam = n / (n + 30)`, where `n` is hands seen against this opponent.

---

## 7. Safety and code-review rules (must follow)

**Never lose a match to a crash or timeout:**

- In `run`: first compute `safe = call` if `call_amount == 0` else `fold`. Wrap all logic in `try/except Exception`; on any error return `safe`. Before returning, call `game_state.validate_action(action)` inside the `try`.
- Wrap `end_game` in `try/except Exception` too (faults there count).
- Time: read `time.perf_counter()` at the start of `run`; Monte Carlo loops check the clock every 64 samples; budget 100 ms; if more than 1 s has passed, stop and return the best answer so far.
- Raises: `raise_to` is your **total bet this street**, an int within `game_state.raise_range`. If `can_raise` is false, call instead. `legal_actions` is a property (no brackets).
- Keep per-hand history (all actions this hand, with the street each happened on) and reset it in `seed`. `run` only receives actions since your last turn. Board cards come from `reveal_card` by the dealer (`player_id == -1`); a `reveal_card` from a player is a shown hole card.
- Build only with `PlayerAction.fold(me)`, `PlayerAction.call(me)`, `PlayerAction.raise_to(me, total)`, using your own `player_id`.
- Use `self.rng = random.Random(<fixed seed>)` for repeatable results.

**Pass the code review without a human:**

- Allowed imports: `random`, `time`, `math`, `bisect`, `itertools`, `collections`, `functools`, `heapq`, `operator`, `dataclasses`, `typing`, plus `card_utils`, `game_state`, `player_action` and your own files.
- Do **not** import `os`, `sys`, `io`, `pickle`, `pathlib`, `threading`, `logging`, `types`, `inspect`, `gc` or similar.
- Do **not** call `eval`, `exec`, `compile`, `open`, `input`, `globals`, `locals`, `vars`, `setattr`, `delattr`, `__import__`, and avoid `getattr`, `hasattr`, `type()` and `super()` (flagged for review).
- Do **not** define `__getstate__`, `__setstate__`, `__reduce__`, `__getattr__`, `__getattribute__`, `__new__` or `__del__`, and do not touch `__class__`, `__dict__`-style internals, `_state`, `PUBLIC` or `modules`.
- No strings containing URLs or system paths in bot code.
- At most 20 `.py` files. Run `python -m submit --team <team>` after every change: it shows exactly what the review would flag.
- Keep the pickle small (under 5 MB) so start-up stays fast.

---

## 8. Milestones and timeline (all times today)

Windows commands shown; on macOS/Linux use `.venv/bin/python`.

| By | Milestone | Acceptance tests |
|---|---|---|
| 14:55 | **M0: Setup.** venv, `pip install -r requirements-dev.txt`, template passes. | `pytest tests/test_model.py -q` passes; `python -m submit --team <team>` prints OK; `python -m evals` runs and prints a baseline table. |
| 15:40 | **M1: Fast core + simple bot.** `pk_cards`, `pk_eval`, `pk_tables` (via `tools/build_tables.py`), `pk_equity`; preflop chart from 5.1; postflop: bet when equity against a random hand is above 0.65, call when it beats pot odds, else check/fold. Safety wrapper from section 7. | `tools/test_pk_eval.py`: on 20,000 random pairs of 7-card hands, comparisons agree with `card_utils.evaluate` 100%; at least 50,000 evaluations/s. `test_model.py` passes with 0 faults. `evals --deals 500`: ahead of `fold`, `call`, `random`, `tight`; not behind `shove` or `equity`. Max move time below 0.3 s. |
| 16:05 | **Submit v1** as soon as the form opens. Copy `<team>.pkl` to `bots/v1.pkl` (a gitignored folder) for later comparisons. | Upload succeeds; the site lists the submission. |
| 17:00 | **M2: Opponent model + ranges + EV postflop** (sections 5.2, 5.3, 6). | Still 0 faults. Ahead of every dummy at `--deals 1000`. Against `bots/v1.pkl` (`evals --opponents bots/v1.pkl --deals 1000`): ahead, or at least not behind with a higher total against the dummies. |
| 17:40 | **M3: Tune and resubmit.** Adjust open %, all-in ranges, bet sizes, fold-to-bet priors; test each change against dummies and previous versions with `--times 3`. | A change is kept only if it is not worse against any dummy and the pooled total improves. Submit each improvement. |
| 17:45 | **Freeze.** Final `python -m submit`, upload. Do not wait until 17:59. | The last upload works. |

**Always keep the last good pickle.** Only resubmit a version with 0 faults that beats the previous one.

**Useful extra sparring partners** (in `tools/`, used through `--model` or by pickling them with `submit`): an always-all-in-preflop bot, an always-min-raise bot, a bot that copies the README example, and your own earlier versions.

---

## 9. Pseudocode

**`model.py` skeleton:**

```python
import random
import time

from player_action import PlayerAction
import pk_cards, pk_preflop, pk_postflop, pk_opponent


class Model:
    def __init__(self):
        self.rng = random.Random(20261107)
        self.opp = {}           # team name -> stats dict (plain data only)
        self.hole = (0, 0)      # ints 0..51
        self.player_id = 0
        self.history = []       # (player_id, kind, amount, street) this hand
        self.shown = {}         # player_id -> (c1, c2) at showdown

    def seed(self, hand, player_id):
        self.hole = (pk_cards.to_int(hand[0]), pk_cards.to_int(hand[1]))
        self.player_id = player_id
        self.history = []
        self.shown = {}

    def run(self, actions, gs):
        me = self.player_id
        safe = PlayerAction.call(me) if gs.call_amount == 0 else PlayerAction.fold(me)
        start = time.perf_counter()
        try:
            self._record(actions)
            name = gs.teams[1 - me]
            stats = self.opp.setdefault(name, pk_opponent.new_stats())
            if gs.street == "preflop":
                kind, total = pk_preflop.decide(self, gs, stats)
            else:
                kind, total = pk_postflop.decide(self, gs, stats, start, 0.10)
            action = to_action(me, gs, kind, total)
            gs.validate_action(action)
            return action
        except Exception:
            return safe

    def end_game(self, actions, gs):
        try:
            self._record(actions)
            name = gs.teams[1 - self.player_id]
            stats = self.opp.setdefault(name, pk_opponent.new_stats())
            pk_opponent.update(stats, self.history, self.shown, self.player_id, gs)
        except Exception:
            pass


def to_action(me, gs, kind, total):
    if kind == "raise" and gs.can_raise:
        low, high = gs.raise_range
        total = int(max(low, min(high, total)))
        if total >= 0.9 * high:
            total = high                          # don't leave crumbs: all-in
        return PlayerAction.raise_to(me, total)
    if kind == "fold" and gs.call_amount > 0:
        return PlayerAction.fold(me)
    return PlayerAction.call(me)                  # call, or check when free
```

**Time-boxed Monte Carlo equity against a weighted range:**

```python
def equity(hole, board, combos, weights, rng, deadline, max_samples=3000):
    dead = set(hole) | set(board)
    live, cum, total = [], [], 0.0
    for (a, b), w in zip(combos, weights):
        if w > 0 and a not in dead and b not in dead:
            total += w; live.append((a, b)); cum.append(total)
    if not live:
        return 0.5
    deck = [c for c in range(52) if c not in dead]
    need = 5 - len(board)
    won = n = 0
    while n < max_samples:
        if n % 64 == 0 and n >= 200 and time.perf_counter() > deadline:
            break
        a, b = live[bisect.bisect_left(cum, rng.random() * total)]
        runout = []
        while len(runout) < need:                 # draw board cards
            c = deck[rng.randrange(len(deck))]
            if c != a and c != b and c not in runout:
                runout.append(c)
        full = list(board) + runout
        mine = rank7(list(hole) + full)
        theirs = rank7([a, b] + full)
        won += 2 if mine > theirs else (1 if mine == theirs else 0)
        n += 1
    return won / (2 * n)
```

**Postflop EV choice:**

```python
def choose(eq, eq_called_for, fold_prob_for, pot, to_call, sizes_chips, my_stack):
    options = []
    if to_call == 0:
        options.append(("call", 0, eq * pot))                  # check
    else:
        options.append(("fold", 0, 0.0))
        options.append(("call", 0, eq * (pot + to_call) - to_call))
    for total, b in sizes_chips:          # (raise_to street total, chips added)
        f = fold_prob_for(b, pot)         # opponent model, by bet size
        eqc = eq_called_for(f)            # equity vs the stronger (1 - f) of range
        ev = f * pot + (1 - f) * (eqc * (pot + 2 * b) - b)
        options.append(("raise", total, ev))
    best = options[0]
    for option in options[1:]:
        if option[2] > best[2]:
            best = option
    return best[0], best[1]
```

**Opponent update (in `end_game`):**

```python
def update(stats, history, shown, me, gs):
    stats["hands"] += 1
    opp = 1 - me
    for street, situation, kind, size in opponent_decisions(history, opp, gs):
        bump(stats, street, situation, kind, size)   # hits and opportunities
    if opp in shown:
        strength = showdown_strength(shown[opp], gs.board)
        for street, kind in opponent_aggression(history, opp):
            record_bluff_or_value(stats, street, kind, strength)

def rate(stats, key, prior, k=10):
    hits, chances = stats[key]
    return (hits + k * prior) / (chances + k)
```

---

## 10. Questions to ask the organisers (WhatsApp group)

1. Does the round use the code defaults: 500-chip stacks (25 bb), 10/20 blinds, 200 deals per pairing?
2. Is numpy installed on the machine that plays the bots?
3. Will the dummy bots (`fold`, `call`, `random`, `shove`, `tight`, `equity`) be in the field?
4. Which Python version runs the pickles?

If stacks are deeper (for example 100 bb), loosen the all-in ranges a lot, raise to 2.5 bb, and give postflop play more weight.

---

## 11. Fair play

- Exploiting other bots' *strategies* is the game; exploiting the engine, the other workers or the organisers' machine is forbidden and visible in the code review.
- Do not try to read other bots' cards, the deck, or engine internals.
- Never run any poker bot on a real-money poker site: they ban bots, close accounts and keep the money.

---

## 12. Links

**This event**

- Event site (rules, submission link from 16:00, results): https://poker-arena-site.vercel.app/
- Organisers' repo (engine, `CLAUDE.md`, `README.md`, dummy bots, `submit`, `evals`): https://github.com/Manchester-AI-Society/poker_bot
- Submission form as linked in the README (use the site's link if it differs): https://docs.google.com/forms/d/e/1FAIpQLSe1MQUfkZcGnGBpcgON4J7HumKMBsOekWnr0ZvLcytxA8R5gQ/viewform

**Hand evaluators (read for algorithms; use offline only)**

- treys (pure Python, Cactus Kev-style evaluator): https://github.com/ihendley/treys
- PokerHandEvaluator (C/C++/Python, fast perfect-hash evaluator): https://github.com/HenryRLee/PokerHandEvaluator
- eval7 (fast equity, handy for building `pk_tables.py` offline): https://github.com/anyall/eval7

**Short-stack preflop references**

- Heads-up Nash push/fold charts, 2 to 15 bb: https://jarvispoker.com/push-fold
- Push/fold trainer and charts: https://www.primedope.com/pushbot-trainer/

**Engines and research code (background, optional)**

- PokerKit (pure-Python engine, rules cross-check): https://github.com/uoftcprg/pokerkit
- OpenSpiel (CFR, MCCFR, Deep CFR, NFSP implementations): https://github.com/google-deepmind/open_spiel
- MIT Pokerbots course (lectures and skeleton bots): https://pokerbots.org/
- Curated list of poker AI papers and tools: https://github.com/PokerBotAI/awesome-poker-ai

**Learning the algorithms**

- Neller and Lanctot, An Introduction to Counterfactual Regret Minimization: http://modelai.gettysburg.edu/2013/cfr/cfr.pdf
- Annotated Monte Carlo CFR on Kuhn poker: https://nn.labml.ai/cfr/index.html
- Zinkevich et al., CFR (2007): https://papers.nips.cc/paper/3306-regret-minimization-in-games-with-incomplete-information
- Moravcik et al., DeepStack (2017): https://arxiv.org/abs/1701.01724
- Brown and Sandholm, Libratus (Science 2018): https://www.science.org/doi/10.1126/science.aao1733
- Brown and Sandholm, Pluribus (Science 2019): https://www.science.org/doi/10.1126/science.aay2400
- Brown et al., Deep CFR (2019): https://arxiv.org/abs/1811.00164
- Heinrich and Silver, NFSP (2016): https://arxiv.org/abs/1603.01121

**Data (for reference, not needed today)**

- PHH dataset (Pluribus's 10,000 hands, WSOP final table, millions of online hands): https://github.com/uoftcprg/phh-dataset
- PokerBench (evidence that LLMs play poker poorly): https://arxiv.org/abs/2501.08328
