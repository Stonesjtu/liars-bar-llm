import yaml
import argparse
from game import Game

class MultiGameRunner:
    def __init__(self, player_configs: list[dict[str, str]], num_games: int = 10):
        """初始化多局游戏运行器

        Args:
            player_configs: 玩家配置列表
            num_games: 要运行的游戏局数
        """
        self.player_configs = player_configs
        self.num_games = num_games

    def run_games(self) -> None:
        """运行指定数量的游戏"""
        for game_num in range(1, self.num_games + 1):
            print(f"\n=== 开始第 {game_num}/{self.num_games} 局游戏 ===")

            # 创建并运行新游戏
            game = Game(self.player_configs)
            game.start_game()

            print(f"第 {game_num} 局游戏结束")

def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='运行多场骗子吧游戏并收集统计数据')
    parser.add_argument(
        '--config',
        type=str,
        default='config/gpt-oss.yaml',
        help='指定玩家配置文件的路径 (默认: config/gpt-oss.yaml)'
    )
    parser.add_argument(
        '--num_games',
        type=int,
        default=100,
        help='要运行的游戏次数 (默认: 100)'
    )
    return parser.parse_args()

if __name__ == '__main__':
    args = parse_arguments()

    # 从 YAML 文件加载玩家配置
    with open(args.config, 'r') as f:
        config_data = yaml.safe_load(f)
    player_configs = config_data['player_configs']

    # 运行多次游戏
    runner = MultiGameRunner(player_configs, num_games=args.num_games)
    runner.run_games()