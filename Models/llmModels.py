from strands.models.openai import OpenAIModel
import os
from dotenv import load_dotenv
load_dotenv()

model=OpenAIModel(model_id="gpt-4o-mini",client_args={"api_key":os.getenv("OPENAI_API_KEY")})