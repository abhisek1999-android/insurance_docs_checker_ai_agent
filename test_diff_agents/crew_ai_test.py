"""
CrewAI - Multi-Agent Marketing Strategy Meeting
================================================
Multi-agent collaboration where different agents with specialized roles
work together on complex tasks like marketing campaigns.

Requirements:
- crewai
- langchain
- openai
- OpenAI API key

Author: AI Agents Article Examples
"""

from crewai import Agent, Task, Crew, Process, LLM
import os
from dotenv import load_dotenv

load_dotenv()

# Initialize the language model (CrewAI uses LiteLLM under the hood)
llm = LLM(model="groq/compound-beta", api_key=os.getenv("GROQ_API_KEY"))

# Define specialized marketing agents
market_researcher = Agent(
    role="Market Research Specialist",
    goal="Uncover deep insights about target customers and market trends",
    backstory="""You are an experienced market researcher who has 
    worked with Fortune 500 companies to launch successful products.
    You excel at data analysis and trend identification.""",
    llm=llm,
    verbose=True
)

creative_director = Agent(
    role="Creative Director",
    goal="Develop compelling messaging and creative concepts",
    backstory="""You have 15 years of experience in advertising,
    having created campaigns for major brands. You have a gift
    for finding the emotional core of any product.""",
    llm=llm,
    verbose=True
)

channel_strategist = Agent(
    role="Digital Channel Strategist",
    goal="Design optimal multi-channel distribution strategy",
    backstory="""You are a digital marketing veteran who understands
    the nuances of every platform from LinkedIn to TikTok.
    You know which messages work where.""",
    llm=llm,
    verbose=True
)

# Define tasks for each agent
research_task = Task(
    description="Research the SaaS project management tool market.",
    expected_output="Comprehensive market analysis document",
    agent=market_researcher
)

creative_task = Task(
    description="Develop brand messaging and creative concepts",
    expected_output="Campaign brief with messaging framework",
    agent=creative_director
)

channel_task = Task(
    description="Create a multi-channel marketing plan",
    expected_output="Detailed channel strategy document",
    agent=channel_strategist
)

# Assemble the crew
crew = Crew(
    agents=[market_researcher, creative_director, channel_strategist],
    tasks=[research_task, creative_task, channel_task],
    process=Process.sequential,
    verbose=True
)

if __name__ == "__main__":
    # Execute the collaborative marketing project
    result = crew.kickoff()

    print("\n=== MARKETING CAMPAIGN OUTPUT ===")
    print(result)