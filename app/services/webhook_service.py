"""
WebhookService — handles simulated messages from the Webhook Simulator.
Delegates all message processing to SalesAI.
"""

from app.services.sales_ai import SalesAI


class WebhookService:

    @staticmethod
    def process_simulation(user_id, text, platform='whatsapp'):
        """
        Process a simulated message and return a reply.
        """
        result = SalesAI.process(user_id, text, platform)
        # SalesAI returns a string for most intents, dict for orders
        if isinstance(result, dict):
            return {"reply": result["text"]}
        return {"reply": result}
