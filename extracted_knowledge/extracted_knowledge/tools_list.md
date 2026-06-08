# Available AI Tools

## Tool: `get_meal_plan_pricing` (Get Meal Plan Pricing)
**Enabled:** True

### Description:
Look up meal plan prices for a specific room type. Call this after room selection AND whenever the guest asks ANY question about food, meals, питание, dining, or что включено в стоимость. This is the ONLY authoritative source for meal pricing — never answer food questions from memory. Returns total_price_per_night for each meal plan — this is the COMPLETE all-in nightly rate (room + meals combined). It is NOT an add-on fee. Do NOT subtract the room base price. Quote total_price_per_night directly as the new rate: 'с полупансионом — 8 800 сом/ночь'. Never do arithmetic with the room price. Never present a delta. Just quote total_price_per_night.

---

## Tool: `transfer_to_manager` (Transfer to Manager)
**Enabled:** True

### Description:
Call this tool to notify the hotel manager about a completed or escalated lead.

Call when ANY of these happen:
1. Guest has confirmed room + meal plan + provided contacts → booking complete
2. Guest is a legal entity (юрлицо), requests invoice or contract
3. Corporate event, conference, teambuilding, banquet request
4. Sports camp or group training request
5. Complaint, conflict, or refund request
6. get_room_options returns {"error": "transfer_to_manager"} for groups > 10 → YOU MUST CALL THIS TOOL IMMEDIATELY. Do not just tell the guest you are transferring — actually call this tool first, then tell the guest.
7. Guest asks a question you cannot answer from the knowledge base

IMPORTANT: Whenever you say "I will transfer you to the manager" or "передам менеджеру" or any equivalent phrase — you MUST call this tool in the same turn. Never say those words without calling this tool. Saying the words without calling the tool is not a transfer.

This tool sends a Telegram notification to the manager with a structured summary.
Always call this tool before or immediately after telling the guest the transfer is happening — never ask the guest to wait.

---

## Tool: `get_room_images` (Send Room Photos)
**Enabled:** True

### Description:
Send photos of hotel rooms to the guest. Call this when a guest asks to see a room, asks what a room looks like, or requests photos. Infer the room category from context: 1-2 guests → standard_queen or standard_twin; 3-4 guests or guest mentions 'комфорт'/'comfort' → comfort; family with confirmed children → family. Pass multiple categories when the guest asks to see all rooms. Photos are sent directly to the guest — compose a natural reply referencing them.

---

## Tool: `get_room_options` (Get Room Options)
**Enabled:** True

### Description:
Use for standard groups — couples, friends, colleagues, solo travelers. Never call this when the guest mentions children, kids, baby, toddler, son, daughter, or family.

---

## Tool: `get_family_room` (Get Family Room)
**Enabled:** True

### Description:
Use ONLY when guest mentions children, kids, baby, toddler, son, daughter, family, or any indication they are travelling with minors. Returns family room options only. guest_count should be adults only — do not count children under 6.

---

