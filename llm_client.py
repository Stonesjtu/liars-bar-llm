import logging
import datetime
from openai import OpenAI

# 配置日志
log_filename = f"game_{datetime.datetime.now().strftime('%Y%m%d')}.log"
logging.basicConfig(
    filename=log_filename,
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    encoding='utf-8'
)
logger = logging.getLogger(__name__)

class LLMClient:
    def __init__(self, base_url: str, api_key: str, model: str, reasoning_effort: str = 'low'):
        """初始化LLM客户端"""
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url
        )
        self.model = model
        self.reasoning_effort = reasoning_effort

    def chat(self, messages):
        """与LLM交互

        Args:
            messages: 消息列表
            model: 使用的LLM模型

        Returns:
            tuple: (content, reasoning_content)
        """
        try:
            logger.info(f"LLM请求: {messages}")
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                reasoning_effort=self.reasoning_effort,
            )
            if response.choices:
                message = response.choices[0].message
                content = message.content if message.content else ""
                reasoning_content = getattr(message, "reasoning_content", "")
                logger.info(f"LLM推理内容: {content}")
                return content, reasoning_content

            return "", ""

        except Exception as e:
            logger.error(f"LLM调用出错: {str(e)}")
            return "", ""