# MCP Server

import sys
import requests
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("MedBridgeTools")

@mcp.tool()
def get_drug_interactions(drug_list: list[str]) -> str:
    """Check for known drug interactions using the OpenFDA Adverse Events API.

    Args:
        drug_list: A list of drug names to check (e.g., ["Aspirin", "Warfarin"]).
    """
    if not drug_list:
        return "⚠️ No drugs provided. Please specify at least one medication name."

    if len(drug_list) < 2:
        return (
            f"ℹ️ Only one drug specified ({drug_list[0]}). "
            "Drug interaction checks require at least two medications."
        )

    base_url = "https://api.fda.gov/drug/event.json"
    search_terms = "+AND+".join(
        [f'patient.drug.medicinalproduct:"{drug.strip()}"' for drug in drug_list]
    )
    params = {
        "search": search_terms,
        "limit": 3,
    }

    try:
        response = requests.get(base_url, params=params, timeout=10)

        if response.status_code == 200:
            data = response.json()
            results = data.get("results", [])

            if results:
                reactions: list[str] = []
                for result in results:
                    for reaction in result.get("patient", {}).get("reaction", []):
                        desc = reaction.get("reactionmeddrapt", "")
                        if desc and desc not in reactions:
                            reactions.append(desc)

                reaction_summary = ", ".join(reactions[:5]) if reactions else "unspecified"
                drug_names = ", ".join(drug_list)

                return (
                    f"⚠️ WARNING: OpenFDA has {data.get('meta', {}).get('results', {}).get('total', 'multiple')} "
                    f"adverse event reports involving the co-administration of: {drug_names}.\n"
                    f"   Common reported reactions: {reaction_summary}.\n"
                    f"   ⚕️ Recommendation: Consult your doctor or pharmacist about this combination."
                )
            else:
                return f"✅ No adverse event reports found in OpenFDA for the combination of {', '.join(drug_list)}."

        elif response.status_code == 404:
            return f"✅ No adverse event reports found in OpenFDA for: {', '.join(drug_list)}."
        else:
            return f"⚠️ OpenFDA API returned status {response.status_code}. Unable to check interactions."

    except requests.exceptions.Timeout:
        return "⚠️ OpenFDA API request timed out. Please try again or consult a pharmacist."
    except requests.exceptions.ConnectionError:
        return "⚠️ Unable to connect to OpenFDA API. Please check your internet connection."
    except Exception as e:
        return f"⚠️ Unexpected error querying OpenFDA: {str(e)}."

@mcp.tool()
def create_calendar_event(title: str, date_time: str) -> str:
    """Create a calendar event/reminder for the patient.

    Args:
        title: The event title (e.g., "Take blood pressure medication").
        date_time: The date/time string (e.g., "2024-01-15 at 8:00 AM").
    """
    print(
        f"\n📅 [MOCK CALENDAR API] Event Created:"
        f"\n   Title: {title}"
        f"\n   When:  {date_time}"
        f"\n   Status: Confirmed ✓\n",
        file=sys.stderr,
    )

    return (
        f"✅ Calendar event created successfully!\n"
        f"   📌 Event: {title}\n"
        f"   📅 Scheduled: {date_time}\n"
        f"   🔔 Reminder will be sent 30 minutes before."
    )

if __name__ == "__main__":
    mcp.run()
