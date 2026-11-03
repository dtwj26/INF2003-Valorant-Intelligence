
# format agent names for display

def format_agent_name(name):
    if not name:
        return "Not recorded"

    agent = str(name).strip().lower()

    special_names = {
        "kayo": "KAY/O"
    }

    return special_names.get(agent, agent.capitalize())
