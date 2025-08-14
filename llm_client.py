from openai import OpenAI

class LLMClient:
    def __init__(self, base_url: str, api_key: str, model: str):
        """初始化LLM客户端"""
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url
        )
        self.model = model

    def chat(self, messages):
        """与LLM交互

        Args:
            messages: 消息列表
            model: 使用的LLM模型

        Returns:
            tuple: (content, reasoning_content)
        """
        try:
            print(f"LLM请求: {messages}")
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                reasoning_effort='low',
            )
            if response.choices:
                message = response.choices[0].message
                content = message.content if message.content else ""
                reasoning_content = getattr(message, "reasoning_content", "")
                print(f"LLM推理内容: {content}")
                return content, reasoning_content

            return "", ""

        except Exception as e:
            print(f"LLM调用出错: {str(e)}")
            return "", ""