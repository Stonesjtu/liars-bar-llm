import yaml
import argparse
import multiprocessing
from game import Game
from tqdm import tqdm

def run_single_game(game_info):
    """运行单场游戏"""
    game_num, player_configs = game_info
    print(f"\n=== 开始第 {game_num} 局游戏 ===")
    game = Game(player_configs)
    game.start_game()
    print(f"第 {game_num} 局游戏结束")
    return game.game_record

class MultiGameRunner:
    def __init__(self, player_configs: list[dict[str, str]], num_games: int = 10, max_parallel_requests: int = 20):
        """初始化多局游戏运行器

        Args:
            player_configs: 玩家配置列表
            num_games: 要运行的游戏局数
            max_parallel_requests: 最大并行请求数
        """
        self.player_configs = player_configs
        self.num_games = num_games
        self.max_parallel_requests = max_parallel_requests

    def run(self) -> None:
        """并行运行指定数量的游戏"""
        with multiprocessing.Pool(processes=self.max_parallel_requests) as pool:
            game_infos = [(i + 1, self.player_configs) for i in range(self.num_games)]
            results = list(tqdm(pool.imap(run_single_game, game_infos), total=self.num_games, desc="运行游戏"))
        # 在这里可以处理 results，例如保存游戏记录等
        print(f"\n所有 {self.num_games} 局游戏已完成。")

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
    parser.add_argument(
        '--max_parallel_requests',
        type=int,
        default=20,
        help='最大并行游戏数 (默认: 20)'
    )
    return parser.parse_args()

if __name__ == '__main__':
    args = parse_arguments()

    # 从 YAML 文件加载玩家配置
    with open(args.config, 'r') as f:
        config_data = yaml.safe_load(f)
    player_configs = config_data['player_configs']

    # 运行多次游戏
    runner = MultiGameRunner(player_configs, num_games=args.num_games, max_parallel_requests=args.max_parallel_requests)
    runner.run()