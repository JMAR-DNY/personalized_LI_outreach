from openai import OpenAI


import json
import os
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Initialize Supabase client
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Set OpenAI API key

# Define table and columns to embed
TABLE_NAME = "companies"
TEXT_COLUMNS = [
    "about_us",
    "target_market",
    "products_services",
    "awards_recognitions",
    "management_team",
    "technology_stack",
    "unique_selling_proposition"
]
VECTOR_COLUMNS = {col: f"{col}_embedding" for col in TEXT_COLUMNS}  # Corresponding vector columns

# OpenAI Embedding Function
def get_embedding(text):
    response = client.embeddings.create(model="text-embedding-ada-002",
    input=text)
    return response.data[0].embedding

# Fetch and process rows
try:
    # Build the filter to select rows where any embedding column is null
    query = supabase.table(TABLE_NAME).select("id, " + ", ".join(TEXT_COLUMNS))
    for vector_col in VECTOR_COLUMNS.values():
        query = query.is_(vector_col, None)  # Filter for null embedding columns

    response = query.execute()
    rows = response.data

    for row in rows:
        row_id = row["id"]
        updates = {}

        for column in TEXT_COLUMNS:
            text = row.get(column)
            if text:  # Ensure text is not None
                embedding = get_embedding(text)
                updates[VECTOR_COLUMNS[column]] = embedding  # Store embedding directly

        # Update row with embeddings
        if updates:
            supabase.table(TABLE_NAME).update(updates).eq("id", row_id).execute()

    print("Embeddings successfully generated and stored!")

except Exception as e:
    print(f"An error occurred: {e}")
