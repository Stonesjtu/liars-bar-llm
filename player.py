import random
import json
import re
import logging
from typing import List, Dict
from llm_client import LLMClient, logger as llm_logger
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

console = Console()

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "http://14.103.241.208:28888/v1/"
DEFAULT_API_KEY = "YOUR_API_KEY"
DEFAULT_MODEL_NAME = 'openai/gpt-oss-120b'

RULE_BASE_PATH = "prompt/rule_base.txt"
PLAY_CARD_PROMPT_TEMPLATE_PATH = "prompt/play_card_prompt_template.txt"
CHALLENGE_PROMPT_TEMPLATE_PATH = "prompt/challenge_prompt_template.txt"
REFLECT_PROMPT_TEMPLATE_PATH = "prompt/reflect_prompt_template.txt"

class Player:
    def __init__(self, name: str, **kwargs):
        """初始化玩家基类"""
        self.name = name
        self.hand = []
        self.alive = True
        self.bullet_position = random.randint(0, 5)
        self.current_bullet_position = 0
        self.opinions = {}

    def print_status(self) -> None:
        """打印玩家状态"""
        print(f"{self.name} - 手牌: {', '.join(self.hand)} - "
              f"子弹位置: {self.bullet_position} - 当前弹舱位置: {self.current_bullet_position}")

    def init_opinions(self, other_players: List["Player"]) -> None:
        """初始化对其他玩家的看法"""
        self.opinions = {
            player.name: "还不了解这个玩家"
            for player in other_players
            if player.name != self.name
        }

    def choose_cards_to_play(self, round_base_info: str, round_action_info: str, play_decision_info: str) -> Dict:
        raise NotImplementedError

    def decide_challenge(self, round_base_info: str, round_action_info: str, challenge_decision_info: str, challenging_player_performance: str, extra_hint: str) -> bool:
        raise NotImplementedError

    def reflect(self, alive_players: List[str], round_base_info: str, round_action_info: str, round_result: str) -> None:
        pass

    def process_penalty(self) -> bool:
        """处理射击惩罚，返回玩家是否存活"""
        if self.current_bullet_position == self.bullet_position:
            self.alive = False
            print(f"{self.name} 中弹身亡！")
        else:
            print(f"{self.name} 幸运地躲过一劫！")
        self.current_bullet_position = (self.current_bullet_position + 1) % 6
        return self.alive

