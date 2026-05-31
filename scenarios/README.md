The 15 Scenarios
Each scenario is a JSON file in scenarios/. It defines a different NPC personality:

What's in the JSON	What it controls
- starting_agreement	How opposed the NPC starts (-1 = maximally opposed)
- threshold	            How convinced they need to be to win
- resistance_profile	Which argument types move them and by how much
- repetition_penalty	How much each repeat of an arg type costs
- response_templates	The actual words the NPC says, per arg type and tone
The "hidden" part: the AI never sees resistance_profile or agreement. It only sees the NPC's words and has to infer what's working.