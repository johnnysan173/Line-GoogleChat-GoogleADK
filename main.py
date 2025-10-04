import os
import sys
import aiohttp
from dotenv import load_dotenv

from fastapi import Request, FastAPI, HTTPException
from linebot import AsyncLineBotApi, WebhookParser
from linebot.aiohttp_async_http_client import AiohttpAsyncHttpClient
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextSendMessage

from google.adk.agents import Agent, LlmAgent, SequentialAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

# Load environment variables from .env file
load_dotenv()

# --- Configuration & Validation ---
APP_NAME = "linebot_adk_app"

# LINE Bot configuration
channel_secret = os.getenv("ChannelSecret")
channel_access_token = os.getenv("ChannelAccessToken")

if channel_secret is None:
    print("Specify ChannelSecret as environment variable.")
    sys.exit(1)
if channel_access_token is None:
    print("Specify ChannelAccessToken as environment variable.")
    sys.exit(1)

# Google GenAI / ADK configuration
USE_VERTEX = os.getenv("GOOGLE_GENAI_USE_VERTEXAI") or "FALSE"
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

if USE_VERTEX == "True":
    GOOGLE_CLOUD_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT")
    GOOGLE_CLOUD_LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION")
    if not GOOGLE_CLOUD_PROJECT:
        raise ValueError("Please set GOOGLE_CLOUD_PROJECT via env var or code when USE_VERTEX is true.")
    if not GOOGLE_CLOUD_LOCATION:
        raise ValueError("Please set GOOGLE_CLOUD_LOCATION via env var or code when USE_VERTEX is true.")
elif not GOOGLE_API_KEY:
    raise ValueError("Please set GOOGLE_API_KEY via env var or code.")


# --- FastAPI App Setup ---
app = FastAPI()
parser = WebhookParser(channel_secret)

# Global variables for LINE Bot API
session: aiohttp.ClientSession
async_http_client: AiohttpAsyncHttpClient
line_bot_api: AsyncLineBotApi

@app.on_event("startup")
async def startup_event():
    """Initializes aiohttp session and LINE Bot API client."""
    global session, async_http_client, line_bot_api
    session = aiohttp.ClientSession()
    async_http_client = AiohttpAsyncHttpClient(session)
    line_bot_api = AsyncLineBotApi(channel_access_token, async_http_client)
    print("✅ LINE Bot API initialized")


@app.on_event("shutdown")
async def shutdown_event():
    """Closes the aiohttp session."""
    await session.close()
    print("🛑 aiohttp session closed")


# --- Session Management ---
session_service = InMemorySessionService()
active_sessions = {} # Dictionary to track active sessions

async def get_or_create_session(user_id: str) -> str:
    """Gets an existing session ID or creates a new one for a user."""
    if user_id not in active_sessions:
        session_id = f"session_{user_id}"
        await session_service.create_session(
            app_name=APP_NAME, user_id=user_id, session_id=session_id
        )
        active_sessions[user_id] = session_id
        print(f"New session created for User = '{user_id}', Session = '{session_id}'")
    else:
        session_id = active_sessions[user_id]
        print(f"Using existing session for User='{user_id}', Session='{session_id}'")
    
    return session_id

# --- ADK Agent Definition (Sequential Pipeline) ---

# Step 1: Get the dinner idea.
step1_idea = LlmAgent(
    name="IdeaAgent",
    model="gemini-2.0-flash",
    instruction=(
        "あなたはプロの料理提案AIです。"
        "あなたの仕事は、ユーザーが入力した料理のジャンルやキーワードに「厳密に」基づいて、具体的な料理名を「一つだけ」提案することです。"
        "提案する料理名だけを日本語で出力し、他の余計な言葉は一切含めないでください。"
    ),
    output_key="dish_name",
)

# Step 2: Get the shopping list. Uses '{dish_name}' from the previous step.
step2_shopping_list = LlmAgent(
    name="ShoppingAgent",
    model="gemini-2.0-flash",
    instruction=(
        "あなたは几帳面な食料品プランナーです。料理「{dish_name}」に基づき、必要な材料の買い物リストを作成してください。"
        "箇条書きのシンプルなリスト形式で、5品目、日本語で返答してください。"
    ),
    output_key="shopping_list",
)

# Step 3: Get the recipe. Uses '{dish_name}' and '{shopping_list}' for the final output.
step3_recipe = LlmAgent(
    name="RecipeAgent",
    model="gemini-2.0-flash",
    instruction=(
        "あなたの仕事は、提供された料理名と買い物リストを、モバイルフレンドリーな最終的なレシピにまとめることです。"
        "「料理のアイデア」「買い物リスト」「作り方」の見出しを使って、簡潔な日本語の応答を**一つだけ**作成してください。\n\n"
        "料理名: {dish_name}\n"
        "買い物リスト:\n{shopping_list}"
    ),
) # No output_key here, as this is the final output.

# Create the sequential pipeline
dinner_pipeline = SequentialAgent(
    name="DinnerPipeline",
    sub_agents=[step1_idea, step2_shopping_list, step3_recipe],
)


# --- Core Logic ---

async def getRecipe(query: str, user_id: str) -> str:
    """
    Main function to run the dinner pipeline for a user query.
    Manages session and executes the ADK Runner.
    """
    print("--- Dinner Planner Bot (Sequential) ---")

    session_id = await get_or_create_session(user_id)

    runner = Runner(
        agent=dinner_pipeline,
        app_name=APP_NAME,
        session_service=session_service,
    )

    final_response = "Sorry, I couldn't come up with a plan."

    # Prepare the user's message in ADK format
    content = types.Content(role="user", parts=[types.Part(text=query)])

    print(f"\n⚙️ Dinner pipeline is running for user {user_id} . . .")
    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=content
    ):
        if event.is_final_response() and event.content and event.content.parts:
            final_response = event.content.parts[0].text

    print("\n--- Final Plan Response ---")
    print(final_response)
    print("---------------------------")
    return final_response


# --- Webhook Endpoints ---

@app.post("/line-webhook")
async def handle_callback(request: Request):
    """Handles incoming webhooks from LINE."""
    signature = request.headers.get("X-Line-Signature")
    if not signature:
        raise HTTPException(status_code=400, detail="Missing X-Line-Signature")
        
    print("Received LINE Webhook")
    body = await request.body()
    body = body.decode()

    try:
        events = parser.parse(body, signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    for event in events:
        if isinstance(event, MessageEvent) and event.message.type == "text":
            msg = event.message.text
            user_id = event.source.user_id
            print(f"Received message: {msg} from user: {user_id}")

            response = await getRecipe(msg, user_id)
            reply_msg = TextSendMessage(text=response)
            await line_bot_api.push_message(user_id, messages=reply_msg)
        
    return "OK"


@app.post("/google-chat-webhook")
async def handle_google_chat_callback(request: Request):
    """Handles incoming webhooks from Google Chat."""
    body = await request.json()
    print("Received Google Chat Webhook")

    # Only process messages
    event_type = body.get('type')
    if event_type == 'MESSAGE':
        # Extract the user's message and unique user ID
        user_message = body.get('message', {}).get('argumentText', '').strip()
        user_id = body.get('user', {}).get('name')

        if user_message and user_id:
            # Call your reusable core logic
            response_text = await getRecipe(user_message, user_id)

            # Return the simple JSON response that Google Chat expects
            return {"text": response_text}

    # Acknowledge other events like being added to a space
    return {"text": "Thank you for adding me!"}