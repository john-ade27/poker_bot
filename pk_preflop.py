"""
Preflop policy (BRIEF section 5.1), heads-up.

decide(model, gs, me, opp) returns (kind, total): kind is "fold", "call"
or "raise", and total the street total for a raise (model.to_action keeps
it legal). ALL_IN asks for every chip.
"""

from pk_cards import class_of
from pk_equity import preflop_equity
from pk_ranges import PERCENTILE, top_weights

ALL_IN = 10 ** 9

DEFAULTS = {
    "open_pct": 0.70,  # button: raise this share of hands, fold the rest
    "open_size": 2.2,  # big blinds
    "bb_shove_pct": 0.13,  # big blind vs an open of 3 bb or less
    "bb_call_pct": 0.65,
    "bb_big_shove_pct": 0.11,  # big blind vs an open of 3 to 8 bb
    "big_raise_bb": 8.0,  # a raise above this is treated like an all-in
    "limp_raise_pct": 0.30,  # big blind vs a limp
    "limp_raise_size": 3.5,
    "allin_margin": 0.02,  # call an all-in when equity > price + this
    "allin_range": 0.30,  # an unknown opponent's all-in range
    "reraise_range": 0.15,  # an unknown opponent's 3-bet range
    "call_margin": 0.05,  # pot-odds calls of small re-raises
}


def preflop_actions(history, player):
    """The kinds of player's moves on the preflop street, in order."""
    return [kind for pid, kind, _, street in history
            if pid == player and street == "preflop"]


def allin_price(gs, me, opp):
    """The share of the final pot we pay by going (or calling) all in:
    no more than the opponent can match counts."""
    my_bet = gs.bets[me]
    opp_bet = gs.bets[opp]
    my_total = min(my_bet + gs.stacks[me], opp_bet + gs.stacks[opp])
    my_add = max(0, my_total - my_bet)
    opp_add = max(0, my_total - opp_bet)
    final_pot = gs.pot + my_add + opp_add
    if final_pot <= 0:
        return 1.0
    return my_add / final_pot


def allin_rule(model, gs, me, opp, weights, margin):
    """Go (or call) all in when our equity against the range beats the
    price, else fold."""
    eq = preflop_equity(model.hole, weights)
    if eq > allin_price(gs, me, opp) + margin:
        return "raise", ALL_IN  # becomes a call when we cannot raise
    return "fold", 0


def decide(model, gs, me, opp):
    p = model.params
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
        # The open: raise or fold (no limping).
        if pct <= p["open_pct"]:
            return "raise", round(p["open_size"] * bb)
        return ("call", 0) if to_call == 0 else ("fold", 0)

    if not button and not acted:
        if to_call == 0:
            # The button limped.
            if pct <= p["limp_raise_pct"]:
                return "raise", round(p["limp_raise_size"] * bb)
            return "call", 0
        if opp_all_in or opp_bet > p["big_raise_bb"] * bb:
            return allin_rule(model, gs, me, opp, top_weights(p["allin_range"]),
                              p["allin_margin"])
        if opp_bet <= 3 * bb:
            if pct <= p["bb_shove_pct"]:
                return "raise", ALL_IN
            if pct <= p["bb_call_pct"]:
                return "call", 0
            return "fold", 0
        if pct <= p["bb_big_shove_pct"]:
            return "raise", ALL_IN
        return "fold", 0

    # Facing a re-raise after our own move.
    if to_call == 0:
        return "call", 0
    if opp_all_in or 3 * to_call >= my_stack:
        rng_pct = p["allin_range"] if opp_all_in else p["reraise_range"]
        return allin_rule(model, gs, me, opp, top_weights(rng_pct),
                          p["allin_margin"])
    weights = top_weights(p["reraise_range"])
    kind, total = allin_rule(model, gs, me, opp, weights, p["allin_margin"])
    if kind == "raise":
        return kind, total
    eq = preflop_equity(hole, weights)
    if eq > gs.pot_odds + p["call_margin"]:
        return "call", 0
    return "fold", 0
