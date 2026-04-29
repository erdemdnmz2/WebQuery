from ai_service.agent.agent import Agent

class AgentManager:
    def __init__(self):
        self.agents = {}

    def add_agent(self, agent: Agent):
        self.agents[agent.name] = agent

    def get_agent(self, agent_name: str) -> Agent:
        return self.agents[agent_name]

    def remove_agent(self, agent_name: str):
        del self.agents[agent_name]

    def get_agents(self):
        return self.agents

    def clear_agents(self):
        self.agents = {}

    def run(self, agent_name: str, query: str):
        agent = self.get_agent(agent_name)
        return agent.run(query)

    def switch_model(self, agent_name: str, model_name: str, model_provider: str):
        agent = self.get_agent(agent_name)
        agent.switch_model(model_name, model_provider)

    def add_tool(self, agent_name: str, tool):
        agent = self.get_agent(agent_name)
        agent.add_tool(tool)

    def add_message(self, agent_name: str, message):
        agent = self.get_agent(agent_name)
        agent.add_message(message)

    def clear_messages(self, agent_name: str):
        agent = self.get_agent(agent_name)
        agent.clear_messages()

    def clear_all_messages(self):
        for agent in self.agents.values():
            agent.clear_messages()

    def clear_all_agents(self):
        self.agents = {}

    def clear_all_tools(self):
        for agent in self.agents.values():
            agent.tools = []

    def clear_all_tools_and_messages(self):
        for agent in self.agents.values():
            agent.tools = []
            agent.messages = []