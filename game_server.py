import random
import logging
from typing import List, Optional, Dict
from player import Player
from game_record import GameRecord, PlayerInitialState

logger = logging.getLogger(__name__)

class GameServer:
    def __init__(self, players: List[Player], game_record: GameRecord):
        self.players = players
        self.game_record = game_record
        self.deck: List[str] = []
        self.target_card: Optional[str] = None
        self.current_player_idx: int = random.randint(0, len(self.players) - 1)
        self.last_shooter_name: Optional[str] = None
        self.game_over: bool = False
        self.round_count = 0

    def _create_deck(self) -> List[str]:
        """创建并洗牌牌组"""
        deck = ['Q'] * 6 + ['K'] * 6 + ['A'] * 6 + ['Joker'] * 2
        random.shuffle(deck)
        return deck

    def deal_cards(self) -> None:
        """发牌并清空旧手牌"""
        self.deck = self._create_deck()
        for player in self.players:
            if player.alive:
                player.hand.clear()
        # 每位玩家发 5 张牌
        for _ in range(5):
            for player in self.players:
                if player.alive and self.deck:
                    player.hand.append(self.deck.pop())
                    logger.info(f"{player.name}'s hand: {player.hand}")

    def choose_target_card(self) -> None:
        """随机选择目标牌"""
        self.target_card = random.choice(['Q', 'K', 'A'])
        logger.info(f"目标牌是: {self.target_card}")

    def start_round_record(self) -> None:
        """开始新的回合，并在 `GameRecord` 里记录信息"""
        self.round_count += 1
        starting_player = self.players[self.current_player_idx].name
        player_initial_states = [
            PlayerInitialState(
                player_name=player.name,
                bullet_position=player.bullet_position,
                current_gun_position=player.current_bullet_position,
                initial_hand=player.hand.copy()
            )
            for player in self.players if player.alive
        ]

        round_players = [player.name for player in self.players if player.alive]

        player_opinions = {}
        for player in self.players:
            player_opinions[player.name] = {}
            for target, opinion in player.opinions.items():
                player_opinions[player.name][target] = opinion

        self.game_record.start_round(
            round_id=self.round_count,
            target_card=self.target_card,
            round_players=round_players,
            starting_player=starting_player,
            player_initial_states=player_initial_states,
            player_opinions=player_opinions
        )

    def is_valid_play(self, cards: List[str]) -> bool:
        return all(card == self.target_card or card == 'Joker' for card in cards)

    def find_next_player_with_cards(self, start_idx: int) -> int:
        idx = start_idx
        for _ in range(len(self.players)):
            idx = (idx + 1) % len(self.players)
            if self.players[idx].alive and self.players[idx].hand:
                return idx
        return start_idx

    def perform_penalty(self, player: Player) -> None:
        logger.info(f"玩家 {player.name} 开枪！")
        still_alive = player.process_penalty()
        self.last_shooter_name = player.name
        self.game_record.record_shooting(
            shooter_name=player.name,
            bullet_hit=not still_alive
        )
        if not still_alive:
            logger.warning(f"{player.name} 已死亡！")
        if not self.check_victory():
            self.reset_round(record_shooter=True)

    def reset_round(self, record_shooter: bool) -> None:
        logger.info("小局游戏重置，开始新的一局！")
        alive_players = self.handle_reflection()
        self.deal_cards()
        self.choose_target_card()
        if record_shooter and self.last_shooter_name:
            shooter_idx = next((i for i, p in enumerate(self.players)
                                if p.name == self.last_shooter_name), None)
            if shooter_idx is not None and self.players[shooter_idx].alive:
                self.current_player_idx = shooter_idx
            else:
                logger.warning(f"{self.last_shooter_name} 已死亡，顺延至下一个存活且有手牌的玩家")
                self.current_player_idx = self.find_next_player_with_cards(shooter_idx or 0)
        else:
            self.last_shooter_name = None
            self.current_player_idx = self.players.index(random.choice(alive_players))
        self.start_round_record()
        logger.info(f"从 {self.players[self.current_player_idx].name} 开始新的一轮！")

    def check_victory(self) -> bool:
        alive_players = [p for p in self.players if p.alive]
        if len(alive_players) == 1:
            winner = alive_players[0]
            logger.info(f"\n{winner.name} 获胜！")
            self.game_record.finish_game(winner.name)
            self.game_over = True
            return True
        return False

    def check_other_players_no_cards(self, current_player: Player) -> bool:
        others = [p for p in self.players if p != current_player and p.alive]
        return all(not p.hand for p in others)

    def handle_reflection(self) -> List[Player]:
        alive_players = [p for p in self.players if p.alive]
        alive_player_names = [p.name for p in alive_players]
        round_base_info = self.game_record.get_latest_round_info()
        for player in alive_players:
            round_action_info = self.game_record.get_latest_round_actions(player.name, include_latest=True)
            round_result = self.game_record.get_latest_round_result(player.name)
            player.reflect(
                alive_players=alive_player_names,
                round_base_info=round_base_info,
                round_action_info=round_action_info,
                round_result=round_result
            )
        return alive_players