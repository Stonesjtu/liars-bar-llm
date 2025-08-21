from typing import Dict, List
from player import Player

class PlayerClient:
    def __init__(self, player: Player):
        self.player = player

    @property
    def name(self):
        return self.player.name

    @property
    def alive(self):
        return self.player.alive

    @property
    def hand(self):
        return self.player.hand

    def choose_cards_to_play(self, round_base_info: str, round_action_info: str, play_decision_info: str) -> Dict:
        return self.player.choose_cards_to_play(round_base_info, round_action_info, play_decision_info)

    def decide_challenge(self, round_base_info: str, round_action_info: str, challenge_decision_info: str, challenging_player_performance: str, extra_hint: str) -> bool:
        return self.player.decide_challenge(round_base_info, round_action_info, challenge_decision_info, challenging_player_performance, extra_hint)

    def reflect(self, alive_players: List[str], round_base_info: str, round_action_info: str, round_result: str) -> None:
        self.player.reflect(alive_players, round_base_info, round_action_info, round_result)