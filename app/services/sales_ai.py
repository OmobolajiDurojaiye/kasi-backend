"""
SalesAI — Unified conversational sales engine.
Handles greetings, price inquiries, negotiation, multi-item orders,
and common phrases (thank you, help, etc.).
Used by both WebhookService and TelegramService.

Uses Groq AI (Llama 3.3 70B) for intelligent intent classification,
with comprehensive regex fallback for Pidgin & informal language.
"""

import re
from app.modules.invoices.models import Invoice, InvoiceItem, Customer
from app.modules.products.models import Product
from app.modules.auth.models import User
from app import db
from datetime import datetime, timedelta


class SalesAI:

    # ── Public entry point ──────────────────────────────────────────────

    @staticmethod
    def process(user_id, text, platform='whatsapp', sender_name=None):
        user = User.query.get(user_id)
        if not user:
            return "Sorry, this service is not configured properly."

        text = text.strip()
        products = Product.query.filter_by(user_id=user_id, in_stock=True).all()
        biz = user.business_name or 'our store'

        if not sender_name:
            sender_name = f"{platform.capitalize()} Customer"

        # ── Try Groq AI first ───────────────────────────────────────────
        intent_data = SalesAI._classify_with_ai(text, products)

        if intent_data:
            return SalesAI._dispatch_ai_intent(
                intent_data, user, products, biz, platform, sender_name
            )

        # ── Fallback to regex ───────────────────────────────────────────
        return SalesAI._process_with_regex(
            text, user, products, biz, platform, sender_name
        )

    # ── AI classification ───────────────────────────────────────────────

    @staticmethod
    def _classify_with_ai(text, products):
        """Try Groq AI for intent classification."""
        try:
            from app.services.groq_service import GroqService
            return GroqService.classify_intent(text, products)
        except Exception as e:
            print(f"[SalesAI] AI unavailable, using regex: {e}")
            return None

    @staticmethod
    def _dispatch_ai_intent(intent_data, user, products, biz, platform, sender_name):
        """Use AI-generated response directly. Create invoice for orders."""
        intent = intent_data.get("intent", "unknown")
        ai_response = intent_data.get("response", "")

        if not ai_response:
            return None  # Fallback to regex if AI gave no response

        # ── For orders, create the invoice and append details ────────
        if intent == "order":
            ai_products = intent_data.get("products", [])
            if ai_products:
                # Include negotiated unit_price if AI provided one
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
                        # Combine AI's natural response with invoice details
                        if isinstance(order_result, dict):
                            order_result["text"] = ai_response + "\n\n" + order_result["text"]
                            return order_result
                        else:
                            return ai_response + "\n\n" + order_result

            # If order processing failed, still return the AI response
            return ai_response

        # ── All other intents: return AI response directly ──────────
        return ai_response

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
        """Create an invoice (used by AI dispatch). Returns dict with text + pdf_path.
        
        order_items: list of (qty, item_name) or (qty, item_name, negotiated_price)
        """
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
        db.session.commit()

        payment_link = f"https://paystack.com/pay/inv-{invoice.reference}"

        # Build invoice summary text
        reply = "🧾 *Invoice Generated!*\n\n"
        for product_name, qty, unit_price in line_items:
            reply += f"• {qty}x *{product_name}* — ₦{qty * unit_price:,}\n"
        reply += f"\n*Total: ₦{total_amount:,}*\n"
        reply += f"\n💳 Pay here: {payment_link}\n\nThank you! 🙏"

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
    def _handle_order(user, products, order_items, platform, sender_name):
        line_items = []

        for qty, item_name in order_items:
            matched = SalesAI._find_product(products, item_name)
            if matched:
                line_items.append((matched.name, qty, matched.price))
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
        db.session.commit()

        payment_link = f"https://paystack.com/pay/inv-{invoice.reference}"

        reply = "🧾 *Invoice Generated!*\n\n"
        for product_name, qty, unit_price in line_items:
            reply += f"• {qty}x *{product_name}* — ₦{qty * unit_price:,}\n"
        reply += f"\n*Total: ₦{total_amount:,}*\n"
        reply += f"\n💳 Pay here: {payment_link}\n\nThank you for your order! 🙏"

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
