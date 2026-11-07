"""
Preflop policy (BRIEF section 5.1), heads-up, with the opponent model's
exploits (section 6).

decide(model, gs, me, opp) returns (kind, total): kind is "fold", "call"
or "raise", and total the street total for a raise (model.to_action keeps
it legal). ALL_IN asks for every chip.
"""

from pk_cards import class_of
from pk_equity import preflop_equity
from pk_estimate import preflop_classes
from pk_opponent import MIN_SEEN, labels, lam, rate, seen
from pk_ranges import PERCENTILE, top_weights

ALL_IN = 10 ** 9

DEFAULTS = {
    "open_pct": 0.70,  # button: raise this share of hands, fold the rest
    "open_size": 2.2,  # big blinds
    "bb_shove_eq": 0.58,  # big blind vs an open of 3 bb or less: all in
    # when equity against their opening range is at least this
    "bb_call_pct": 0.65,  # call with hands up to this percentile
    "bb_call_margin": 0.06,  # when equity > price + this
    "big_raise_bb": 8.0,  # a raise above this is treated like an all-in
    "limp_raise_pct": 0.30,  # big blind vs a limp
    "limp_raise_size": 3.5,
    "allin_margin": 0.02,  # call an all-in when equity > price + this
    "call_margin": 0.05,  # pot-odds calls of small re-raises
    "station_call_allin": 0.60,  # they call all-ins this often: shove
    "station_shove_ev": 0.5,  # for value when it wins this many bb
    "station_limp_pct": 0.85,  # and limp these hands otherwise
    "stat_decay": 0.99,  # opponent counts are multiplied by this each hand
}


def preflop_actions(history, player):
    """The kinds of player's moves on the preflop street, in order."""
    return [kind for pid, kind, _, street in history
            if pid == player and street == "preflop"]


def allin_amounts(gs, me, opp):
    """(chips we add, final pot) if we go all in and are called: no more
    than the opponent can match counts."""
    my_bet = gs.bets[me]
    opp_bet = gs.bets[opp]
    my_total = min(my_bet + gs.stacks[me], opp_bet + gs.stacks[opp])
    my_add = max(0, my_total - my_bet)
    opp_add = max(0, my_total - opp_bet)
    return my_add, gs.pot + my_add + opp_add


def allin_rule(model, gs, me, opp, weights, margin):
    """Go (or call) all in when our equity against the range beats the
    price, else fold."""
    eq = preflop_equity(model.hole, weights)
    my_add, final_pot = allin_amounts(gs, me, opp)
    if final_pot > 0 and eq > my_add / final_pot + margin:
        return "raise", ALL_IN  # becomes a call when we cannot raise
    return "fold", 0


def call_allin_chance(stats):
    """How often they call an all-in: their record when they have one,
    otherwise guessed from how rarely they fold to an open."""
    guess = 1.0 - rate(stats, "bb_fold") - 0.1
    return rate(stats, "call_allin", min(0.9, max(0.15, guess)))


def decide(model, gs, me, opp):
    p = model.params
    stats = model.opp_stats(gs, opp)
    labs = labels(stats)
    exploit = model.rng.random() < lam(stats)
    hole = model.hole
    pct = PERCENTILE[class_of(hole[0], hole[1])]
    bb = gs.big_blind
    to_call = gs.call_amount
    opp_bet = gs.bets[opp]
    my_stack = gs.stacks[me]
    opp_all_in = gs.stacks[opp] == 0
    button = gs.button == me
    acted = len(preflop_actions(model.history, me)) > 0

    if button and not acted:
        return _open(model, gs, me, opp, stats, labs, exploit, pct)

    if not button and not acted:
        if to_call == 0:
            # The button limped.
            if pct <= p["limp_raise_pct"]:
                return "raise", round(p["limp_raise_size"] * bb)
            return "call", 0
        their = preflop_classes(model, gs, me, opp, stats)
        if opp_all_in or opp_bet > p["big_raise_bb"] * bb:
            return allin_rule(model, gs, me, opp, their, p["allin_margin"])
        eq = preflop_equity(hole, their)
        if opp_bet <= 3 * bb:
            if eq >= p["bb_shove_eq"]:
                return "raise", ALL_IN
            if pct <= p["bb_call_pct"] and eq > gs.pot_odds + p[
                    "bb_call_margin"]:
                return "call", 0
            return "fold", 0
        if eq >= p["bb_shove_eq"] + 0.03:
            return "raise", ALL_IN
        return "fold", 0

    # Facing a re-raise after our own move.
    if to_call == 0:
        return "call", 0
    their = preflop_classes(model, gs, me, opp, stats)
    if opp_all_in or 3 * to_call >= my_stack:
        return allin_rule(model, gs, me, opp, their, p["allin_margin"])
    kind, total = allin_rule(model, gs, me, opp, their, p["allin_margin"])
    if kind == "raise":
        return kind, total
    eq = preflop_equity(hole, their)
    if eq > gs.pot_odds + p["call_margin"]:
        return "call", 0
    return "fold", 0


def _open(model, gs, me, opp, stats, labs, exploit, pct):
    """The button's first move."""
    p = model.params
    bb = gs.big_blind
    open_to = round(p["open_size"] * bb)
    if exploit and "folder" in labs:
        return "raise", open_to  # they fold: raise every hand
    if exploit:
        calls = call_allin_chance(stats)
        evidence = (seen(stats, "call_allin") >= 8
                    or seen(stats, "bb_fold") >= MIN_SEEN)
        if evidence and calls >= p["station_call_allin"]:
            # They call too much: all in when ahead of their calling range.
            eq = preflop_equity(model.hole, top_weights(calls))
            my_add, final_pot = allin_amounts(gs, me, opp)
            ev = (1.0 - calls) * gs.pot + calls * (eq * final_pot - my_add)
            if ev > p["station_shove_ev"] * bb:
                return "raise", ALL_IN
            if pct <= p["station_limp_pct"]:
                return "call", 0
            return "fold", 0
        if "pf_maniac" in labs:
            # They re-raise most opens: open only what can call it.
            reraise = rate(stats, "bb_raise") + rate(stats, "bb_allin")
            weights = top_weights(max(0.05, reraise))
            eq = preflop_equity(model.hole, weights)
            my_add, final_pot = allin_amounts(gs, me, opp)
            if eq > my_add / final_pot + p["allin_margin"]:
                return "raise", open_to
            return "fold", 0
    if pct <= p["open_pct"]:
        return "raise", open_to
    return "fold", 0
