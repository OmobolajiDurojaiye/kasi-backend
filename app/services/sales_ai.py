"""
Kasi AI — Unified conversational sales engine.
Handles greetings, price inquiries, negotiation, multi-item orders,
and common phrases (thank you, help, etc.).
Used by both WebhookService and TelegramService.

Uses Groq AI (Llama 3.3 70B) for intelligent intent classification,
with comprehensive regex fallback for Pidgin & informal language.
"""

import re
from app.modules.invoices.models import Invoice, InvoiceItem, Customer
from app.modules.products.models import Product
from app.modules.services.models import Service, Availability, Booking
from app.modules.auth.models import User, CreditTransaction
from app import db
from datetime import datetime, timedelta


class SalesAI:

    # ── Public entry point ──────────────────────────────────────────────

    @staticmethod
    def process(user_id, text, platform='whatsapp', sender_name=None, customer_id=None):
        user = User.query.get(user_id)
        if not user:
            return "Sorry, this service is not configured properly."

        text = text.strip()
        products = Product.query.filter_by(user_id=user_id, in_stock=True).all()
        services = Service.query.filter_by(user_id=user_id, is_active=True).all()
        availabilities = Availability.query.filter_by(user_id=user_id, is_active=True).all()
        biz = user.business_name or 'our store'

        if not sender_name:
            sender_name = f"{platform.capitalize()} Customer"

        # ── Capture CRM Context (Purchase History) ──────────────
        customer = Customer.query.filter_by(user_id=user_id, name=sender_name).first()
        customer_context = None
        if customer:
            invoices = Invoice.query.filter_by(customer_id=customer.id).filter(Invoice.status.in_(['Paid', 'Pending'])).all()
            if invoices:
                total_spent = sum(inv.total_amount for inv in invoices if inv.status == 'Paid')
                orders_count = len(invoices)
                
                past_items = set()
                for inv in invoices:
                    items = InvoiceItem.query.filter_by(invoice_id=inv.id).all()
                    for it in items:
                        if it.description:
                            past_items.add(it.description)
                
                if orders_count > 0:
                    past_items_str = ", ".join(list(past_items)[:10])
                    customer_context = (
                        f"Customer Name: {sender_name} | "
                        f"Total Lifetime Orders: {orders_count} | "
                        f"Total Amount Spent: ₦{total_spent:,.0f} | "
                        f"Past Items Bought: {past_items_str}"
                    )

        # ── Try Groq AI first ───────────────────────────────────────────
        intent_data = SalesAI._classify_with_ai(
            text, 
            products=products, 
            services=services, 
            availabilities=availabilities, 
            user_id=user_id, 
            customer_id=customer_id,
            customer_context=customer_context
        )

        if intent_data:
            return SalesAI._dispatch_ai_intent(
                intent_data, user, products, biz, platform, sender_name, services=services
            )

        # ── Fallback to regex ───────────────────────────────────────────
        return SalesAI._process_with_regex(
            text, user, products, biz, platform, sender_name
        )

    # ── AI classification ───────────────────────────────────────────────

    @staticmethod
    def _classify_with_ai(text, products=None, services=None, availabilities=None, user_id=None, customer_id=None, customer_context=None):
        """Try Groq AI for intent classification."""
        try:
            from app.services.groq_service import GroqService
            return GroqService.classify_intent(
                text, 
                products=products, 
                services=services, 
                availabilities=availabilities, 
                user_id=user_id, 
                customer_id=customer_id,
                customer_context=customer_context
            )
        except Exception as e:
            print(f"[SalesAI] AI unavailable, using regex: {e}")
            return None

    @staticmethod
    def _dispatch_ai_intent(intent_data, user, products, biz, platform, sender_name, services=None):
        """Use AI-generated response directly. Create invoice/booking for orders."""
        intent = intent_data.get("intent", "unknown")
        ai_response = intent_data.get("response", "")

        if not ai_response:
            return None  # Fallback to regex if AI gave no response

        final_response_text = ai_response
        combined_result = None

        if intent in ["order", "booking"]:
            # ── For service bookings ────────
            ai_bookings = intent_data.get("bookings", [])
            if ai_bookings:
                booking_result = SalesAI._create_booking(user, services, ai_bookings, platform, sender_name)
                if booking_result:
                    if isinstance(booking_result, dict):
                        if "paused" in booking_result["text"].lower() and "contact the seller" in booking_result["text"].lower():
                            return booking_result["text"]
                        final_response_text += "\n\n" + booking_result["text"]
                        combined_result = booking_result # captures the PDF path
                    else:
                        final_response_text += "\n\n" + booking_result

            # ── For orders, create the invoice and append details ────────
            ai_products = intent_data.get("products", [])
            if ai_products:
                order_items = []
                for p in ai_products:
                    if p.get("name"):
                        qty = p.get("quantity", 1)
                        name = p.get("name", "")
                        negotiated_price = p.get("unit_price")  # None if not negotiated
                        order_items.append((qty, name, negotiated_price))

                if order_items:
                    order_result = SalesAI._create_invoice(
                        user, products, order_items, platform, sender_name
                    )
                    if order_result:
                        if isinstance(order_result, dict):
                            if "paused" in order_result["text"].lower() and "contact the seller" in order_result["text"].lower():
                                return order_result["text"]
                            
                            final_response_text += "\n\n" + order_result["text"]
                            if combined_result:
                                # We already have a booking PDF map. We just override text.
                                # Let's append text to the first combined_result, but set invoice_id to order so we know it's a multi-invoice turn
                                pass
                            else:
                                combined_result = order_result
                        else:
                            final_response_text += "\n\n" + order_result

        if combined_result:
            combined_result["text"] = final_response_text
            return combined_result

        return final_response_text

    # ── Regex-based classification (fallback) ───────────────────────────

    @staticmethod
    def _process_with_regex(text, user, products, biz, platform, sender_name):
        if SalesAI._is_greeting(text):
            return SalesAI._handle_greeting(biz, products)

        if SalesAI._is_help(text):
            return SalesAI._handle_help()

        if SalesAI._is_thanks(text):
            return SalesAI._handle_thanks(biz)

        negotiation = SalesAI._extract_negotiation(text)
        if negotiation:
            return SalesAI._handle_negotiation(products, negotiation)

        price_query = SalesAI._extract_price_query(text)
        if price_query:
            return SalesAI._handle_price_inquiry(products, price_query)

        order_items = SalesAI._extract_order_items(text, products)
        if order_items:
            return SalesAI._handle_order(user, products, order_items, platform, sender_name)

        avail_query = SalesAI._extract_availability(text)
        if avail_query:
            return SalesAI._handle_availability(products, avail_query)

        return SalesAI._handle_fallback(products)

    # ── Intent detection — Enhanced for Pidgin & informal language ──────

    @staticmethod
    def _is_greeting(text):
        lower = text.lower().strip()
        # Handle bot commands with @mentions
        if lower.startswith('/') and '@' in lower:
            lower = lower.split('@')[0]

        greetings = [
            # English
            'hello', 'hi', 'hey', 'good morning', 'good afternoon',
            'good evening', 'howdy', 'sup', 'yo', 'hiya', 'greetings',
            'good day', 'morning', 'afternoon', 'evening',
            # Bot commands
            '/start', '/hello',
            # Pidgin / Nigerian
            'how far', 'howfar', 'how body', 'howbody', 'how you dey',
            'wetin dey', 'what\'s up', 'whatsup', 'wassup', 'wazzup',
            'how e dey', 'how na', 'hafa', 'Bros', 'bros', 'bro',
            'sis', 'sister', 'abeg', 'oga', 'madam', 'boss',
            'e kaaro', 'e kaasan', 'e kale', 'bawo ni',  # Yoruba
            'sannu', 'ina kwana', 'barka da safe',  # Hausa
            'kedu', 'ndewo',  # Igbo
        ]

        for g in greetings:
            if lower == g or lower.startswith(g + ' ') or lower.startswith(g + '!') or lower.startswith(g + ',') or lower.startswith(g + '?'):
                return True
        return False

    @staticmethod
    def _is_help(text):
        lower = text.lower()
        patterns = [
            'help', 'menu', 'what can you do', 'options', 'commands',
            '/help', '/menu', 'how does this work', 'how to order',
            'how to buy', 'wetin you fit do', 'what you sell',
            'wetin you dey sell', 'show me', 'list',
        ]
        return any(p in lower for p in patterns)

    @staticmethod
    def _is_thanks(text):
        lower = text.lower()
        patterns = [
            'thank', 'thanks', 'thx', 'appreciate', 'cheers',
            'god bless', 'bless you', 'e se', 'ese',  # Yoruba
            'dalu', 'daalu',  # Igbo
            'na gode',  # Hausa
            'well done', 'nice one', 'respect',
        ]
        return any(p in lower for p in patterns)

    @staticmethod
    def _extract_price_query(text):
        """Extract product name from a price inquiry."""
        lower = text.lower().strip()
        patterns = [
            # English
            r'(?:how much|price|cost)(?:\s+(?:is|for|of|does|be|na))?\s+(?:the\s+|dat\s+|d\s+|dis\s+)?(.+)',
            r'what(?:\'s| is| be) the (?:price|cost) (?:of|for)\s+(.+)',
            r'how much (?:does?|is|be|na)\s+(.+?)(?:\s+cost)?',

            # Pidgin
            r'wetin (?:be|na) (?:the )?(?:price|cost) (?:of|for)\s+(.+)',
            r'wetin (?:be|na)\s+(.+?)(?:\s+cost|\s+price)?',
            r'how much (?:be|na)\s+(.+)',
            r'wetin .+ cost',
            r'(?:dat|dis|the)\s+(.+?)(?:\s+)?how much',
            r'(.+?) how much',
            r'(?:e|it|am) cost how much',
        ]

        for pat in patterns:
            m = re.search(pat, lower, re.IGNORECASE)
            if m:
                query = m.group(1).strip().rstrip('?.,!').strip()
                # Filter out noise words
                noise = ['please', 'pls', 'plz', 'abeg', 'biko', 'jor', 'o', 'na']
                words = [w for w in query.split() if w not in noise]
                if words:
                    return ' '.join(words)

        return None

    @staticmethod
    def _extract_negotiation(text):
        """Extract offered price and product from negotiation messages."""
        lower = text.lower().strip()

        patterns = [
            # "can you do 2000 for lip gloss" / "do 5000 for cream"
            r'(?:can you|you fit|abeg|pls|please|make una|e go|you go|fit)\s+(?:do|give|sell|make)\s+(?:me\s+)?(?:the\s+|dat\s+|d\s+)?(.+?)\s+(?:for\s+)?₦?\s*(\d[\d,]*)',
            r'(?:can you|you fit|abeg|pls|please|make una|e go|you go|fit)\s+(?:do|give|sell|make)\s+(?:me\s+)?₦?\s*(\d[\d,]*)\s+(?:for|on)\s+(.+)',

            # "I'll pay 2000 for lip gloss"
            r'(?:i\'?ll pay|i wan pay|i go pay|make i pay|lemme pay)\s*₦?\s*(\d[\d,]*)\s+(?:for|on)\s+(.+)',

            # "how about 2000 for lip gloss" / "what about"
            r'(?:how about|what about|what of)\s*₦?\s*(\d[\d,]*)\s+(?:for|on)\s+(.+)',
            r'(?:how about|what about|what of)\s+(.+?)\s+(?:for|at)\s*₦?\s*(\d[\d,]*)',

            # "2000 for lip gloss" (bare)
            r'^₦?\s*(\d[\d,]*)\s+(?:for)\s+(.+?)$',

            # "lip gloss for 2000" / "lip gloss at 2000"
            r'(.+?)\s+(?:for|at)\s*₦?\s*(\d[\d,]*)\s*$',

            # "last price 2000" / "last last 5000"
            r'(?:last|final)\s+(?:price\s+)?(?:na\s+)?₦?\s*(\d[\d,]*)\s+(?:for|on)\s+(.+)',
            r'(?:last|final)\s+(?:price\s+)?(?:na\s+)?₦?\s*(\d[\d,]*)',

            # Pidgin: "abeg you fit do me the lip gloss 2000"
            r'(?:abeg|pls|please)\s+(?:you\s+)?(?:fit\s+)?(?:do|give|sell)\s+(?:me\s+)?(?:the\s+|dat\s+|d\s+)?(.+?)\s+₦?\s*(\d[\d,]*)',
        ]

        for i, pat in enumerate(patterns):
            m = re.search(pat, lower, re.IGNORECASE)
            if m:
                g1, g2 = m.group(1), m.group(2) if m.lastindex >= 2 else (m.group(1), None)

                # Determine which group is price and which is product
                # If g1 is all digits, it's the price
                g1_clean = g1.replace(',', '').replace('₦', '').strip() if g1 else ''
                g2_clean = g2.replace(',', '').replace('₦', '').strip() if g2 else ''

                if g1_clean.isdigit() and g2:
                    price_str = g1_clean
                    product_query = g2.strip().rstrip('?.,!').strip()
                elif g2_clean.isdigit() and g1:
                    price_str = g2_clean
                    product_query = g1.strip().rstrip('?.,!').strip()
                else:
                    continue

                try:
                    price = float(price_str)
                    if price > 0 and product_query:
                        # Clean noise words from product name
                        noise = ['the', 'dat', 'dis', 'me', 'na', 'o', 'for', 'abeg', 'pls']
                        words = [w for w in product_query.split() if w not in noise]
                        if words:
                            return (price, ' '.join(words))
                except ValueError:
                    continue

        return None

    @staticmethod
    def _extract_order_items(text, products=None):
        """Extract order items — understands Pidgin, informal language, and bare quantities."""
        lower = text.lower().strip()

        # Order trigger phrases (English + Pidgin)
        order_triggers = [
            r'(?:i\s+want|i\s+need|order|buy|give me|get me|i\'?d like|i\'?ll take)',
            r'(?:i\s+wan|abeg give|abeg bring|carry come|bring|bring am)',
            r'(?:make i get|lemme get|let me get|i go take|i dey order)',
            r'(?:send me|deliver|pack)',
        ]

        # First: check for trigger phrase + items
        for trigger in order_triggers:
            m = re.search(trigger + r'\s+(.+)', lower, re.IGNORECASE)
            if m:
                return SalesAI._parse_item_list(m.group(1), products)

        # Second: check for bare "qty product" patterns (e.g. "2 lipgloss")
        # Only if the text looks like a simple item list
        items = SalesAI._parse_item_list(lower, products)
        if items:
            return items

        return []

    @staticmethod
    def _parse_item_list(text, products=None):
        """Parse a text string into a list of (quantity, product_name) tuples."""
        # Split by comma, &, and, plus
        parts = re.split(r'\s*(?:,|&|\band\b|\bplus\b|\bwith\b)\s*', text.strip())
        items = []

        for part in parts:
            part = part.strip().rstrip('?.,!').strip()
            if not part:
                continue

            # Match "2 lipgloss" or "lipgloss 2" or just "lipgloss"
            m = re.match(r'(\d+)\s+(.+)', part)
            if m:
                qty = int(m.group(1))
                name = m.group(2).strip()
                if qty > 0 and len(name) > 0:
                    items.append((qty, name))
                continue

            # "lipgloss x2" or "lipgloss ×2"
            m = re.match(r'(.+?)\s*[x×]\s*(\d+)', part)
            if m:
                name = m.group(1).strip()
                qty = int(m.group(2))
                if qty > 0 and len(name) > 0:
                    items.append((qty, name))
                continue

            # Bare product name — check if it matches a known product
            if products:
                matched = SalesAI._find_product(products, part)
                if matched:
                    items.append((1, part))

        return items

    @staticmethod
    def _extract_availability(text):
        """Check if customer is asking about product availability."""
        lower = text.lower().strip()

        patterns = [
            # English
            r'(?:do you (?:have|sell|stock|carry))\s+(.+)',
            r'(?:is|are)\s+(.+?)\s+(?:available|in stock)',
            r'(.+?)\s+(?:available|in stock)\s*\??',

            # Pidgin
            r'(?:you get|una get|you carry|una carry|you dey sell)\s+(.+)',
            r'(?:e dey|them dey|it dey)\s*\??\s*(.+)?',
            r'(?:you still get|una still get)\s+(.+)',
            r'(?:wetin )?(?:you|una) (?:get|carry)\s*\??\s*$',
        ]

        for pat in patterns:
            m = re.search(pat, lower, re.IGNORECASE)
            if m and m.group(1):
                return m.group(1).strip().rstrip('?.,!').strip()

        return None

    # ── Response handlers ───────────────────────────────────────────────

    @staticmethod
    def _handle_greeting(biz, products):
        greeting = f"Hello! 👋 Welcome to *{biz}*.\n\n"
        if products:
            greeting += "Here's what we have available:\n\n"
            for p in products:
                greeting += f"✅ *{p.name}* — ₦{p.price:,.0f}\n"
            greeting += (
                "\n*How to order:*\n"
                "• Just tell me what you want, e.g. \"I want 2 lipgloss\"\n"
                "• Ask \"how much is [product]?\" for details\n"
                "• You can negotiate! Try: \"Can you do ₦X for [product]?\"\n"
                "• I understand English, Pidgin, and more! 🇳🇬"
            )
        else:
            greeting += "We're still setting up our catalog. Check back soon! 🛍️"
        return greeting

    @staticmethod
    def _handle_help():
        return (
            "Here's what I can help you with:\n\n"
            "🛒 *Order:* \"I want 2 lipgloss\" or \"abeg give me 3 cream\"\n"
            "💰 *Price:* \"How much is soap?\" or \"wetin be the price?\"\n"
            "🤝 *Negotiate:* \"Can you do ₦5000 for lipgloss?\"\n"
            "📦 *Multi-order:* \"I want 2 lipgloss and 3 cream\"\n"
            "📋 *Browse:* Say \"hi\" to see all products\n"
            "❓ *Availability:* \"You get soap?\" or \"Do you have cream?\"\n\n"
            "💡 _I understand English, Pidgin, and other languages!_"
        )

    @staticmethod
    def _handle_thanks(biz):
        return (
            f"You're welcome! 😊 Thank you for shopping with *{biz}*.\n"
            "Need anything else? Just say *hi* to see our products!"
        )

    @staticmethod
    def _handle_price_inquiry(products, query):
        matched = SalesAI._find_product(products, query)
        if matched:
            reply = f"💰 *{matched.name}*\n"
            reply += f"Price: *₦{matched.price:,.0f}*\n"
            if matched.description:
                reply += f"\n_{matched.description}_\n"
            if matched.min_price and matched.min_price < matched.price:
                reply += "\n💡 _We're open to negotiation on this item!_\n"
            reply += f"\nTo order: just say \"I want [qty] {matched.name}\""
            return reply
        return SalesAI._not_found_response(products, query)

    @staticmethod
    def _handle_negotiation(products, negotiation):
        offered_price, query = negotiation
        matched = SalesAI._find_product(products, query)

        if not matched:
            return SalesAI._not_found_response(products, query)

        if offered_price >= matched.price:
            return (
                f"✅ Deal! *₦{matched.price:,.0f}* for *{matched.name}* works perfectly.\n\n"
                f"To complete your order, just say: \"I want 1 {matched.name}\""
            )

        min_price = matched.min_price or matched.price
        if offered_price >= min_price:
            return (
                f"🤝 You've got a deal! *₦{offered_price:,.0f}* for *{matched.name}* is accepted.\n\n"
                f"To order at this price, say: \"I want 1 {matched.name}\"\n\n"
                f"_Note: Final invoice will reflect the listed price. "
                f"Mention this negotiation to the seller for the agreed discount._"
            )

        if matched.min_price and matched.min_price < matched.price:
            return (
                f"😅 ₦{offered_price:,.0f} is a bit low for *{matched.name}*.\n"
                f"Our best price is *₦{matched.min_price:,.0f}* (listed at ₦{matched.price:,.0f}).\n\n"
                f"Want it at ₦{matched.min_price:,.0f}? Just let me know!"
            )
        else:
            return (
                f"😅 ₦{offered_price:,.0f} is below our price for *{matched.name}*.\n"
                f"The price is *₦{matched.price:,.0f}*.\n\n"
                f"Ready to order? Just say \"I want 1 {matched.name}\""
            )

    @staticmethod
    def _create_invoice(user, products, order_items, platform, sender_name):
        """Create an invoice (used by AI dispatch). Returns dict with text + pdf_path."""
        # Allow up to 20 credits of debt (-20) before cutting the merchant off.
        if user.kasi_credits < -19:
            return {
                "text": "Sorry, our automated system is currently paused. Please contact the seller directly to finalize your order!",
                "pdf_path": None,
                "invoice_id": None
            }

        line_items = []

        for item in order_items:
            # Unpack — negotiated_price is optional (3rd element)
            if len(item) == 3:
                qty, item_name, negotiated_price = item
            else:
                qty, item_name = item
                negotiated_price = None

            matched = SalesAI._find_product(products, item_name)
            if matched:
                # Use negotiated price if valid (>= min_price)
                price = matched.price
                if negotiated_price is not None:
                    min_price = matched.min_price if hasattr(matched, 'min_price') and matched.min_price else matched.price
                    if negotiated_price >= min_price:
                        price = negotiated_price
                line_items.append((matched.name, qty, price))

        if not line_items:
            return None

        total_amount = sum(q * p for _, q, p in line_items)

        customer = Customer.query.filter_by(user_id=user.id, name=sender_name).first()
        if not customer:
            customer = Customer(
                user_id=user.id,
                name=sender_name,
                phone="",
                email="",
                address=f"{platform.capitalize()} Order",
            )
            db.session.add(customer)
            db.session.commit()

        prefix = platform[:2].upper()
        invoice = Invoice(
            user_id=user.id,
            customer_id=customer.id,
            reference=f"{prefix}-{int(datetime.now().timestamp())}",
            date_issued=datetime.utcnow().date(),
            due_date=datetime.utcnow().date() + timedelta(days=1),
            total_amount=total_amount,
            status='Pending',
        )
        db.session.add(invoice)
        db.session.commit()

        for product_name, qty, unit_price in line_items:
            item = InvoiceItem(
                invoice_id=invoice.id,
                description=product_name,
                quantity=qty,
                unit_price=unit_price,
                total_price=qty * unit_price,
            )
            db.session.add(item)
            
        # Deduct 1 Kasi Credit
        user.kasi_credits -= 1
        log = CreditTransaction(
            user_id=user.id,
            amount=-1,
            transaction_type='ai_generation',
            description=f"Generated Invoice #{invoice.reference}"
        )
        db.session.add(log)
        db.session.commit()

        # Build invoice summary text
        reply = "🧾 *Invoice Generated!*\n\n"
        for product_name, qty, unit_price in line_items:
            reply += f"• {qty}x *{product_name}* — ₦{qty * unit_price:,}\n"
        reply += f"\n*Total: ₦{total_amount:,}*\n"
        reply += f"\n🏦 *Payment Instructions:*\nPlease transfer to the bank details listed in the attached PDF Invoice to complete your order!\n\nThank you! 🙏"

        # Generate PDF
        pdf_path = None
        try:
            from app.services.pdf_service import PDFService
            subtotal = total_amount
            tax_amount = subtotal * 0.075
            invoice_data = {
                'reference': invoice.reference,
                'date_issued': str(invoice.date_issued),
                'due_date': str(invoice.due_date),
                'subtotal': subtotal,
                'tax_amount': tax_amount,
                'total_amount': subtotal + tax_amount,
                'items': [
                    {
                        'description': pn,
                        'quantity': q,
                        'unit_price': up,
                        'total_price': q * up,
                    }
                    for pn, q, up in line_items
                ],
                'merchant': {
                    'business_name': user.business_name or 'BizFlow Store',
                    'phone': user.phone or '',
                    'address': user.address or '',
                    'logo_url': user.logo_url if hasattr(user, 'logo_url') else None,
                    'bank_name': user.bank_name if hasattr(user, 'bank_name') else None,
                    'account_number': user.account_number if hasattr(user, 'account_number') else None,
                    'account_name': user.account_name if hasattr(user, 'account_name') else None,
                },
                'customer': {
                    'name': sender_name,
                    'phone': '',
                    'email': '',
                },
            }
            pdf_path = PDFService.generate_invoice_pdf(invoice_data)
        except Exception as e:
            print(f"PDF generation failed: {e}")

        return {
            "text": reply,
            "pdf_path": pdf_path,
            "invoice_id": invoice.id,
        }

    @staticmethod
    def _create_booking(user, services, ai_bookings, platform, sender_name):
        """Create a booking and a booking slip from AI output."""
        if user.kasi_credits < -19:
            return {
                "text": "Sorry, our automated system is currently paused. Please contact the seller directly to finalize your booking!",
                "pdf_path": None,
                "invoice_id": None
            }

        line_items = []
        for b in ai_bookings:
            s_name = b.get("service_name", "")
            loc = b.get("location_type", "in_shop")
            
            # AI sometimes hallucinates 'in_shop' loc even if it puts (Home Service) in the name
            if "(Home Service)" in s_name or "home" in s_name.lower():
                loc = "home_service"
            elif "(In Shop)" in s_name or "shop" in s_name.lower():
                loc = "in_shop"
            
            b_date = b.get("date")
            b_time = b.get("time")
            
            # Match strictly by location type first to capture differentiated pricing (e.g Home vs Shop)
            filtered_services = [s for s in services if getattr(s, 'service_type', 'in_shop') == loc]
            matched = SalesAI._find_product(filtered_services, s_name)
            
            # Fallback if no specific loc matched
            if not matched:
                matched = SalesAI._find_product(services, s_name)
            if matched:
                d = None
                t = None
                try:
                    d = datetime.strptime(b_date, "%Y-%m-%d").date()
                except Exception as e:
                    print(f"Booking date parse error: {e}")
                    continue

                # Try common formats for time
                for fmt in ("%H:%M", "%I:%M %p", "%I:%M%p", "%H:%M:%S", "%I %p", "%I%p"):
                    try:
                        # Clean up strings like "9:00 AM" to "09:00 AM" for stricter `%I` parser if needed, 
                        # but Python `%I` already handles single digits on most platforms. 
                        # Just in case, try padding:
                        padded_time = b_time
                        if ':' in padded_time and len(padded_time.split(':')[0].strip()) == 1:
                            padded_time = '0' + padded_time.strip()
                        
                        t = datetime.strptime(padded_time, fmt).time()
                        break
                    except ValueError:
                        pass
                    
                    try:
                        t = datetime.strptime(b_time, fmt).time()
                        break
                    except ValueError:
                        pass
                
                if d and t:
                    dt = datetime.combine(d, t)
                    duration_mins = matched.duration if hasattr(matched, 'duration') and matched.duration else 30
                    et = (dt + timedelta(minutes=duration_mins)).time()
                    line_items.append((matched, d, t, et, loc))

        if not line_items:
            print("No valid line items parsed for booking.")
            print(f"AI Bookings attempting to parse: {ai_bookings}")
            return None

        # Build Customer
        customer = Customer.query.filter_by(user_id=user.id, name=sender_name).first()
        if not customer:
            customer = Customer(
                user_id=user.id,
                name=sender_name,
                phone="",
                email="",
                address=f"{platform.capitalize()} Client",
            )
            db.session.add(customer)
            db.session.commit()

        total_amount = sum(service.price for service, _, _, _, _ in line_items)

        # Build Invoice
        prefix = platform[:2].upper()
        invoice = Invoice(
            user_id=user.id,
            customer_id=customer.id,
            reference=f"{prefix}-{int(datetime.now().timestamp())}",
            date_issued=datetime.utcnow().date(),
            due_date=datetime.utcnow().date() + timedelta(days=1),
            total_amount=total_amount,
            status='Pending',
        )
        db.session.add(invoice)
        db.session.flush() # flush to get invoice.id

        reply = "📅 *Booking Confirmed!*\n\n"
        
        pdf_invoice_items = []
        for (service, b_date, b_time, e_time, loc) in line_items:
            # 1. Booking record
            booking = Booking(
                user_id=user.id,
                customer_id=customer.id,
                service_id=service.id,
                booking_date=b_date,
                booking_time=b_time,
                end_time=e_time,
                status="Confirmed",
                location_type=loc
            )
            db.session.add(booking)
            
            # 2. Invoice Item record
            loc_str = "Home Service" if loc == "home_service" else "In Shop"
            desc = f"{service.name} ({loc_str}) on {b_date.strftime('%b %d')} at {b_time.strftime('%I:%M %p')}"
            
            item = InvoiceItem(
                invoice_id=invoice.id,
                description=desc,
                quantity=1,
                unit_price=service.price,
                total_price=service.price,
            )
            db.session.add(item)
            
            pdf_invoice_items.append({
                'description': desc,
                'quantity': 1,
                'unit_price': service.price,
                'total_price': service.price,
            })

            reply += f"• *{service.name}* ({loc_str})\n"
            reply += f"  Date: {b_date.strftime('%B %d, %Y')}\n"
            reply += f"  Time: {b_time.strftime('%I:%M %p')}\n"
            reply += f"  Price: ₦{service.price:,.0f}\n\n"

        # Deduct 1 Kasi Credit
        user.kasi_credits -= 1
        log = CreditTransaction(
            user_id=user.id,
            amount=-1,
            transaction_type='ai_generation',
            description=f"Generated Booking & Invoice #{invoice.reference}"
        )
        db.session.add(log)
        db.session.commit()

        # Generate Invoice PDF
        pdf_path = None
        try:
            from app.services.pdf_service import PDFService
            subtotal = total_amount
            tax_amount = 0.0 # No tax on services right now to keep it simple, or user can add later
            
            invoice_data = {
                'reference': invoice.reference,
                'date_issued': str(invoice.date_issued),
                'due_date': str(invoice.due_date),
                'subtotal': subtotal,
                'tax_amount': tax_amount,
                'total_amount': subtotal + tax_amount,
                'items': pdf_invoice_items,
                'merchant': {
                    'business_name': user.business_name or 'BizFlow Store',
                    'phone': user.phone or '',
                    'address': user.address or '',
                    'logo_url': user.logo_url if hasattr(user, 'logo_url') else None,
                    'bank_name': user.bank_name if hasattr(user, 'bank_name') else None,
                    'account_number': user.account_number if hasattr(user, 'account_number') else None,
                    'account_name': user.account_name if hasattr(user, 'account_name') else None,
                },
                'customer': {
                    'name': sender_name,
                    'phone': '',
                    'email': '',
                },
            }
            pdf_path = PDFService.generate_invoice_pdf(invoice_data)
        except Exception as e:
            print(f"PDF generation failed for booking: {e}")

        reply += "Here is your booking confirmation slip. Payment can be made to the account details provided, or in-person upon service. We look forward to seeing you! 🙏"

        return {
            "text": reply,
            "pdf_path": pdf_path,
            "invoice_id": invoice.id
        }

    @staticmethod
    def _handle_order(user, products, order_items, platform, sender_name):
        # Allow up to 20 credits of debt (-20) before cutting the merchant off.
        if user.kasi_credits < -19:
            return {
                "text": "Sorry, our automated system is currently paused. Please contact the seller directly to finalize your order!",
                "pdf_path": None,
                "invoice_id": None
            }
            
        line_items = []

        for item in order_items:
            # Unpack — negotiated_price is optional (3rd element)
            if len(item) == 3:
                qty, item_name, negotiated_price = item
            else:
                qty, item_name = item
                negotiated_price = None

            matched = SalesAI._find_product(products, item_name)
            if matched:
                # Use negotiated price if valid (>= min_price)
                price = matched.price
                if negotiated_price is not None:
                    min_price = matched.min_price if hasattr(matched, 'min_price') and matched.min_price else matched.price
                    if negotiated_price >= min_price:
                        price = negotiated_price
                line_items.append((matched.name, qty, price))
            else:
                return SalesAI._not_found_response(products, item_name)

        total_amount = sum(q * p for _, q, p in line_items)

        customer = Customer.query.filter_by(user_id=user.id, name=sender_name).first()
        if not customer:
            customer = Customer(
                user_id=user.id,
                name=sender_name,
                phone="",
                email="",
                address=f"{platform.capitalize()} Order",
            )
            db.session.add(customer)
            db.session.commit()

        prefix = platform[:2].upper()
        invoice = Invoice(
            user_id=user.id,
            customer_id=customer.id,
            reference=f"{prefix}-{int(datetime.now().timestamp())}",
            date_issued=datetime.utcnow().date(),
            due_date=datetime.utcnow().date() + timedelta(days=1),
            total_amount=total_amount,
            status='Pending',
        )
        db.session.add(invoice)
        db.session.commit()

        for product_name, qty, unit_price in line_items:
            item = InvoiceItem(
                invoice_id=invoice.id,
                description=product_name,
                quantity=qty,
                unit_price=unit_price,
                total_price=qty * unit_price,
            )
            db.session.add(item)
            
        # Deduct 1 Kasi Credit
        user.kasi_credits -= 1
        log = CreditTransaction(
            user_id=user.id,
            amount=-1,
            transaction_type='ai_generation',
            description=f"Generated Invoice #{invoice.reference}"
        )
        db.session.add(log)
        db.session.commit()

        reply = "🧾 *Invoice Generated!*\n\n"
        for product_name, qty, unit_price in line_items:
            reply += f"• {qty}x *{product_name}* — ₦{qty * unit_price:,}\n"
        reply += f"\n*Total: ₦{total_amount:,}*\n"
        reply += f"\n🏦 *Payment Instructions:*\nPlease transfer to the bank details listed in the attached PDF Invoice to complete your order!\n\nThank you for your order! 🙏"

        pdf_path = None
        try:
            from app.services.pdf_service import PDFService
            subtotal = total_amount
            tax_amount = subtotal * 0.075
            invoice_data = {
                'reference': invoice.reference,
                'date_issued': str(invoice.date_issued),
                'due_date': str(invoice.due_date),
                'subtotal': subtotal,
                'tax_amount': tax_amount,
                'total_amount': subtotal + tax_amount,
                'items': [
                    {
                        'description': pn,
                        'quantity': q,
                        'unit_price': up,
                        'total_price': q * up,
                    }
                    for pn, q, up in line_items
                ],
                'merchant': {
                    'business_name': user.business_name or 'BizFlow Store',
                    'phone': user.phone or '',
                    'address': user.address or '',
                    'logo_url': user.logo_url if hasattr(user, 'logo_url') else None,
                    'bank_name': user.bank_name if hasattr(user, 'bank_name') else None,
                    'account_number': user.account_number if hasattr(user, 'account_number') else None,
                    'account_name': user.account_name if hasattr(user, 'account_name') else None,
                },
                'customer': {
                    'name': sender_name,
                    'phone': '',
                    'email': '',
                },
            }
            pdf_path = PDFService.generate_invoice_pdf(invoice_data)
        except Exception as e:
            print(f"PDF generation failed: {e}")

        return {
            "text": reply,
            "pdf_path": pdf_path,
            "invoice_id": invoice.id,
        }

    @staticmethod
    def _handle_availability(products, query):
        matched = SalesAI._find_product(products, query)
        if matched:
            return (
                f"Yes! *{matched.name}* is available ✅\n"
                f"Price: *₦{matched.price:,.0f}*\n\n"
                f"To order, just say: \"I want [qty] {matched.name}\""
            )
        return SalesAI._not_found_response(products, query)

    @staticmethod
    def _handle_fallback(products):
        reply = "🤔 I didn't quite understand that. Here's what I can do:\n\n"
        reply += (
            "• Say *hi* to browse our products\n"
            "• Ask *how much is [product]?*\n"
            "• Order with *I want 2 [product]*\n"
            "• Negotiate with *Can you do ₦X for [product]?*\n"
            "• I understand Pidgin too! 🇳🇬\n"
        )
        if products:
            reply += "\n*Available products:*\n"
            for p in products[:5]:
                reply += f"  ✅ {p.name} — ₦{p.price:,.0f}\n"
            if len(products) > 5:
                reply += f"  _...and {len(products) - 5} more_\n"
        return reply

    # ── Product matching ────────────────────────────────────────────────

    @staticmethod
    def _find_product(products, query):
        """Fuzzy-match a product by name — handles Pidgin abbreviations."""
        q = query.lower().strip()
        # Remove common noise
        q = re.sub(r'\b(the|dat|dis|one|some|dem|am)\b', '', q).strip()

        if not q:
            return None

        # Exact match
        for p in products:
            if p.name.lower() == q:
                return p

        # Partial match (query in product name or vice versa)
        for p in products:
            if q in p.name.lower() or p.name.lower() in q:
                return p

        # Word overlap (e.g., "lip gloss" matches "Lip Gloss Set")
        q_words = set(q.split())
        for p in products:
            p_words = set(p.name.lower().split())
            if q_words & p_words:  # any word in common
                return p

        return None

    @staticmethod
    def _not_found_response(products, query):
        reply = f"Sorry, we don't have *{query}* in stock right now.\n\n"
        if products:
            reply += "Here's what we *do* have:\n\n"
            for p in products[:5]:
                reply += f"✅ *{p.name}* — ₦{p.price:,.0f}\n"
            if len(products) > 5:
                reply += f"_...and {len(products) - 5} more. Say *hi* to see all._\n"
        else:
            reply += "Our catalog is being set up — check back soon!"
        return reply
