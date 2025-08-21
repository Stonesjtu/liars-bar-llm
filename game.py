import yaml
import argparse
import logging
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from typing import List, Dict
from player import LLMPlayer, HumanPlayer
from game_record import GameRecord
from game_server import GameServer
from player_client import PlayerClient

logger = logging.getLogger(__name__)
console = Console()

class Game:
    def __init__(self, player_configs: List[Dict[str, str]]) -> None:
        """初始化游戏"""
        players = []
        print(player_configs)
        for config in player_configs:
            player_type = config.pop('type', 'llm')
            if player_type == 'human':
                players.append(HumanPlayer(**config))
            else:
                players.append(LLMPlayer(**config))

        for player in players:
            player.init_opinions(players)

        self.clients = [PlayerClient(p) for p in players]
        self.game_record = GameRecord()
        self.game_record.start_game([c.name for c in self.clients])
        self.server = GameServer(players, self.game_record)

    def handle_play_cards(self, current_player_client: PlayerClient, next_player_client: PlayerClient) -> List[str]:
        round_base_info = self.game_record.get_latest_round_info()
        round_action_info = self.game_record.get_latest_round_actions(current_player_client.name, include_latest=True)
        play_decision_info = self.game_record.get_play_decision_info(current_player_client.name, next_player_client.name)

        play_result, reasoning = current_player_client.choose_cards_to_play(
            round_base_info, round_action_info, play_decision_info
        )

        console.print(Panel(f"[cyan]{current_player_client.name}[/cyan] 打出了 [bold]{len(play_result['played_cards'])}[/bold] 张牌。", expand=False))

        self.game_record.record_play(
            player_name=current_player_client.name,
            played_cards=play_result["played_cards"].copy(),
            remaining_cards=current_player_client.hand.copy(),
            play_reason=play_result["play_reason"],
            behavior=play_result["behavior"],
            next_player=next_player_client.name,
            play_thinking=reasoning
        )
        return play_result["played_cards"]

    def handle_challenge(self, current_player_client: PlayerClient, next_player_client: PlayerClient, played_cards: List[str]) -> PlayerClient:
        round_base_info = self.game_record.get_latest_round_info()
        round_action_info = self.game_record.get_latest_round_actions(next_player_client.name, include_latest=False)
        challenge_decision_info = self.game_record.get_challenge_decision_info(next_player_client.name, current_player_client.name)
        challenging_player_behavior = self.game_record.get_latest_play_behavior()
        extra_hint = "注意：其他玩家手牌均已打空。" if self.server.check_other_players_no_cards(next_player_client.player) else ""

        challenge_result, reasoning = next_player_client.decide_challenge(
            round_base_info, round_action_info, challenge_decision_info, challenging_player_behavior, extra_hint
        )

        if challenge_result["was_challenged"]:
            console.print(Panel(f"[bold yellow]{next_player_client.name} 决定质疑！[/bold yellow]\n理由: {challenge_result['challenge_reason']}", title="[red]质疑[/red]", expand=False))
            is_valid = self.server.is_valid_play(played_cards)
            self.game_record.record_challenge(
                was_challenged=True,
                reason=challenge_result["challenge_reason"],
                result=not is_valid,
                challenge_thinking=reasoning
            )
            return next_player_client if is_valid else current_player_client
        else:
            console.print(Panel(f"[green]{next_player_client.name} 选择不质疑。[/green]", expand=False))
            self.game_record.record_challenge(
                was_challenged=False,
                reason=challenge_result["challenge_reason"],
                result=None,
                challenge_thinking=reasoning
            )
            return None

    def handle_system_challenge(self, current_player_client: PlayerClient) -> None:
        logger.info(f"系统自动质疑 {current_player_client.name} 的手牌！")
        all_cards = current_player_client.hand.copy()
        current_player_client.player.hand.clear()

        self.game_record.record_play(
            player_name=current_player_client.name,
            played_cards=all_cards,
            remaining_cards=[],
            play_reason="最后一人，自动出牌",
            behavior="无",
            next_player="无",
            play_thinking=""
        )

        is_valid = self.server.is_valid_play(all_cards)
        self.game_record.record_challenge(
            was_challenged=True,
            reason="系统自动质疑",
            result=not is_valid,
            challenge_thinking=""
        )

        if is_valid:
            logger.info(f"系统质疑失败！{current_player_client.name} 的手牌符合规则。")
            self.game_record.record_shooting(shooter_name="无", bullet_hit=False)
            self.server.reset_round(record_shooter=False)
        else:
            logger.warning(f"系统质疑成功！{current_player_client.name} 的手牌违规，将执行射击惩罚。")
            self.server.perform_penalty(current_player_client.player)

    def play_round(self) -> None:
        current_player_client = self.clients[self.server.current_player_idx]

        if self.server.check_other_players_no_cards(current_player_client.player):
            self.handle_system_challenge(current_player_client)
            return

        table = Table(title=f"第 {self.server.round_count} 轮 - {current_player_client.name} 的回合")
        table.add_column("玩家", justify="center", style="cyan")
        table.add_column("手牌数", justify="center", style="magenta")
        table.add_column("子弹位置", justify="center", style="yellow")
        for c in self.clients:
            if c.alive:
                table.add_row(c.name, str(len(c.hand)), str(c.player.bullet_position))
        console.print(table)
        console.print(Panel(f"目标牌是 [bold red]{self.server.target_card}[/bold red]", expand=False))

        next_idx = self.server.find_next_player_with_cards(self.server.current_player_idx)
        next_player_client = self.clients[next_idx]

        played_cards = self.handle_play_cards(current_player_client, next_player_client)

        if next_player_client != current_player_client:
            client_to_penalize = self.handle_challenge(current_player_client, next_player_client, played_cards)
            if client_to_penalize:
                self.server.perform_penalty(client_to_penalize.player)
                if self.server.game_over:
                    winner_name = self.game_record.winner
                    console.print(Panel(f"[bold green]{winner_name} 获胜！[/bold green]", title="游戏结束", expand=False))
                return
            else:
                logger.info(f"{next_player_client.name} 选择不质疑，游戏继续。")

        self.server.current_player_idx = next_idx

    def start_game(self) -> None:
        self.server.deal_cards()
        self.server.choose_target_card()
        self.server.start_round_record()
        while not self.server.game_over:
            self.play_round()
        if self.server.game_over:
            winner_name = self.game_record.winner
            if winner_name:
                console.print(Panel(f"[bold green]{winner_name} 获胜！[/bold green]", title="游戏结束", expand=False))

def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='运行一场骗子吧游戏')
    parser.add_argument(
        '--config',
        type=str,
        default='config/gpt-oss.yaml',
        help='指定玩家配置文件的路径 (默认: config/gpt-oss.yaml)'
    )
    parser.add_argument(
        '--log-level',
        type=str,
        default='INFO',
        help='指定日志记录级别 (默认: INFO)'
    )
    return parser.parse_args()

def main():
    args = parse_arguments()

    # 配置日志记录
    log_level = getattr(logging, args.log_level.upper(), logging.INFO)
    logging.basicConfig(level=log_level, format='%(asctime)s - %(levelname)s - %(message)s')

    # 加载玩家配置
    with open(args.config, 'r') as f:
        config = yaml.safe_load(f)

    # 创建并开始游戏
    game = Game(config['player'])
    game.start_game()


if __name__ == "__main__":
    main()
