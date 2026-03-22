import os
from dotenv import load_dotenv

import phi
from phi.agent import Agent
from phi.playground import Playground, serve_playground_app

# Models
from phi.model.groq import Groq
# Optional fallback (uncomment if you have OPENAI_API_KEY set)
# from phi.model.openai import OpenAIChat

# Tools
from phi.tools.yfinance import YFinanceTools
from phi.tools.duckduckgo import DuckDuckGo

# =============================
# Environment & API Keys
# =============================
load_dotenv()

# If your Phi SDK expects api key like this, keep as-is to match your current setup
phi.api = os.getenv("PHI_API_KEY")

# =============================
# Common Guardrail Instructions
# =============================
COMMON_GUARDRAILS = [
    "Be precise and factual.",
    "Never fabricate numbers, quotes, tickers, or sources.",
    "If a value cannot be found, say 'Not available' rather than guessing.",
    "Prefer concise, well-structured answers over long paragraphs.",
]

# =============================
# Shared Response Template (consistency across agents)
# =============================
STRUCTURE_INSTRUCTION = (
    "Always respond using this structure in clean Markdown:\n"
    "## Overview\n"
    "A brief summary in 1-3 bullet points.\n\n"
    "## Key Data\n"
    "Use one or more Markdown tables. Include column headers.\n\n"
    "## Insights\n"
    "3-6 bullet points: trends, anomalies, risks, opportunities.\n\n"
    "## Sources\n"
    "Bullet list of URLs or titles (hyperlinked)."
)

# =============================
# Tools
# =============================
ddg = DuckDuckGo()
yf = YFinanceTools(
    stock_price=True,
    analyst_recommendations=True,
    stock_fundamentals=True,
    company_news=True,
)

# =============================
# Web Search Agent (Improved)
# =============================
web_search_agent = Agent(
    name="Web Search Agent",
    role=(
        "Search the web for up-to-date, trustworthy information. "
        "Synthesize results succinctly, avoid raw dumps."
    ),
    model=Groq(id="llama-3.3-70b-versatile"),
    tools=[ddg],
    instructions=[
        "Summarize findings as bullet points before links.",
        "Always include source URLs in the 'Sources' section.",
        "Never return raw HTML/JSON.",
        STRUCTURE_INSTRUCTION,
        *COMMON_GUARDRAILS,
    ],
    show_tool_calls=True,
    markdown=True,
)

# =============================
# Finance Agent (Improved + Multi-Tool)
# =============================
finance_agent = Agent(
    name="Finance AI Agent",
    role=(
        "Retrieve market data, fundamentals, analyst recommendations, and company news. "
        "Cross-check headlines with web search when helpful."
    ),
    model=Groq(id="llama-3.3-70b-versatile"),
    tools=[
        yf,            # primary financial data
        ddg,           # supplemental news/context
    ],
    instructions=[
        "Always use Markdown tables with clear headers for numbers.",
        "When analyzing a ticker: (1) fetch price & fundamentals, (2) pull recent news, (3) provide short analysis.",
        "If multiple tickers are provided, make one table per ticker, then a comparative insights list.",
        "If data is stale or missing, state it explicitly.",
        STRUCTURE_INSTRUCTION,
        *COMMON_GUARDRAILS,
    ],
    show_tool_calls=True,
    markdown=True,
)

# (Optional) Fallback model if you want extra robustness (commented out by default)
# fallback_model = OpenAIChat(id="gpt-4o-mini")
# web_search_agent.fallback_model = fallback_model
# finance_agent.fallback_model = fallback_model

# =============================
# Coordinator / Orchestrator Agent
# =============================
coordinator_agent = Agent(
    name="Coordinator Agent",
    role=(
        "Understand the user query, decide which specialized agent(s) to call, "
        "and synthesize a single, clean report."
    ),
    model=Groq(id="llama-3.3-70b-versatile"),
    agents=[finance_agent, web_search_agent],
    instructions=[
        # Routing policy
        (
            "Routing policy:\n"
            "- If the query is primarily about stocks/markets/tickers -> call Finance AI Agent.\n"
            "- If it's general knowledge/current events -> call Web Search Agent.\n"
            "- If both finance data and current news are relevant -> call BOTH and merge.\n"
            "- If the user asks to compare multiple tickers -> call Finance AI Agent and ensure comparison.\n"
            "- If tools return insufficient data -> explicitly say so and add 'Next steps' suggestions."
        ),
        # Synthesis policy
        (
            "Synthesis policy:\n"
            "- Merge sub-agent outputs into ONE response using the standard structure.\n"
            "- Keep it concise; surface the key numbers and 3-6 insights.\n"
            "- Always include a 'Sources' section when Web Search Agent or news tools are used."
        ),
        # Clarification policy (no external memory)
        (
            "If the user request is ambiguous (e.g., no ticker symbol, timeframe, or market), "
            "ask at most ONE concise clarifying question, then proceed with reasonable assumptions."
        ),
        STRUCTURE_INSTRUCTION,
        *COMMON_GUARDRAILS,
    ],
    show_tool_calls=True,
    markdown=True,
)

# =============================
# Playground App
# =============================
# Expose the single, unified Coordinator by default. Optionally also show sub-agents for power users.
app = Playground(agents=[coordinator_agent, finance_agent, web_search_agent]).get_app()


if __name__ == "__main__":
    # Run with: uvicorn playground:app --reload  (or rely on serve_playground_app below)
    serve_playground_app("playground:app", reload=True)