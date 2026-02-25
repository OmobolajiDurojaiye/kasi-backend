import csv
import io
from app.modules.invoices.models import Invoice, InvoiceItem
from app.modules.auth.models import User
from app import db
from datetime import datetime
import re

class CsvService:
    @staticmethod
    def process_csv(user_id, file_stream):
        """
        Parses a CSV file and creates invoices.
        Expected Headers: Date, Customer, Amount, Description
        """
        user = User.query.get(user_id)
        if not user:
            return {"error": "User not found"}

        stream = io.StringIO(file_stream.read().decode("UTF8"), newline=None)
        csv_reader = csv.DictReader(stream)
        
        # Normalize headers
        if not csv_reader.fieldnames:
            return {"error": "Empty CSV file"}
            
        required_headers = ['Date', 'Customer', 'Amount', 'Description']
        
        # Check if headers exist (case-insensitive)
        headers = [h.strip() for h in csv_reader.fieldnames]
        # Allow some flexibility
        # We need to map actual headers to required ones
        
        created_count = 0
        errors = []
        
        for row_idx, row in enumerate(csv_reader):
            try:
                # Basic validation
                date_str = row.get('Date') or row.get('date')
                customer = row.get('Customer') or row.get('customer') or row.get('Client')
                amount_str = row.get('Amount') or row.get('amount') or row.get('Price')
                desc = row.get('Description') or row.get('description') or row.get('Item')
                
                if not (date_str and customer and amount_str):
                    continue # Skip empty rows
                
                # Parse Date (Assume YYYY-MM-DD or DD/MM/YYYY)
                # Try simple parsing
                try:
                    date_issued = datetime.strptime(date_str, '%Y-%m-%d').date()
                except ValueError:
                    try:
                        date_issued = datetime.strptime(date_str, '%d/%m/%Y').date()
                    except ValueError:
                         date_issued = datetime.utcnow().date() # Fallback
                
                # Parse Amount (Remove currency symbols)
                amount = float(re.sub(r'[^\d.]', '', amount_str))
                
                # Create Invoice
                invoice = Invoice(
                    user_id=user.id,
                    reference=f"BLK-{int(datetime.now().timestamp())}-{row_idx}",
                    date_issued=date_issued,
                    due_date=date_issued, # Default due immediately
                    total_amount=amount,
                    status='Paid', # Assume bulk sales are paid? Or maybe Pending. Let's assume Paid for "Sales Notebook" imports.
                    customer_name=customer,
                    customer_email="",
                    customer_phone=""
                )
                db.session.add(invoice)
                db.session.commit()
                
                item = InvoiceItem(
                    invoice_id=invoice.id,
                    description=desc or "Bulk Import Item",
                    quantity=1,
                    unit_price=amount,
                    total_price=amount
                )
                db.session.add(item)
                created_count += 1
                
            except Exception as e:
                errors.append(f"Row {row_idx + 1}: {str(e)}")
                
        db.session.commit()
        
        return {
            "created": created_count,
            "errors": errors
        }
