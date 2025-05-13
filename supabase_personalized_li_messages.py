import os
from dotenv import load_dotenv
from openai import OpenAI
from supabase import create_client, Client

# Load environment variables
load_dotenv()

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Initialize Supabase client
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def fetch_leads_and_companies():
    """Fetches leads with their associated company details."""
    print("Fetching leads...")

    # Debug: Check all leads
    all_leads = supabase.table("leads").select("*").execute()
    print(f"All leads debug: {all_leads.data}")

    # Fetch leads where linkedin_message is NULL
    response = (
        supabase
        .table("leads")
        .select("id, first_name, last_name, title, organization_primary_domain, linkedin_message")
        .is_("linkedin_message", None)  # Use None instead of "null"
        .not_.is_("ranking", "null")    # Filter where ranking is NOT NULL
        .execute()
    )

    print(f"Raw API Response: {response.data}")  # Debug

    if not response.data:
        print("No leads found that need a LinkedIn message.")
        return []

    leads = response.data

    # Get unique domains
    company_domains = list({lead["organization_primary_domain"] for lead in leads if lead["organization_primary_domain"]})

    # Fetch company data
    company_data = {}
    if company_domains:
        company_response = (
            supabase
            .table("companies")
            .select("organization_primary_domain, about_us")
            .in_("organization_primary_domain", company_domains)
            .execute()
        )
        if company_response.data:
            company_data = {c["organization_primary_domain"]: c["about_us"] for c in company_response.data}

    # Attach about_us data to each lead
    for lead in leads:
        lead["about_us"] = company_data.get(lead["organization_primary_domain"], "")

    return leads

def generate_message(first_name, title, company_name, about_us):
    """Generates a personalized LinkedIn message using OpenAI."""
    system_message = (
        "You write personalized LinkedIn messages. All responses must be under 200 characters. "
        "Keep messages professional, engaging, and concise.\n\n"
        "If the recipient's title includes 'recruiter', 'manager', 'director', or something similar, structure the message as:\n"
        "[greetings with their name][reason I like the company or something I appreciate about its unique offer based on the about_us section]"
        "[I understand you may not be hiring right now but I'd love to get involved in the space][would love to connect]\n\n"
        "If the recipient's title includes 'sales engineer', 'solutions engineer', 'solutions architect', or something similar, structure it as:\n"
        "[greetings with their name][I came across your profile while researching your company and was inpressed with your background.][would love to connect]"
    )

    user_prompt = f"""
    Create a LinkedIn message for {first_name}, who is a {title} at {company_name}.
    Use the following company description to personalize the message:
    \"{about_us}\"
    """

    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=75,
            temperature=0.7
        )

        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Error generating message for {first_name} at {company_name}: {e}")
        return "ERROR"

def update_linkedin_messages():
    """Fetch leads, generate messages, and update the database."""
    leads = fetch_leads_and_companies()
    if not leads:
        return

    for lead in leads:
        try:
            print(f"Processing lead: {lead['first_name']} {lead['last_name']} - {lead['title']} at {lead['organization_primary_domain']}")

            message = generate_message(
                first_name=lead["first_name"],
                title=lead["title"],
                company_name=lead["organization_primary_domain"],
                about_us=lead["about_us"] or ""
            )

            print(f"Generated message: {message}")

            # Attempt to update the lead's LinkedIn message
            update_response = (
                supabase
                .table("leads")
                .update({"linkedin_message": message})
                .eq("id", lead["id"])
                .execute()
            )

            print(f"Update Response Debug: {update_response}")  # 🔍 Debugging step

            #  Assume success unless an exception occurs
            print(f"Updated lead {lead['id']} successfully with message: {message}")

        except Exception as e:
            print(f"Error encountered for lead {lead['id']}: {e}")
            print("Inserting 'ERROR' into linkedin_message and continuing...")
            supabase.table("leads").update({"linkedin_message": "ERROR"}).eq("id", lead["id"]).execute()

if __name__ == "__main__":
    update_linkedin_messages()
