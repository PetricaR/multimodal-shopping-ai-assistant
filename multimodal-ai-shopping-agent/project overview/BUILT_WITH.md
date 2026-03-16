# Built With

The Shopping AI Assistant was built using a modern, scalable tech stack, heavily leveraging Google Cloud and the latest Gemini multimodal capabilities.

## 🧠 Core AI & Machine Learning

* **Gemini 2.5 Flash Native Audio**: The "brain" of our agent. We use the Realtime WebSocket API (`gemini-2.5-flash-native-audio-latest`) for ultra-low latency, human-like voice interaction with native speech-to-speech capabilities.
* **Vertex AI Vector Search**: Powers our `find_shopping_items` tool, enabling semantic and similarity-based product discovery across a large Romanian grocery catalog.

## ⚙️ Backend API

* **Python**: The core language for our backend logic, tool routing, and database interactions.
* **FastAPI**: Provides a high-performance, asynchronous REST API for the frontend to communicate with (handling cart state, user profiles, and context generation).
* **Asyncio**: Used heavily to manage concurrent tool executions, API calls, and non-blocking real-time endpoints.
* **Google Cloud Secret Manager**: Securely stores and injects the Gemini API keys and other sensitive credentials at runtime.

## 🖥️ Frontend & User Interface

* **React**: Drives the dynamic, component-based user interface.
* **TypeScript**: Ensures type safety across the complex states (shopping cart, chat history, live agent status).
* **Vite**: Used as the lightning-fast build tool and development server.
* **Tailwind CSS**: For responsive, modern, and highly customizable styling directly in the markup.
* **Web Audio API**: Crucial for capturing raw microphone input, resampling it to `16kHz`, and encoding it as `Base64` PCM data to stream directly to Gemini over WebSockets.

## ☁️ Cloud & Deployment

* **Google Cloud Run**: Both the React frontend container and the Python FastAPI backend container are deployed to Cloud Run, providing secure, auto-scaling, serverless HTTP hosting.
* **Docker**: Used to containerize both the frontend and backend applications, ensuring consistency from local development to cloud deployment.
