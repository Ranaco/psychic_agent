from google.adk.agents import Agent
from google.adk.tools.tool_context import ToolContext
from google.adk.sessions import InMemorySessionService
from google.adk.runners import Runner
from multi_tool_agent.agent import root_agent
from psychic_agent.setup_env.env import load_env
from google.genai import types
import requests
import os
import asyncio

load_env()

async def call_agent_async(query: str, runner, user_id, session_id):
  """Sends a query to the agent and prints the final response."""
  print(f"\n>>> User Query: {query}")

  content = types.Content(role='user', parts=[types.Part(text=query)])

  final_response_text = "Agent did not produce a final response."

  async for event in runner.run_async(user_id=user_id, session_id=session_id, new_message=content):
      if event.is_final_response():
          if event.content and event.content.parts:
             final_response_text = event.content.parts[0].text
          elif event.actions and event.actions.escalate:
             final_response_text = f"Agent escalated: {event.error_message or 'No specific message.'}"
          break 

  print(f"<<< Agent Response: {final_response_text}")

def get_weather_tool(city: str, tool_context: ToolContext) -> dict:
    """Provides the current weather for a given city.

    Args:
        city (str): The name of the city to get the weather for.
    
    Returns:
        dict: The weather report. This contains a status and a report.
              If the status is "success", the report will contain the weather report.
              in the format: "{
                  'status': 'success',
                  'report': {
                    'temperature': 25,
                    'condition': 'sunny',
                    'city':'<city-name>'
                  }
                }"
              If the status is "error", the report will contain an error message.
    """
    print(f"--- Tool: get_weather_tool called with city: {city} ---")

    if tool_context and not tool_context.state:
        tool_context.state = {}
    
    try:
        response = requests.get(f"https://api.openweathermap.org/data/2.5/weather?q={city}&appId={os.environ['OPEN_WEATHER_API_KEY']}&units=metrices") 
        response.raise_for_status()
        if response.status_code == 200:
            weather = response.json()

            tool_context.state['last_city_query'] = {
                'city': city,
                'temperature': weather['main']['temp'],
                'condition': weather['weather'][0]['description'],
                'city': weather['name']
            }

            return {
                'status':'success',
                'report': {
                    'temperature': weather['main']['temp'],
                    'condition': weather['weather'][0]['description'],
                    'city': weather['name']
                }
            }
        else:
            return {
                'status':'error',
            'report': f"Error getting weather for city: {city}"
            }
    except Exception as e:
        return {
            'status':'error',
            'report': f"Error getting weather for city: {city}"
        }


MODEL_GEMINI_2_5_FLASH = "gemini-2.5-flash-preview-04-17"


weather_agent = Agent(
    model=MODEL_GEMINI_2_5_FLASH,
    name="weather_agent",
    description="A weather agent that can provide the current weather for a given city.",
    instruction="""
    You are a weather agent that can provide the current weather for a given city.
    You can use the get_weather_tool to get the weather for a city.
    
    If the user asks you to get the weather for a city, you should use the get_weather_tool to get the weather for the city.
    If the user asks you to get the weather for a city and you have already provided the weather for the city, you should use the get_weather_tool to get the weather for the city.

    Point to be noted:
    - You should be very polite and try answering differently for everytime,
    - Your mood is very light and happy and you are very friendly.
    - You should be very short and sweet and you should not be very long.
    """,
    tools=[get_weather_tool],
)

session_service = InMemorySessionService()

initial_state = {
    "last_city_query": None
}

session = session_service.create_session(
    app_name="weather_ai_app",
    user_id="12345",
    session_id="12345",
    state=initial_state
)

runner = Runner(
    app_name="weather_ai_app",
    agent=weather_agent,
    session_service=session_service,
)

async def run_conversation():
    call_agent = lambda query: call_agent_async(query, runner, "12345", "12345")

    print("Welcome to the weather agent!")
    print("Type 'exit' to quit.")

    await call_agent("Hello, Mark here!")

    await call_agent("What is the weather like in London?")

    await call_agent("What about Paris?")

    await call_agent("What about Bihar?")
# if __name__ == "__main__":
#     print(get_weather_tool("London"))
#     print(get_weather_tool("London"))

root_agent=weather_agent

if __name__ == "__main__":
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        loop.run_until_complete(run_conversation())
    except Exception as e:
        print(e)
    finally:
        pending_tasks = asyncio.all_tasks(loop=loop)
        for task in pending_tasks:
            task.cancel()
            
        if pending_tasks:
            loop.run_until_complete(asyncio.gather(*pending_tasks, return_exceptions=True))
            
        loop.close()