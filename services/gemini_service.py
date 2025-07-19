
import logging
import time
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

GEMINI_SAFETY_SETTINGS = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
]

class GeminiService:
    def __init__(self, api_key, context_history_enabled=True, system_instruction=None, model_name=None):
        self.api_key = api_key
        self.model = None
        self._enabled = False
        self.context_history_enabled = context_history_enabled
        self.system_instruction = system_instruction or "You are a helpful assistant."
        self.model_name = model_name or 'gemini-1.5-flash-latest'
        self.last_latency = 0.0
        self.init_model()

    def init_model(self):
        if not GEMINI_AVAILABLE or not self.api_key:
            self._enabled = False
            return

        try:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel(
                self.model_name,
                system_instruction=self.system_instruction
            )
            logging.info(f"Gemini model '{self.model_name}' initialized successfully.")
            self._enabled = True
        except Exception as e:
            logging.error(f"Failed to initialize Gemini model '{self.model_name}': {e}. Features will be disabled.")
            self.model = None
            self._enabled = False

    def set_model(self, new_model_name: str):
        """Sets a new model name and re-initializes the model."""
        logging.info(f"Attempting to switch Gemini model to '{new_model_name}'")
        self.model_name = new_model_name
        self.init_model()
        return self.is_enabled()

    def list_available_models(self) -> list[str]:
        """Lists available generative models suitable for chat."""
        if not GEMINI_AVAILABLE or not self.api_key:
            logging.error("Cannot list models, Gemini library or API key is not available.")
            return []
        try:
            models = []
            for m in genai.list_models():
                if 'generateContent' in m.supported_generation_methods:
                    models.append(m.name)
            return models
        except Exception as e:
            logging.error(f"Failed to list Gemini models: {e}")
            return []

    def is_enabled(self):
        return self._enabled and self.model is not None

    def generate_content(self, prompt, history=None):
        if not self.is_enabled():
            return f"[Gemini Error] Service not available. Current model: '{self.model_name}'."

        start_time = time.time()
        try:
            # Format history for Gemini chat
            formatted_history = []
            if history and self.context_history_enabled:
                for msg in history:
                    role = "model" if msg['is_bot'] else "user"
                    formatted_history.append({'role': role, 'parts': [msg['message']]})
            
            chat = self.model.start_chat(history=formatted_history)
            response = chat.send_message(prompt, stream=False, safety_settings=GEMINI_SAFETY_SETTINGS)
            
            if hasattr(response, 'text') and response.text.strip():
                return response.text
            elif hasattr(response, 'parts') and response.parts:
                full_text = "".join(part.text for part in response.parts if hasattr(part, 'text'))
                if full_text.strip(): return full_text
            elif hasattr(response, 'prompt_feedback') and response.prompt_feedback.block_reason:
                 return f"[Gemini Error] Request blocked: {response.prompt_feedback.block_reason.name}"
            
            return "[Gemini] (Received an empty response)"
        except Exception as e:
            logging.error(f"Error during Gemini API call: {e}", exc_info=True)
            return f"[Bot Error] Error contacting Gemini. Check if model '{self.model_name}' supports chat."
        finally:
            self.last_latency = time.time() - start_time

    def generate_welcome_message(self):
        if not self.is_enabled():
            return "Welcome!"
        # This function can now also be influenced by the system instruction.
        return self.generate_content("Generate a short, friendly, and creative welcome message for a user who just joined a chat channel.")