class LLMPlayer(Player):
    def __init__(self, name: str, model: str = DEFAULT_MODEL_NAME, base_url: str = DEFAULT_BASE_URL, api_key: str = DEFAULT_API_KEY, reasoning_effort: str = 'low', **kwargs):
        super().__init__(name, **kwargs)
        self.llm_client = LLMClient(
            base_url=base_url,
            api_key=api_key,
            model=model,
            reasoning_effort=reasoning_effort
        )

    def _read_file(self, filepath: str) -> str:
        """读取文件内容"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return f.read().strip()
        except Exception as e:
            logger.error(f"读取文件 {filepath} 失败: {str(e)}")
            return ""

    def choose_cards_to_play(self,
                        round_base_info: str,
                        round_action_info: str,
                        play_decision_info: str) -> Dict:
        """
        玩家选择出牌

        Args:
            round_base_info: 轮次基础信息
            round_action_info: 轮次操作信息
            play_decision_info: 出牌决策信息

        Returns:
            tuple: (结果字典, 推理内容)
            - 结果字典包含played_cards, behavior和play_reason
            - 推理内容为LLM的原始推理过程
        """
        # 读取规则和模板
        rules = self._read_file(RULE_BASE_PATH)
        template = self._read_file(PLAY_CARD_PROMPT_TEMPLATE_PATH)

        # 准备当前手牌信息
        current_cards = ", ".join(self.hand)

        # 填充模板
        prompt = template.format(
            rules=rules,
            self_name=self.name,
            round_base_info=round_base_info,
            round_action_info=round_action_info,
            play_decision_info=play_decision_info,
            current_cards=current_cards
        )

        # 尝试获取有效的JSON响应，最多重试五次
        for attempt in range(5):
            # 每次都发送相同的原始prompt
            messages = [
                {"role": "user", "content": prompt}
            ]

            try:
                content, reasoning_content = self.llm_client.chat(messages)

                # 尝试从内容中提取JSON部分
                json_match = re.search(r'({[\s\S]*})', content)
                if json_match:
                    json_str = json_match.group(1)
                    result = json.loads(json_str)

                    # 验证JSON格式是否符合要求
                    if all(key in result for key in ["played_cards", "behavior", "play_reason"]):
                        # 确保played_cards是列表
                        if not isinstance(result["played_cards"], list):
                            result["played_cards"] = [result["played_cards"]]

                        # 确保选出的牌是有效的（从手牌中选择1-3张）
                        valid_cards = all(card in self.hand for card in result["played_cards"])
                        valid_count = 1 <= len(result["played_cards"]) <= 3

                        if valid_cards and valid_count:
                            # 从手牌中移除已出的牌
                            for card in result["played_cards"]:
                                self.hand.remove(card)
                            return result, reasoning_content

            except Exception as e:
                # 仅记录错误，不修改重试请求
                logger.warning(f"尝试 {attempt+1} 解析失败: {str(e)}")
        raise RuntimeError(f"玩家 {self.name} 的choose_cards_to_play方法在多次尝试后失败")

    def decide_challenge(self,
                        round_base_info: str,
                        round_action_info: str,
                        challenge_decision_info: str,
                        challenging_player_performance: str,
                        extra_hint: str) -> bool:
        """
        玩家决定是否对上一位玩家的出牌进行质疑

        Args:

            round_base_info: 轮次基础信息
            round_action_info: 轮次操作信息
            challenge_decision_info: 质疑决策信息
            challenging_player_performance: 被质疑玩家的表现描述
            extra_hint: 额外提示信息

        Returns:
            tuple: (result, reasoning_content)
            - result: 包含was_challenged和challenge_reason的字典
            - reasoning_content: LLM的原始推理过程
        """
        # 读取规则和模板
        rules = self._read_file(RULE_BASE_PATH)
        template = self._read_file(CHALLENGE_PROMPT_TEMPLATE_PATH)
        self_hand = f"你现在的手牌是: {', '.join(self.hand)}"

        # 填充模板
        prompt = template.format(
            rules=rules,
            self_name=self.name,
            round_base_info=round_base_info,
            round_action_info=round_action_info,
            self_hand=self_hand,
            challenge_decision_info=challenge_decision_info,
            challenging_player_performance=challenging_player_performance,
            extra_hint=extra_hint
        )

        # 尝试获取有效的JSON响应，最多重试五次
        for attempt in range(5):
            # 每次都发送相同的原始prompt
            messages = [
                {"role": "user", "content": prompt}
            ]

            try:
                content, reasoning_content = self.llm_client.chat(messages)

                # 解析JSON响应
                json_match = re.search(r'({[\s\S]*})', content)
                if json_match:
                    json_str = json_match.group(1)
                    result = json.loads(json_str)

                    # 验证JSON格式是否符合要求
                    if all(key in result for key in ["was_challenged", "challenge_reason"]):
                        # 确保was_challenged是布尔值
                        if isinstance(result["was_challenged"], bool):
                            return result, reasoning_content

            except Exception as e:
                # 仅记录错误，不修改重试请求
                logger.warning(f"尝试 {attempt+1} 解析失败: {str(e)}")
        raise RuntimeError(f"玩家 {self.name} 的decide_challenge方法在多次尝试后失败")

    def reflect(self, alive_players: List[str], round_base_info: str, round_action_info: str, round_result: str) -> None:
        """
        玩家在轮次结束后对其他存活玩家进行反思，更新对他们的印象

        Args:
            alive_players: 还存活的玩家名称列表
            round_base_info: 轮次基础信息
            round_action_info: 轮次操作信息
            round_result: 轮次结果
        """
        # 读取反思模板
        template = self._read_file(REFLECT_PROMPT_TEMPLATE_PATH)

        # 读取规则
        rules = self._read_file(RULE_BASE_PATH)

        # 对每个存活的玩家进行反思和印象更新（排除自己）
        for player_name in alive_players:
            # 跳过对自己的反思
            if player_name == self.name:
                continue

            # 获取此前对该玩家的印象
            previous_opinion = self.opinions.get(player_name, "还不了解这个玩家")

            # 填充模板
            prompt = template.format(
                rules=rules,
                self_name=self.name,
                round_base_info=round_base_info,
                round_action_info=round_action_info,
                round_result=round_result,
                player=player_name,
                previous_opinion=previous_opinion
            )

            # 向LLM请求分析
            messages = [
                {"role": "user", "content": prompt}
            ]

            try:
                content, _ = self.llm_client.chat(messages)

                # 更新对该玩家的印象
                self.opinions[player_name] = content.strip()
                logger.info(f"{self.name} 更新了对 {player_name} 的印象")

            except Exception as e:
                logger.error(f"反思玩家 {player_name} 时出错: {str(e)}")



class HumanPlayer(Player):
    def __init__(self, name: str, **kwargs):
        super().__init__(name, **kwargs)

    def choose_cards_to_play(self, round_base_info: str, round_action_info: str, play_decision_info: str) -> Dict:
        console.print(Panel(round_base_info, title="轮次信息", border_style="green"))
        console.print(Panel(round_action_info, title="本轮操作", border_style="yellow"))
        
        status_panel = Panel(f"手牌: {', '.join(self.hand)}\n子弹位置: {self.bullet_position} | 当前弹舱: {self.current_bullet_position}", title=f"{self.name} 的回合", border_style="cyan")
        console.print(status_panel)

        while True:
            try:
                cards_str = Prompt.ask("请输入你要出的牌 (用逗号分隔, 例如: Q,Joker)")
                played_cards = [card.strip() for card in cards_str.split(',')]
                
                if not (1 <= len(played_cards) <= 3):
                    console.print("[bold red]你必须出1到3张牌。[/bold red]")
                    continue
                
                hand_copy = self.hand[:]
                valid_play = True
                for card in played_cards:
                    if card in hand_copy:
                        hand_copy.remove(card)
                    else:
                        valid_play = False
                        break
                
                if not valid_play:
                    console.print("[bold red]你出的牌必须是你手上的牌。[/bold red]")
                    continue

                for card in played_cards:
                    self.hand.remove(card)
                
                return {
                    "played_cards": played_cards,
                    "behavior": "常规出牌",
                    "play_reason": "玩家决策"
                }, "Human Input"
            except Exception as e:
                logger.warning(f"输入无效，请重试: {e}")
                console.print(f"[bold red]输入无效，请重试。[/bold red]")

    def decide_challenge(self, round_base_info: str, round_action_info: str, challenge_decision_info: str, challenging_player_performance: str, extra_hint: str) -> bool:
        console.print(Panel(round_base_info, title="轮次信息", border_style="green"))
        console.print(Panel(round_action_info, title="本轮操作", border_style="yellow"))
        console.print(Panel(challenge_decision_info, title="质疑阶段", border_style="red"))
        
        status_panel = Panel(f"手牌: {', '.join(self.hand)}\n子弹位置: {self.bullet_position} | 当前弹舱: {self.current_bullet_position}", title=f"{self.name} 的回合", border_style="cyan")
        console.print(status_panel)

        if extra_hint:
            console.print(Panel(f"[bold magenta]提示: {extra_hint}[/bold magenta]"))

        while True:
            choice = Prompt.ask("你是否要质疑?", choices=["yes", "no"], default="no")
            if choice == 'yes':
                return {"was_challenged": True, "challenge_reason": "玩家决策"}, "Human Input"
            elif choice == 'no':
                return {"was_challenged": False, "challenge_reason": "玩家决策"}, "Human Input"

    def reflect(self, alive_players: List[str], round_base_info: str, round_action_info: str, round_result: str) -> None:
        pass