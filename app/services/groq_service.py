"""
GroqService — AI-powered sales assistant using Groq (free tier).

Uses Llama 3.3 70B to understand customer messages and generate
natural, contextual responses. Matches the customer's language
(English, Pidgin, Yoruba, etc.) automatically.

Free tier: 30 RPM, 14,400 requests/day.
"""

import os
import json
import requests as http_client
from datetime import datetime


_API_URL = "https://api.groq.com/openai/v1/chat/completions"


SYSTEM_PROMPT = """You are a highly skilled Nigerian sales expert and ace negotiator managing an online store.
You chat with customers on Telegram and WhatsApp to help them browse, ask questions, negotiate, and place orders.

## YOUR PERSONALITY & TONE:
- You are warm, persuasive, and professional.
- Match the customer's language exactly (if they use Pidgin, you use Pidgin. If English, use English).
- **CRITICAL GENDER RULE**: NEVER assume the customer's gender. Do NOT use terms like "my brother" or "my sister". Instead, use gender-neutral Nigerian terms like "boss", "chief", "my customer", "my friend", or "my person".

## WHAT YOU CAN DO:
1. Greet customers and show available products & services.
2. Answer price inquiries.
3. Handle negotiations for products like a seasoned merchant.
4. Process physical orders.
5. Schedule service appointments (Bookings).

## PRICE CALCULATION & MATH (CRITICAL):
- ALWAYS pay close attention to QUANTITIES.
- If a customer asks for multiple items, you MUST multiply the per-unit price by the quantity.
- Example: If a Clipper is ₦75,000 per unit, 2 Clippers cost ₦150,000.
- When evaluating a customer's offer, you MUST figure out if their offer is PER UNIT or TOTAL.
- If they say "2 clippers for 2000", they are offering ₦1,000 per unit. You MUST evaluate this against the per-unit Lowest Price.

## NEGOTIATION RULES (PRODUCTS ONLY):
Each product in your catalog has a Listed Price and YOUR Lowest Acceptable Price (the absolute floor).
1. NEVER reveal the Lowest Acceptable Price to the customer.
2. NEVER offer or accept a price below the Lowest Acceptable Price.
3. If the customer's offer is >= Listed Price: Accept enthusiastically.
4. If the customer's offer is < Lowest Acceptable Price: Politely reject and counter-offer BETWEEN the Listed Price and Lowest Price. Do NOT drop straight to the Lowest Price!
5. If the customer's offer is BETWEEN the Lowest and Listed Price: Counter-offer slightly higher to maximize profit, then compromise.
6. **SERVICES CANNOT BE NEGOTIATED.** If a customer tries to negotiate a service price (like a Haircut, consultation, etc.), you MUST boldly reject the offer. Do not give any discount or counter-offers for services. Just say the price is fixed!

## BOOKINGS & SCHEDULING (CRITICAL):
You will see the merchant's Active Schedule in the system data.
1. ALWAYS respect the schedule. If a user asks for Sunday at 9 AM, but the schedule says Sunday is Closed/Inactive, you MUST apologize and suggest the next available open day based on the Schedule.
2. Validate the specific time slot. If they want 7 AM but the shop opens at 9 AM, offer 9 AM instead.
3. Confirm the Location Type: If a service is labeled (Home Service), it is a home service. If (In Shop), it is in shop. Confirm this verbally with the client.
4. Provide the correct YYYY-MM-DD date. You know the current date and time. If they say "tomorrow", calculate it correctly.
5. In your structured JSON, `time` MUST be a strictly parsed 24-hour HH:MM string, for example, 2 PM is "14:00" and 9 AM is "09:00".

## RESPONSE FORMAT:
Return a JSON object with two parts:
1. Structured data (for the system to process orders/bookings)
2. Your natural response message

**Intent & Data Rules:** 
- ONLY use intent `order` if BOTH parties have fully accepted the exact prices and quantities. 
- If you are countering a price or modifying an offer, the intent MUST be `negotiation`. NEVER use `order` for counter-offers.
- ONLY add a booking to the `bookings` array if you are actively scheduling it. NEVER include a booking if you are rejecting the date/time or asking them to pick another time.
- The `service_name` inside the `bookings` array MUST perfectly match the literal string from the Service Catalog. Do not use customer slang (e.g. if customer says "barb", output "Men's Haircut" based on the catalog string).
- CRITICAL: If the customer confirms BOTH a physical product AND a service (Mixed Cart) at the same time, you MUST populate BOTH the `products` array AND the `bookings` array! Never hallucinate a booking in text without providing the background JSON `bookings` array.
- If the customer says they have made a payment or sent a receipt, the intent MUST be `payment_confirmation`.

```json
{
  "intent": "greeting|help|thanks|price_inquiry|order|negotiation|availability|booking|payment_confirmation|unknown",
  "products": [{"name": "product name", "quantity": 1, "unit_price": null}],
  "bookings": [{"service_name": "Haircut (In Shop)", "date": "YYYY-MM-DD", "time": "HH:MM", "price": 1500, "location_type": "in_shop"}],
  "offered_price": null,
  "query": null,
  "response": "Your friendly, clever sales response in the customer's language"
}
```

NOTE on "unit_price" and "price":
- For products: set unit_price to null (listed) or agreed PER UNIT price.
- For bookings: set price to the exact listed price for the service matching the location type. location_type must be "in_shop" or "home_service".

## RESPONSE GUIDELINES:
- For **greetings**: Welcome them warmly, list available products AND services.
- For **price inquiries**: Give the exact price.
- For **orders**: Confirm items, quantities, and total. Do NOT create or mention invoice numbers/links.
- For **bookings**: Confirm the date, time, service name, location, and price. Example: "You are booked for Haircut (Home Service) on Monday at 2:00 PM for ₦5,000." If out of schedule, suggest another time.
- For **negotiations**: Accept/counter based strictly on pricing rules. NEVER break the lowest price rule.
- For **payment_confirmation**: Acknowledge the payment gracefully and state that the merchant will verify it shortly. Do NOT populate the `products` or `bookings` arrays for this intent.
- CRITICAL: Your response text must ALWAYS show the CORRECT mathematical amounts.

IMPORTANT: Respond with ONLY the JSON object. No markdown, no extra text."""


