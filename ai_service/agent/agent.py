from langchain.chat_models import init_chat_model
from typing import List
from tool import Tool

class Agent:
    def __init__(self, model_name: str, model_provider: str, temperature: float = 0):
        self.tools : List[Tool] = []
        self.messages : str = []
        self.system_prompt = """"""

        self.llm = init_chat_model(
            model=model_name,
            model_provider=model_provider,
            temperature=temperature
        )
        
        self.llm_with_tools = self.llm.bind_tools(self.tools)

    def init_system_prompt():
        pass

    def run(self, query: str):
        messages = self.messages + [{"role": "user", "content": query}]
        return self.llm_with_tools.invoke(messages)

    def switch_model(self, model_name: str, model_provider: str, temperature: int):
        self.llm = init_chat_model(
            model=model_name,
            model_provider=model_provider,
            temperature=temperature
        )
        self.llm_with_tools = self.llm.bind_tools(self.tools)

    def add_tool(self, tool):
        self.tools.append(tool)
        self.llm_with_tools = self.llm.bind_tools(self.tools)

    def add_message(self, message):
        self.messages.append(message)

    def clear_messages(self):
        self.messages = []