"""
Postflop policy. Milestone 1: equity against a random hand; bet when it
is high, call when it beats the price, else check or fold.
"""

from pk_cards import COMBOS
from pk_equity import mc_equity

DEFAULTS = {
    "post_bet_eq": 0.65,  # bet when equity is above this
    "post_raise_eq": 0.85,  # raise a bet when equity is above this
    "post_call_margin": 0.10,  # call when equity > price + this
    "post_bet_frac": 0.75,  # bet size, share of the pot
    "post_raise_frac": 1.0,  # raise size, share of the pot after calling
    "mc_budget": 0.05,  # seconds of Monte Carlo per decision
    "mc_samples": 1500,  # Monte Carlo samples at most
}

_UNIFORM = [1.0] * len(COMBOS)


def bet_total(gs, me, frac):
    """The street total for a bet (or raise) of frac of the pot, counted
    after calling."""
    to_call = gs.call_amount
    return gs.bets[me] + to_call + frac * (gs.pot + to_call)


def decide(model, gs, me, opp, start):
    p = model.params
    deadline = start + p["mc_budget"]
    eq = mc_equity(model.hole, model.board, COMBOS, _UNIFORM, model.rng,
                   deadline, p["mc_samples"])
    to_call = gs.call_amount
    if to_call == 0:
        if eq > p["post_bet_eq"]:
            return "raise", bet_total(gs, me, p["post_bet_frac"])
        return "call", 0
    if eq > p["post_raise_eq"]:
        if gs.stacks[me] <= to_call:
            return "call", 0
        return "raise", bet_total(gs, me, p["post_raise_frac"])
    if eq > gs.pot_odds + p["post_call_margin"]:
        return "call", 0
    return "fold", 0
