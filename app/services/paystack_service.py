import requests
import os
from flask import current_app

class PaystackService:
    @staticmethod
    def initialize_transaction(email, amount, reference, callback_url=None):
        """
        Initialize a Paystack transaction.
        Amount should be in kobo (naira * 100).
        """
        secret_key = os.environ.get('PAYSTACK_SECRET_KEY')
        if not secret_key:
            current_app.logger.error("Paystack Secret Key not found")
            return None

        url = "https://api.paystack.co/transaction/initialize"
        headers = {
            "Authorization": f"Bearer {secret_key}",
            "Content-Type": "application/json"
        }
        
        # Paystack expects amount in kobo
        amount_kobo = int(float(amount) * 100)
        
        data = {
            "email": email,
            "amount": amount_kobo,
            "reference": reference,
            "callback_url": callback_url or "http://localhost:5173/payment/callback" 
        }

        try:
            response = requests.post(url, headers=headers, json=data)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            current_app.logger.error(f"Paystack Error: {str(e)}")
            if hasattr(e, 'response') and e.response:
                 current_app.logger.error(f"Paystack Response: {e.response.text}")
            return None

    @staticmethod
    def verify_transaction(reference):
        """
        Verify a Paystack transaction by its reference.
        """
        secret_key = os.environ.get('PAYSTACK_SECRET_KEY')
        if not secret_key:
            current_app.logger.error("Paystack Secret Key not found")
            return None

        url = f"https://api.paystack.co/transaction/verify/{reference}"
        headers = {
            "Authorization": f"Bearer {secret_key}",
            "Content-Type": "application/json"
        }

        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            current_app.logger.error(f"Paystack Verification Error: {str(e)}")
            if hasattr(e, 'response') and e.response:
                 current_app.logger.error(f"Paystack Response: {e.response.text}")
            return None
