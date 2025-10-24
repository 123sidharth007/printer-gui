from flask import Flask, request, render_template, redirect, url_for
import razorpay
import os
import time
from PyPDF2 import PdfReader
import requests

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['ORDER_FILES'] = {}

# Razorpay setup (replace with your test keys)
razorpay_client = razorpay.Client(auth=("rzp_test_RG9lbxm3vi0JVH", "csWpoDM8sl3DLubjjge3XlI8"))

# Replace with your active Linux/ngrok print URL
LINUX_PRINT_URL = "http://192.168.0.101:5001/print"

# ---------------------------
# Home Page
# ---------------------------
@app.route('/')
def index():
    return render_template('index.html')


# ---------------------------
# File Upload Route
# ---------------------------
@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return render_template('index.html', error="No file uploaded")

    file = request.files['file']
    if file.filename == '':
        return render_template('index.html', error="No file selected")

    if not file.filename.lower().endswith('.pdf'):
        return render_template('index.html', error="Invalid file format. Please upload a PDF.")

    filename = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    file.save(filename)

    # Count PDF pages
    pdf = PdfReader(filename)
    page_count = len(pdf.pages)
    cost = page_count * 1  # ₹1 per page (edit as needed)

    # Create Razorpay order
    order = razorpay_client.order.create({
        'amount': int(cost * 100),  # amount in paisa
        'currency': 'INR',
        'payment_capture': 1
    })
    order_id = order['id']
    app.config['ORDER_FILES'][order_id] = filename

    return render_template('payment.html',
                           order_id=order_id,
                           cost=cost,
                           key_id="rzp_test_RG9lbxm3vi0JVH")  # add your Razorpay key ID


# ---------------------------
# Function: Send file to printer (with retry)
# ---------------------------
def send_to_printer(file_path, retries=2):
    for attempt in range(retries):
        try:
            with open(file_path, 'rb') as f:
                response = requests.post(LINUX_PRINT_URL, files={'file': f}, timeout=15)
                if response.status_code == 200:
                    return True
                else:
                    print("Printer returned error:", response.status_code)
        except requests.exceptions.ConnectionError as e:
            print(f"Connection error on attempt {attempt + 1}: {e}")
            # Retry only for connection reset (104)
            if "104" in str(e):
                time.sleep(2)
                continue
            else:
                break
        except Exception as e:
            print("Unexpected error:", e)
            break
    return False


# ---------------------------
# Payment Success Route
# ---------------------------
@app.route('/payment_success/<order_id>')
def payment_success(order_id):
    try:
        payment = razorpay_client.order.payments(order_id)

        if not payment['items']:
            return render_template('index.html', error="Payment failed or not found")

        filename = app.config['ORDER_FILES'].get(order_id)
        if not filename:
            return render_template('index.html', error="File not found")

        # Send to printer
        success = send_to_printer(filename)
        if success:
            os.remove(filename)
            del app.config['ORDER_FILES'][order_id]
            return render_template('success.html')
        else:
            return render_template('index.html', error="Printer not reachable or offline")

    except Exception as e:
        return render_template('index.html', error=f"Payment verification failed: {str(e)}")


# ---------------------------
# Run Flask app
# ---------------------------
if __name__ == '__main__':
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    os.makedirs('static', exist_ok=True)
    app.run(debug=False, host='0.0.0.0')
