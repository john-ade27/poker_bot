"""
Heads-up no-limit hold'em bot (see BRIEF.md).

Everything the model keeps is plain data: ints, floats, strings, tuples,
lists, dicts and one random.Random. Cards are ints 0..51 (pk_cards); no
Card object is ever stored.
"""

import random
import time

import pk_cards
import pk_postflop
import pk_preflop
from player_action import PlayerAction

DEALER = -1
STREETS = {0: "preflop", 3: "flop", 4: "turn", 5: "river"}


class Model:
    def __init__(self):
        self.rng = random.Random(20261107)
        self.params = dict(pk_preflop.DEFAULTS)
        self.params.update(pk_postflop.DEFAULTS)
        self.debug = False  # True (local tests only): errors are raised
        self.opp = {}  # team name -> statistics (plain dicts)
        self.hole = None  # (card int, card int)
        self.player_id = 0
        self.history = []  # (player_id, kind, amount, street) this hand
        self.board = []  # card ints
        self.shown = {}  # player_id -> [card ints] shown at showdown
        self.won = {}  # player_id -> chips won this hand

    # -- the engine's calls --------------------------------------------------

    def seed(self, hand, player_id):
        self.player_id = player_id
        self.history = []
        self.board = []
        self.shown = {}
        self.won = {}
        try:
            self.hole = (pk_cards.to_int(hand[0]), pk_cards.to_int(hand[1]))
        except Exception:
            self.hole = None  # run() then only checks or folds

    def run(self, actions, game_state):
        start = time.perf_counter()
        me = self.player_id
        try:
            if game_state.call_amount == 0:
                safe = PlayerAction.call(me)
            else:
                safe = PlayerAction.fold(me)
        except Exception:
            safe = PlayerAction.fold(me)
        try:
            self._record(actions)
            if self.hole is None:
                return safe
            opp = self._opponent(game_state, me)
            if game_state.street == "preflop":
                kind, total = pk_preflop.decide(self, game_state, me, opp)
            else:
                kind, total = pk_postflop.decide(
                    self, game_state, me, opp, start)
            action = to_action(me, game_state, kind, total)
            game_state.validate_action(action)
            return action
        except Exception:
            if self.debug:
                raise
            return safe

    def end_game(self, actions, game_state):
        try:
            self._record(actions)
        except Exception:
            if self.debug:
                raise

    # -- per-hand bookkeeping ------------------------------------------------

    def _record(self, actions):
        """Adds the actions since our last turn to this hand's history."""
        for action in actions:
            kind = action.kind
            pid = action.player_id
            if kind == "reveal_card":
                card = pk_cards.to_int(action.card)
                if pid == DEALER:
                    self.board.append(card)
                else:
                    self.shown.setdefault(pid, []).append(card)
            elif kind == "win":
                self.won[pid] = self.won.get(pid, 0) + action.amount
            else:
                street = STREETS.get(len(self.board), "preflop")
                self.history.append((pid, kind, action.amount, street))

    def _opponent(self, gs, me):
        """The other player still in the hand (heads-up: the other seat)."""
        for p in gs.players_in_hand:
            if p != me:
                return p
        return (me + 1) % gs.num_players


def to_action(me, gs, kind, total):
    """A legal PlayerAction for (kind, total): raises are clamped to the
    legal range (all in when little would be left), a raise that is not
    allowed becomes a call, and we never fold when checking is free."""
    if kind == "raise" and gs.can_raise:
        low, high = gs.raise_range
        total = int(max(low, min(high, total)))
        if total >= 0.9 * high:
            total = high
        return PlayerAction.raise_to(me, total)
    if kind == "fold" and gs.call_amount > 0:
        return PlayerAction.fold(me)
    return PlayerAction.call(me)