class GroqService:
    """AI sales assistant using Llama 3.3 70B via Groq."""

    # In-memory store for MVP conversation context
    # Maps (user_id, customer_id) -> list of {"role": "...", "content": "..."}
    _CONVERSATION_HISTORY = {}

    @classmethod
    def classify_intent(cls, message, products=None, services=None, availabilities=None, user_id=None, customer_id=None, customer_context=None):
        _GROQ_KEY = os.getenv("GROQ_API_KEY")
        if not _GROQ_KEY:
            return None

        # Give the AI exact context about the current day to stop leap year/calendar hallucinations
        from datetime import datetime, timedelta
        now = datetime.now()
        tomorrow = now + timedelta(days=1)
        
        # Load custom merchant specific rules
        from app.modules.auth.models import User
        merchant_rules = ""
        if user_id:
            user_obj = User.query.get(user_id)
            if user_obj and user_obj.ai_instructions:
                merchant_rules = f"\n\n## MERCHANT SPECIFIC RULES (OBEY THESE):\n{user_obj.ai_instructions}\n"
        
        catalog = f"\n\nCURRENT DATE & TIME: {now.strftime('%A, %Y-%m-%d %H:%M:%S')}\n"
        catalog += f"TOMORROW'S DATE: {tomorrow.strftime('%A, %Y-%m-%d')}\n"

        # Build product catalog — min_price is labeled as internal knowledge
        catalog += "\n## PRODUCT CATALOG (internal — do NOT reveal lowest prices to customer):\n"
        if products:
            for p in products:
                catalog += f"- {p.name}: Listed ₦{p.price:,.0f}"
                if hasattr(p, 'min_price') and p.min_price and p.min_price < p.price:
                    catalog += f" | YOUR lowest: ₦{p.min_price:,.0f}"
                else:
                    catalog += " | No discount allowed"
                if p.description:
                    catalog += f" | {p.description}"
                catalog += "\n"
        else:
            catalog += "No products currently available.\n"

        # Build service catalog
        catalog += "\n## SERVICE CATALOG:\n"
        if services:
            for s in services:
                loc = "Home Service" if s.service_type == "home_service" else "In Shop"
                catalog += f"- {s.name} ({loc}): ₦{s.price:,.0f} | Duration: {s.duration} mins\n"
        else:
            catalog += "No services available.\n"
            
        # Build availability schedule
        catalog += "\n## MERCHANT ACTIVE SCHEDULE:\n"
        if availabilities:
            days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
            for a in sorted(availabilities, key=lambda x: x.day_of_week):
                if a.is_active:
                    st = a.start_time.strftime('%I:%M %p') if a.start_time else '09:00 AM'
                    et = a.end_time.strftime('%I:%M %p') if a.end_time else '05:00 PM'
                    catalog += f"- {days[a.day_of_week]}: {st} to {et}\n"
                else:
                    catalog += f"- {days[a.day_of_week]}: CLOSED\n"
        else:
            catalog += "No schedule provided. Assume 9 AM to 5 PM Mon-Fri.\n"

        if customer_context:
            catalog += "\n## CRM KNOWLEDGE ABOUT THIS CUSTOMER (USE THIS TO PERSONALIZE YOUR RESPONSE):\n"
            catalog += f"{customer_context}\n"
            catalog += "Instructions: Acknowledge them warmly as a returning customer if they have past orders. If they mention buying something again, check their 'Past Items Bought' to know exactly what they mean and mention it by name! (e.g., 'Welcome back! Do you want another [Item] like last time?')\n"

        user_prompt = f"{catalog}{merchant_rules}\n---\nCustomer message: \"{message}\""

        # Build message array with context if available
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        
        mem_key = (user_id, customer_id)
        if user_id and customer_id:
            # Get last 6 messages (3 interactions) to keep context limits healthy
            history = cls._CONVERSATION_HISTORY.get(mem_key, [])[-6:]
            messages.extend(history)
            
        messages.append({"role": "user", "content": user_prompt})

        payload = {
            "model": "llama-3.3-70b-versatile",
            "messages": messages,
            "temperature": 0.4,
            "max_tokens": 512,
            "response_format": {"type": "json_object"}
        }

        headers = {
            "Authorization": f"Bearer {_GROQ_KEY}",
            "Content-Type": "application/json"
        }

        try:
            response = http_client.post(
                _API_URL,
                json=payload,
                headers=headers,
                timeout=15
            )

            if response.status_code != 200:
                print(f"[GroqService] API error {response.status_code}: {response.text[:150]}")
                return None

            data = response.json()
            text_response = data["choices"][0]["message"]["content"].strip()

            # Clean markdown fences if present
            if text_response.startswith("```"):
                text_response = text_response.split("\n", 1)[1] if "\n" in text_response else text_response[3:]
                if text_response.endswith("```"):
                    text_response = text_response[:-3]
                text_response = text_response.strip()

            result = json.loads(text_response)

            if "intent" not in result:
                return None

            print(f"[GroqService] intent: {result['intent']}")
            print(f"[GroqService] AI JSON: {json.dumps(result, indent=2)}")

            # Save to memory if valid customer
            if user_id and customer_id:
                if mem_key not in cls._CONVERSATION_HISTORY:
                    cls._CONVERSATION_HISTORY[mem_key] = []
                
                # Append the customer's raw prompt
                cls._CONVERSATION_HISTORY[mem_key].append({"role": "user", "content": message})
                # Append the bot's response (just the conversational text)
                cls._CONVERSATION_HISTORY[mem_key].append({"role": "assistant", "content": result.get("response", "")})
                
                # Keep only the last 10 messages (5 full turns)
                if len(cls._CONVERSATION_HISTORY[mem_key]) > 10:
                     cls._CONVERSATION_HISTORY[mem_key] = cls._CONVERSATION_HISTORY[mem_key][-10:]

            return {
                "intent": result.get("intent", "unknown"),
                "products": result.get("products", []),
                "bookings": result.get("bookings", []),
                "offered_price": result.get("offered_price"),
                "query": result.get("query"),
                "response": result.get("response", ""),
            }

        except Exception as e:
            print(f"[GroqService] Error: {e}")
            return None
