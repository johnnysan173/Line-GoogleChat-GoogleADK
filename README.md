# Line-GoogleChat-GoogleADK
Dinner Planner Bot: A Google ADK starter project demonstrating structured Sequential Agent workflows. Takes a meal idea and generates a full plan (dish, shopping list, recipe). This project shows how to integrate ADK intelligence with LINE Messenger and Google Chat via FastAPI webhooks. Perfect for learning core ADK concepts quickly.

# **Dinner Planner Bot: Simple Design Document**

## **1\. Overview and Purpose**

| Field | Description |
| :---- | :---- |
| **Project Name** | Dinner Planner Bot (Sequential) |
| **Goal** | Provide users with a complete dinner plan (idea, shopping list, and recipe) based on a text prompt (e.g., "fast dinner," "Chinese food"). |
| **Core Technology** | **Google Agent Development Kit (ADK)** for building a multi-step planning pipeline. |
| **Integration Points** | **LINE Messenger** and **Google Chat** via webhooks. |

## **2\. Architecture and Data Flow**

The application uses **FastAPI** as the web server and the **Google ADK** for structured intelligence, following a standard **Webhook → Core Logic → Response** pattern.

### **A. Execution Flow (User Query to Response)**

1. **Incoming Request:** A user sends a message on LINE or Google Chat.  
2. **Webhook:** Request hits the appropriate FastAPI endpoint (/line-webhook or /google-chat-webhook).  
3. **Session Management:** The handler calls get\_or\_create\_session() to retrieve the user's conversation context.  
4. **Agent Run:** The query is passed to the **ADK Runner**, which executes the dinner\_pipeline.  
5. **Pipeline Execution:** The sequential agent processes the steps: Idea → Shopping List → Recipe.  
6. **Reply:** The webhook handler sends the final text back to the user via the platform's API.

## **3\. Key Components**

### **A. Core Agents (The Sequential Pipeline)**

The dinner\_pipeline uses three sequential agents to build the full recipe plan.

| Step | Agent Name | Output Key | Role |
| :---- | :---- | :---- | :---- |
| 1 | IdeaAgent | dish\_name | Proposes a single, specific dish name based on the user's query. |
| 2 | ShoppingAgent | shopping\_list | Generates a 5-item shopping list using the dish\_name. |
| 3 | RecipeAgent | (Final Output) | Formats all gathered data into the final, comprehensive recipe response. |

### **B. Webhook Endpoints**

| Endpoint | Method | Purpose |
| :---- | :---- | :---- |
| /line-webhook | POST | Handles incoming messages from **LINE**. Validates signature and sends reply via Line API. |
| /google-chat-webhook | POST | Handles incoming messages from **Google Chat**. Returns a simple JSON response. |

## **4\. Configuration and Environment Variables**

The application requires these variables to be loaded from the environment (e.g., a .env file).

| Variable | Required? | Usage |
| :---- | :---- | :---- |
| ChannelSecret | **Yes** | Used for LINE webhook signature validation. |
| ChannelAccessToken | **Yes** | Used to send reply messages via the LINE API. |
| GOOGLE\_API\_KEY | **Yes (Conditional)** | Required for GenAI API access if USE\_VERTEX is not "True". |
| GOOGLE\_GENAI\_USE\_VERTEXAI | No | If set to "True", switches the ADK model access to use Vertex AI endpoints. |

## **5\. Getting Started (Local Development)**

Follow these steps to set up and run the bot on your local machine for development and testing.

### **A. Setup and Run**

1. **Clone the Repository:** Clone the project files to your local machine.  
2. **Configure Environment Variables:** Create a .env file in the root directory and populate it with the required values listed in **Section 4**.  
3. **Install Dependencies:** Install the necessary Python libraries:  
   pip install \-r requirements.txt

4. **Start the Server:** Run the FastAPI application locally with auto-reload enabled:  
   uvicorn main:app \--reload

   The server will typically run on http://127.0.0.1:8000.

### **B. Local Webhook Testing (Ngrok)**

Since platforms like LINE and Google Chat require public URLs for their webhooks, you must use a tool like **Ngrok** to expose your local server to the internet during development.

1. **Install and Run Ngrok:** Open a new terminal window and expose your local server port (default is 8000):  
   ngrok http 8000

2. **Obtain Public URL:** Ngrok will provide a temporary public URL (e.g., https://xxxx.ngrok-free.app).  
3. **Set Webhooks:** Use this temporary Ngrok URL as the base URL when configuring the LINE and Google Chat webhooks (see **Section 6**).

## **6\. Deployment and Interface Configuration**

Once the FastAPI application is successfully deployed to a **stable, public server**, the URL must be registered with the respective messaging platforms to enable communication.

### **A. Webhook Setup Steps (Production)**

1. **Get Public URL:** Obtain the public base URL of the deployed FastAPI application (e.g., https://your-app-domain.com).  
2. Configure LINE Webhook: In the LINE Developer Console, set the webhook URL to the base URL plus the LINE endpoint:  
   https://your-app-domain.com/line-webhook  
3. Configure Google Chat Webhook: In the Google Chat application settings, set the webhook URL (or bot endpoint) to the base URL plus the Google Chat endpoint:  
   https://your-app-domain.com/google-chat-webhook
